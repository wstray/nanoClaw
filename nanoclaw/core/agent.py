"""Main agent loop - LLM and tool execution cycle."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable, Optional

from nanoclaw.core.context import ContextBuilder
from nanoclaw.core.llm import LLMClient, LLMResponse, ToolCall
from nanoclaw.core.logger import get_logger
from nanoclaw.memory.store import MemoryStore
from nanoclaw.security.audit import AuditLog
from nanoclaw.security.budget import SessionBudget, SessionTracker
from nanoclaw.security.prompt_guard import PromptGuard
from nanoclaw.tools.registry import ToolRegistry

logger = get_logger(__name__)


class SessionCache:
    """In-memory cache for expensive tool results within a session."""

    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize SessionCache.

        Args:
            ttl_seconds: Cache TTL in seconds (default 5 min)
        """
        self._cache: dict[str, tuple[str, float]] = {}
        self.ttl = ttl_seconds

    def get(self, key: str) -> Optional[str]:
        """Get cached value if not expired."""
        if key in self._cache:
            result, ts = self._cache[key]
            if time.time() - ts < self.ttl:
                return result
            del self._cache[key]
        return None

    def set(self, key: str, value: str) -> None:
        """Set cached value."""
        self._cache[key] = (value, time.time())

    def invalidate(self, prefix: str) -> None:
        """Invalidate cache entries matching prefix."""
        keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._cache[k]

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()


class Agent:
    """Main agent that processes messages and executes tools."""

    # Tools that can be cached
    CACHEABLE = {"web_search", "web_fetch", "file_read", "memory_search"}
    # Tools that should never be cached (side effects)
    NEVER_CACHE = {"shell_exec", "file_write", "memory_save", "spawn_task"}

    def __init__(
        self,
        llm: LLMClient,
        memory: MemoryStore,
        tools: ToolRegistry,
        audit: AuditLog,
        budget: SessionBudget,
        prompt_guard: PromptGuard,
        context_builder: ContextBuilder,
        max_iterations: int = 15,
    ):
        """
        Initialize Agent.

        Args:
            llm: LLM client
            memory: Memory store
            tools: Tool registry
            audit: Audit log
            budget: Session budget
            prompt_guard: Prompt guard
            context_builder: Context builder
            max_iterations: Max iterations per message
        """
        self.llm = llm
        self.memory = memory
        self.tools = tools
        self.audit = audit
        self.budget = budget
        self.prompt_guard = prompt_guard
        self.ctx = context_builder
        self.max_iterations = max_iterations
        self.cache = SessionCache(ttl_seconds=300)

    async def run(
        self,
        user_message: str,
        session_id: str,
        confirm_callback: Optional[Callable] = None,
    ) -> str:
        """
        Main agent loop. Process user message, execute tools, return response.

        Uses ReAct pattern with automatic escalation: if agent struggles
        for 4+ iterations, inject a planning nudge (costs zero extra tokens).

        Args:
            user_message: User's message
            session_id: Session identifier
            confirm_callback: Async function for user confirmation

        Returns:
            Final response string
        """
        # Start session tracking
        session = SessionTracker(session_id=session_id)
        logger.debug(f"=== New message from session {session_id} ===")
        logger.debug(f"User: {user_message}")

        # 1. Load context (keep it lean for speed)
        history = await self.memory.get_history(session_id, limit=15)
        relevant_memories = await self.memory.search_memories(user_message, limit=5)

        # 2. Build messages array
        messages = self.ctx.build_messages(user_message, history, relevant_memories)

        # Check if user explicitly wants a plan
        if self._user_wants_plan(user_message):
            # Inject planning instruction
            messages[-1]["content"] = (
                f"{user_message}\n\n"
                "Please think through this step by step. "
                "Outline your plan, then execute it."
            )

        # Dynamic tool selection
        all_tool_schemas = self.tools.get_schemas()
        tool_schemas = self.ctx.select_tools(user_message, all_tool_schemas)

        # 3. Agent loop
        final_response = ""
        escalated = False  # Track if we've already injected escalation nudge

        for iteration in range(self.max_iterations):
            # Budget check
            allowed, reason = self.budget.check_iteration(session)
            if not allowed:
                final_response = (
                    f"Stopped: {reason}. "
                    f"Here's what I have so far:\n{final_response}"
                )
                break

            session.increment_iterations()
            logger.debug(f"--- Iteration {iteration + 1} ---")

            # Escalation: if 4+ iterations and still calling tools, nudge LLM
            # This is an internal directive, not a request for user-facing output
            if iteration >= 4 and not escalated and len(messages) > 2:
                last_msg = messages[-1]
                if last_msg.get("role") == "tool":
                    # Collect successful results to remind LLM what it already has
                    successes = []
                    for msg in messages:
                        if msg.get("role") == "tool":
                            content = msg.get("content", "")
                            if not self._is_error_result(content):
                                # Take first 150 chars of successful result
                                successes.append(content[:150])

                    nudge = (
                        "[Internal: You have taken many iterations. "
                        "Do NOT output a plan to the user. "
                        "Stop repeating failed calls - try different search terms. "
                        "Use the successful results you already have. "
                    )
                    if successes:
                        nudge += "Successful results so far: " + " | ".join(successes[-3:]) + " "
                    nudge += "Answer the user now with available information.]"

                    messages.append({"role": "user", "content": nudge})
                    escalated = True
                    logger.info(f"Escalating after {iteration} iterations")

            # Call LLM
            try:
                llm_response = await self.llm.chat(messages, tools=tool_schemas)
                session.add_tokens(llm_response.usage.total_tokens)
            except Exception as e:
                error_text = str(e)
                # Log full error, truncate for user response
                logger.error(f"LLM call failed: {error_text[:1000]}")
                if len(error_text) > 200:
                    error_text = error_text[:200] + "..."
                final_response = f"Error communicating with LLM: {error_text}"
                break

            # If text response with no tool calls -> done
            if llm_response.content and not llm_response.tool_calls:
                final_response = llm_response.content
                logger.debug(f"Final response: {final_response[:300]}...")
                break

            # If tool calls -> execute all in parallel
            if llm_response.tool_calls:
                # Log tool calls
                for tc in llm_response.tool_calls:
                    logger.debug(f"Tool call: {tc.name}({tc.arguments})")

                # Add assistant message with tool calls
                messages.append(llm_response.to_message())

                # Execute tools in parallel
                results = await self._execute_tools_parallel(
                    llm_response.tool_calls, session, confirm_callback
                )

                # Process results
                for tc, result in results:
                    compressed = self.ctx.compress_tool_output(tc.name, result)
                    sanitized = self.prompt_guard.sanitize_tool_output(
                        tc.name, compressed
                    )
                    # Log tool result (truncated for readability)
                    result_preview = sanitized[:200] + "..." if len(sanitized) > 200 else sanitized
                    logger.debug(f"Tool result [{tc.name}]: {result_preview}")
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": sanitized,
                        }
                    )

                # If there's also text content, capture it (this is "thinking")
                if llm_response.content:
                    logger.debug(f"LLM thinking: {llm_response.content}")
                    final_response = llm_response.content

                continue

            # No content and no tool calls -> something went wrong
            final_response = "I encountered an issue processing your request."
            break

        # 4. Save to history
        await self.memory.add_message(session_id, "user", user_message)
        await self.memory.add_message(session_id, "assistant", final_response)

        # 5. Background: extract and save important facts
        skip_memory = self._should_skip_memory(user_message)
        if not skip_memory:
            asyncio.create_task(
                self._extract_memories(user_message, final_response)
            )

        # 6. Audit log
        await self.audit.log(
            action_type="response",
            input_summary=user_message[:500],
            output_summary=final_response[:500],
            status="success",
            tokens=session.total_tokens,
            ms=session.elapsed_ms,
            session_id=session_id,
        )

        return final_response

    async def _execute_tools_parallel(
        self,
        tool_calls: list[ToolCall],
        session: SessionTracker,
        confirm_callback: Optional[Callable],
    ) -> list[tuple[ToolCall, str]]:
        """Execute multiple tools in parallel."""

        async def _run_one_tool(tc: ToolCall) -> tuple[ToolCall, str]:
            session.increment_tool_calls()

            # Check session cache
            cache_key = f"{tc.name}:{json.dumps(tc.arguments, sort_keys=True)}"
            if tc.name in self.CACHEABLE:
                cached = self.cache.get(cache_key)
                if cached:
                    return tc, cached

            result = await self._execute_tool_safely(tc, session, confirm_callback)

            # Cache the result only if not an error
            if tc.name in self.CACHEABLE and not self._is_error_result(result):
                self.cache.set(cache_key, result)

            # Invalidate file_read cache on file_write
            if tc.name == "file_write":
                path = tc.arguments.get("path", "")
                self.cache.invalidate(
                    f"file_read:{json.dumps({'path': path}, sort_keys=True)}"
                )

            return tc, result

        raw_results = await asyncio.gather(
            *[_run_one_tool(tc) for tc in tool_calls],
            return_exceptions=True,
        )

        results = []
        for i, item in enumerate(raw_results):
            if isinstance(item, Exception):
                tc = tool_calls[i]
                results.append((tc, f"ERROR: {item}"))
            else:
                results.append(item)

        return results

    async def _execute_tool_safely(
        self,
        tool_call: ToolCall,
        session: SessionTracker,
        confirm_callback: Optional[Callable],
    ) -> str:
        """Execute a tool call with full security pipeline."""
        start_time = time.time()

        try:
            # Track shell calls
            if tool_call.name == "shell_exec":
                session.increment_shell_calls()

            result = await asyncio.wait_for(
                self.tools.execute(
                    tool_call.name,
                    tool_call.arguments,
                    confirm_callback=confirm_callback,
                ),
                timeout=30,
            )

            elapsed_ms = int((time.time() - start_time) * 1000)
            await self.audit.log(
                action_type="tool_call",
                tool_name=tool_call.name,
                input_summary=str(tool_call.arguments)[:500],
                output_summary=str(result)[:500],
                status="success",
                ms=elapsed_ms,
            )
            return str(result)

        except asyncio.TimeoutError:
            await self.audit.log(
                action_type="tool_call",
                tool_name=tool_call.name,
                status="timeout",
            )
            return f"TIMEOUT: {tool_call.name} exceeded 30 second limit"

        except Exception as e:
            from nanoclaw.security.sandbox import SecurityError

            if isinstance(e, SecurityError):
                await self.audit.log(
                    action_type="blocked",
                    tool_name=tool_call.name,
                    input_summary=str(tool_call.arguments)[:500],
                    status="blocked",
                )
                return f"SECURITY: Action blocked - {e}"

            await self.audit.log(
                action_type="tool_call",
                tool_name=tool_call.name,
                status="error",
                output_summary=str(e)[:500],
            )
            return f"ERROR: {tool_call.name} failed - {e}"

    def _is_error_result(self, result: str) -> bool:
        """Check if result is an error that should not be cached."""
        error_prefixes = (
            "Search failed:",
            "Search rate limited",
            "Search error:",
            "ERROR:",
            "TIMEOUT:",
            "SECURITY:",
            "Failed to fetch:",
            "Network error",
            "Unknown tool:",
            "Invalid arguments",
        )
        return result.startswith(error_prefixes)

    def _should_skip_memory(self, user_message: str) -> bool:
        """Check if we should skip memory extraction for this message."""
        trivial_messages = {
            "thanks",
            "thank you",
            "ok",
            "okay",
            "got it",
            "cool",
            "yes",
            "no",
            "sure",
            "hi",
            "hello",
            "hey",
            "bye",
            "nice",
            "great",
            "perfect",
            "done",
            "next",
            "continue",
            "go ahead",
        }
        return (
            len(user_message) < 20
            or user_message.lower().strip() in trivial_messages
        )

    def _user_wants_plan(self, message: str) -> bool:
        """Check if user explicitly requested a plan."""
        explicit = ["make a plan", "plan first", "step by step", "create a plan"]
        return any(p in message.lower() for p in explicit)

    async def _extract_memories(
        self, user_message: str, response: str
    ) -> None:
        """Background task: extract important facts from conversation."""
        # Skip short messages
        if len(user_message) < 20:
            return

        triggers = [
            "my name",
            "i work",
            "i live",
            "i prefer",
            "i like",
            "i am",
            "my job",
            "i'm",
            "remember that",
            "don't forget",
            "i need",
            "my project",
            "my company",
            "my team",
        ]

        should_extract = any(t in user_message.lower() for t in triggers)
        if not should_extract:
            return

        try:
            extract_prompt = [
                {
                    "role": "system",
                    "content": (
                        "Extract factual information about the user from this "
                        "conversation. Return ONLY a JSON array of strings, "
                        "each being one fact. If no personal facts, return []. "
                        "Be concise. Max 3 facts."
                    ),
                },
                {
                    "role": "user",
                    "content": f"User: {user_message}\nAssistant: {response}",
                },
            ]
            result = await self.llm.chat(extract_prompt)

            # Parse JSON array of facts
            facts = json.loads(result.content)
            for fact in facts[:3]:
                await self.memory.save_memory(fact, category="auto")
        except Exception:
            pass  # Memory extraction is best-effort


# Global agent instance
_agent: Optional[Agent] = None


def get_agent() -> Agent:
    """Get the global Agent instance."""
    global _agent
    if _agent is None:
        from nanoclaw.core.config import get_config
        from nanoclaw.core.llm import get_llm_client
        from nanoclaw.memory.store import get_memory_store
        from nanoclaw.security.audit import get_audit_log
        from nanoclaw.security.budget import get_session_budget
        from nanoclaw.security.prompt_guard import get_prompt_guard
        from nanoclaw.tools.registry import get_tool_registry

        # Import tools to register them
        import nanoclaw.tools.files  # noqa: F401
        import nanoclaw.tools.memory_tools  # noqa: F401
        import nanoclaw.tools.shell  # noqa: F401
        import nanoclaw.tools.spawn  # noqa: F401
        import nanoclaw.tools.web  # noqa: F401

        config = get_config()
        tools = get_tool_registry()

        # Load skills from built-in and user directories
        from pathlib import Path

        builtin_skills = Path(__file__).parent.parent / "skills"
        user_skills = Path.home() / ".nanoclaw" / "skills"

        tools.load_skills(str(builtin_skills))
        tools.load_skills(str(user_skills))

        _agent = Agent(
            llm=get_llm_client(),
            memory=get_memory_store(),
            tools=tools,
            audit=get_audit_log(),
            budget=get_session_budget(),
            prompt_guard=get_prompt_guard(),
            context_builder=ContextBuilder(),
            max_iterations=config.agent.max_iterations,
        )
    return _agent


def set_agent(agent: Agent) -> None:
    """Set the global Agent instance."""
    global _agent
    _agent = agent
