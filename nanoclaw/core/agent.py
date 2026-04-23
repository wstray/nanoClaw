"""Main agent based on LangChain DeepAgents framework."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from typing import Callable, Optional, List, Any

# from deepagents.backends.filesystem import FilesystemBackend
# from deepagents.backends.sandbox import SandboxBackendProtocol
from nanoclaw.core.config import get_config
from nanoclaw.core.context import ContextBuilder
from nanoclaw.core.jsonl_logger import JSONLLogger, get_jsonl_logger, ThoughtType
from nanoclaw.core.logger import get_logger
from nanoclaw.core.llm import get_llm_client
from nanoclaw.memory.store import MemoryStore
from nanoclaw.security.audit import AuditLog
from nanoclaw.security.budget import SessionBudget
from nanoclaw.security.prompt_guard import PromptGuard
from nanoclaw.tools.registry import ToolRegistry
from deepagents import MemoryMiddleware

from langgraph.checkpoint.memory import InMemorySaver

# Langfuse imports for tracing
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
from dotenv import load_dotenv
load_dotenv()


logger = get_logger(__name__)


def get_platform_default_path() -> str:
    """Get platform-specific default PATH for shell environment."""
    import sys
    import os

    if sys.platform == "win32":
        # Windows default paths
        paths = [
            os.environ.get("SystemRoot", r"C:\Windows") + r"\System32",
            os.environ.get("SystemRoot", r"C:\Windows") + r"\System32\Wbem",
        ]
        return ";".join(paths)
    else:
        # Unix/Linux default paths
        return "/usr/bin:/bin:/usr/local/bin"


def get_platform_default_env() -> dict[str, str]:
    """Get platform-specific default environment variables.

    Windows Python requires certain environment variables to initialize properly,
    especially for random number generation.
    """
    import sys
    import os

    env = {"PATH": get_platform_default_path()}

    if sys.platform == "win32":
        # Windows requires these variables for Python to initialize properly
        # SystemRoot is needed for _Py_HashRandomization_Init
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        env["SystemRoot"] = system_root
        env["SYSTEMROOT"] = system_root  # Some apps use uppercase

        # TEMP/TMP are needed for temporary file operations
        temp_dir = os.environ.get(
            "TEMP", os.environ.get("TMP", r"C:\Windows\Temp"))
        env["TEMP"] = temp_dir
        env["TMP"] = temp_dir

    return env


class Agent:
    """
    Agent based on LangChain DeepAgents framework.

    This agent provides:
    - Automatic task planning (write_todos)
    - Subagent delegation for complex tasks
    - File system integration
    - Streaming output support
    - Full nanoClaw security layer integration
    - Langfuse observability and tracing
    """

    def __init__(
        self,
        model: str,
        memory: MemoryStore,
        tools: ToolRegistry,
        audit: AuditLog,
        budget: SessionBudget,
        prompt_guard: PromptGuard,
        context_builder: ContextBuilder,
        provider: str = "openai",  # Default provider
        base_url: Optional[str] = None,
        enable_planning: bool = True,
        enable_subagents: bool = True,
        jsonl_logger: Optional[JSONLLogger] = None,
        langfuse_callback: Optional[LangfuseCallbackHandler] = None,
    ):
        """
        Initialize DeepAgents-based Agent.

        Args:
            model: Model string (e.g., "deepseek-chat", "gpt-4o")
            memory: Memory store
            tools: Tool registry
            audit: Audit log
            budget: Session budget
            prompt_guard: Prompt guard
            context_builder: Context builder
            provider: Provider name for DeepAgents format
            base_url: Optional base URL for API (e.g., "https://api.deepseek.com")
            enable_planning: Enable DeepAgents planning features
            enable_subagents: Enable DeepAgents subagent spawning
            jsonl_logger: Optional JSONL logger instance
            langfuse_callback: Optional Langfuse callback handler for tracing
        """
        self.model = model
        self.provider = provider
        self.jsonl_logger = jsonl_logger or get_jsonl_logger()
        self.base_url = base_url
        self.memory = memory
        self.tools = tools
        self.audit = audit
        self.budget = budget
        self.prompt_guard = prompt_guard
        self.ctx = context_builder
        self.enable_planning = enable_planning
        self.enable_subagents = enable_subagents
        self.langfuse_callback = langfuse_callback

        # Lazy initialization: DeepAgents instances created per session
        self._agents: dict[str, any] = {}

    def _get_deepagent_instance(
        self, session_id: str, user_message: str, confirm_callback: Optional[Callable] = None
    ):
        """
        Get or create DeepAgents instance for this session.

        Args:
            session_id: Session identifier
            user_message: Current user message (for context building)
            confirm_callback: Optional confirmation callback

        Returns:
            SafeDeepAgent wrapper instance
        """
        if session_id not in self._agents:
            import os

            # Import here to avoid circular dependencies
            from deepagents import create_deep_agent
            from deepagents.backends.filesystem import FilesystemBackend
            from deepagents.backends.local_shell import LocalShellBackend
            from langchain.chat_models import init_chat_model
            from nanoclaw.deepagents.tools_adapter import get_all_adapted_tools
            from nanoclaw.core.config import get_workspace_path

            # Adapt all nanoClaw tools for DeepAgents
            logger.info("Adapting nanoClaw tools for DeepAgents...")
            adapted_tools = get_all_adapted_tools(confirm_callback)
            logger.info(f"Adapted {len(adapted_tools)} tools for DeepAgents")
            if adapted_tools:
                tool_names = [tool.name if hasattr(tool, 'name') else str(
                    tool) for tool in adapted_tools]
                # Log first 5 tool names
                logger.info(f"Available tools: {tool_names[:5]}...")

            # Set base URL environment variable if configured
            # This is needed for non-standard API endpoints like DeepSeek
            if self.base_url and self.provider == "openai":
                os.environ["OPENAI_BASE_URL"] = self.base_url
                logger.debug(f"Set OPENAI_BASE_URL={self.base_url}")

            # Initialize model with proper configuration
            # For non-OpenAI APIs (like DeepSeek), disable Responses API
            model = init_chat_model(
                f"{self.provider}:{self.model}",
                use_responses_api=(
                    self.provider == "openai" and not self.base_url),
                max_retries =3,
                timeout = 30,
            )

            # Get workspace directory for filesystem backend
            workspace_path = get_workspace_path()
            workspace_path.mkdir(parents=True, exist_ok=True)

            try:

                # Build environment from configuration
                config = get_config()
                shell_config = config.tools.shell

                # Start with platform defaults (includes SystemRoot on Windows)
                env_vars = get_platform_default_env()

                # Add user-configured environment variables
                if shell_config.env_vars:
                    env_vars.update(shell_config.env_vars)

                # Handle PATH appending if user provides custom PATH
                if "PATH" in shell_config.env_vars:
                    user_path = shell_config.env_vars["PATH"]
                    if sys.platform == "win32":
                        env_vars["PATH"] = f"{env_vars['PATH']};{user_path}"
                    else:
                        env_vars["PATH"] = f"{env_vars['PATH']}:{user_path}"

                logger.info(f"localShellBackend env:{env_vars}")
                shell_backend = LocalShellBackend(
                    root_dir=workspace_path,
                    virtual_mode=True,
                    inherit_env=shell_config.inherit_env,
                    env=env_vars)
                
                # 文件系统
                fs_backend = FilesystemBackend(
                    root_dir=workspace_path, virtual_mode=True)
                mem_middleware = MemoryMiddleware(
                    backend=fs_backend,
                    sources=[
                        "/AGENTS.md",
                    ],
                )

                deepagent = create_deep_agent(
                    model=model,  # Use pre-initialized model
                    backend=shell_backend,
                    # memory=memory_paths,
                    # skills=skills_paths,
                    skills=["/skills"],
                    checkpointer=InMemorySaver(),
                    middleware=[mem_middleware],
                    debug=True
                )
                logger.info(f"DeepAgents instance created successfully")
            except Exception as e:
                logger.error(f"Failed to create DeepAgents instance: {e}")
                raise RuntimeError(
                    f"DeepAgents initialization failed: {e}") from e

            try:
                # Use DeepAgents directly with built-in memory support
                logger.info("Using DeepAgents with built-in memory support...")
                self._agents[session_id] = deepagent

                logger.info(
                    f"Created DeepAgents instance for session {session_id}")
                logger.info("Agent initialization complete")
            except Exception as e:
                logger.error(
                    f"Failed to wrap DeepAgents instance with safety layer: {e}")
                raise RuntimeError(
                    f"Safety wrapper initialization failed: {e}") from e

        return self._agents[session_id]

    async def run(
        self,
        user_message: str,
        session_id: str,
        confirm_callback: Optional[Callable] = None,
    ) -> str:
        """
        Main agent loop. Process user message using DeepAgents.

        Args:
            user_message: User's message
            session_id: Session identifier
            confirm_callback: Async function for user confirmation

        Returns:
            Final response string
        """
        logger.info(f"=== New message from session {session_id} ===")
        logger.info(f"User: {user_message}")
        logger.debug(f"Message length: {len(user_message)} chars")

        import time
        start_time = time.time()

        # Extract channel_id and user_id from session_id
        channel_id, user_id = session_id.split(
            ":") if ":" in session_id else ("unknown", "unknown")

        # Log user message to JSONL
        if self.jsonl_logger:
            await self.jsonl_logger.log_user_message(
                session_id=session_id,
                channel_id=channel_id,
                user_id=user_id,
                content=user_message
            )

        try:
            # Get or create DeepAgents instance
            logger.info("Getting or creating DeepAgents instance...")

            # Log agent thinking - starting DeepAgents initialization
            if self.jsonl_logger:
                await self.jsonl_logger.log_agent_thinking(
                    session_id=session_id,
                    iteration=0,
                    thought_type=ThoughtType.REASONING,
                    content="Getting or creating DeepAgents instance"
                )

            agent = self._get_deepagent_instance(
                session_id, user_message, confirm_callback
            )
            logger.info(
                f"DeepAgents instance ready, time elapsed: {time.time() - start_time:.2f}s")

            # Execute DeepAgents
            logger.info("Preparing inputs for DeepAgents...")
            inputs = {"messages": [{"role": "user", "content": user_message}]}

            # Configure DeepAgents with thread_id for built-in memory
            # Add Langfuse callbacks for tracing if enabled
            config = {"configurable": {"thread_id": session_id}}
            if self.langfuse_callback:
                config["callbacks"] = [self.langfuse_callback]
                logger.info(f"Added Langfuse callback to config")

            logger.info(
                f"Invoking DeepAgents with {len(inputs['messages'])} messages")
            logger.info(f"Thread ID: {session_id}")
            logger.info(
                f"Starting DeepAgents invocation at {time.strftime('%H:%M:%S')}")

            # Log agent thinking - starting invocation
            if self.jsonl_logger:
                await self.jsonl_logger.log_agent_thinking(
                    session_id=session_id,
                    iteration=0,
                    thought_type=ThoughtType.REASONING,
                    content=f"Starting DeepAgents invocation with {len(inputs['messages'])} messages"
                )

            # Invoke DeepAgents (Langfuse callback already attached at creation)
            result = await agent.ainvoke(inputs, config)

            elapsed = time.time() - start_time
            logger.info(f"DeepAgents invocation completed in {elapsed:.2f}s")

            # Log agent thinking - completion
            if self.jsonl_logger:
                await self.jsonl_logger.log_agent_thinking(
                    session_id=session_id,
                    iteration=0,
                    thought_type=ThoughtType.COMPLETION,
                    content=f"DeepAgents invocation completed in {elapsed:.2f}s"
                )

            # Extract final response
            logger.info("Extracting final response from DeepAgents result...")
            final_response = self._extract_final_response(result)
            logger.info(f"Final response length: {len(final_response)} chars")

            # Log agent response to JSONL
            if self.jsonl_logger:
                await self.jsonl_logger.log_agent_response(
                    session_id=session_id,
                    content=final_response,
                    tokens_used=0,  # DeepAgents doesn't expose this
                    iterations=1,
                    tool_calls_count=0,
                    duration_ms=int(elapsed * 1000)
                )

            # Save to memory
            await self.memory.add_message(session_id, "user", user_message)
            await self.memory.add_message(session_id, "assistant", final_response)

            logger.debug(f"Final response: {final_response[:300]}...")

            # Flush JSONL logs to disk
            if self.jsonl_logger:
                await self.jsonl_logger.flush()

            return final_response

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            import traceback
            traceback.print_exc()

            # Log error to JSONL
            if self.jsonl_logger:
                await self.jsonl_logger.log_system(
                    level="ERROR",
                    component="agent",
                    message=f"Agent execution failed: {e}",
                    exception=traceback.format_exc(),
                    context={"session_id": session_id}
                )

            error_msg = f"I encountered an error processing your request: {e}"
            await self.memory.add_message(session_id, "user", user_message)
            await self.memory.add_message(session_id, "assistant", error_msg)

            # Log error response
            if self.jsonl_logger:
                await self.jsonl_logger.log_agent_response(
                    session_id=session_id,
                    content=error_msg,
                    tokens_used=0,
                    iterations=0,
                    tool_calls_count=0,
                    duration_ms=int((time.time() - start_time) * 1000)
                )

            return error_msg

    async def stream(
        self,
        user_message: str,
        session_id: str,
        confirm_callback: Optional[Callable] = None,
    ):
        """
        Stream agent output in real-time.

        Args:
            user_message: User's message
            session_id: Session identifier
            confirm_callback: Async function for user confirmation

        Yields:
            Response chunks as they arrive
        """
        logger.debug(f"=== Streaming message from session {session_id} ===")

        # Get or create DeepAgents instance
        agent = self._get_deepagent_instance(
            session_id, user_message, confirm_callback
        )

        # Stream from DeepAgents
        inputs = {"messages": [{"role": "user", "content": user_message}]}
        config = {"configurable": {"thread_id": session_id}}

        try:
            for chunk in agent.stream(inputs, config):
                yield chunk
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield f"Error: {e}"

    def _extract_final_response(self, result: dict) -> str:
        """
        Extract final text response from DeepAgents result.

        Args:
            result: DeepAgents result dict with 'messages' key

        Returns:
            Final response string
        """
        if not isinstance(result, dict):
            return str(result)

        # Check for messages array (DeepAgents returns this)
        messages = result.get("messages", [])
        if messages and isinstance(messages, list):
            last_msg = messages[-1]

            # Handle LangChain Message objects
            if hasattr(last_msg, 'content'):
                content = last_msg.content
                if isinstance(content, str):
                    return content
                # Handle list content (e.g., with tool calls)
                elif isinstance(content, list):
                    # Extract text parts
                    text_parts = [c for c in content if isinstance(c, str)]
                    return " ".join(text_parts) if text_parts else str(content)

            # Handle dict format
            elif isinstance(last_msg, dict):
                content = last_msg.get("content", "")
                if content:
                    return str(content)

        # Fallback: return string representation
        return str(result)

    async def flush(self) -> None:
        """Flush all pending telemetry data (Langfuse, JSONL logs)."""
        # Flush JSONL logs
        if self.jsonl_logger:
            await self.jsonl_logger.flush()
            logger.debug("JSONL logs flushed")

        # Flush Langfuse data
        if self.langfuse_callback:
            try:
                # Langfuse 4.x: use the client attribute
                if hasattr(self.langfuse_callback, 'client'):
                    self.langfuse_callback.client.flush()
                    logger.debug("Langfuse data flushed")
                # Fallback for older versions
                elif hasattr(self.langfuse_callback, 'langfuse'):
                    self.langfuse_callback.langfuse.flush()
                    logger.debug("Langfuse data flushed")
                elif hasattr(self.langfuse_callback, 'flush'):
                    self.langfuse_callback.flush()
                    logger.debug("Langfuse callback flushed")
            except Exception as e:
                logger.warning(f"Failed to flush Langfuse data: {e}")


# Global agent instance
_agent: Optional[Agent] = None


def get_agent() -> Agent:
    """Get the global Agent instance."""
    global _agent
    if _agent is None:
        import os

        from nanoclaw.core.config import get_config

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

        # Load pre-registered robots from config
        from nanoclaw.tools.rpa_tools import load_config_robots
        auto_registered = load_config_robots()
        if auto_registered:
            logger.info(
                f"Auto-registered robots from config: {auto_registered}")

        # Initialize JSONL logger if enabled
        jsonl_logger = None
        if config.jsonl_logging.enabled:
            from nanoclaw.core.config import get_logs_path

            log_dir = get_logs_path()
            jsonl_logger = JSONLLogger(
                log_dir=log_dir,
                config=config.jsonl_logging
            )
            # Set global JSONL logger instance
            from nanoclaw.core.jsonl_logger import set_jsonl_logger
            set_jsonl_logger(jsonl_logger)
            logger.info(f"JSONL logging enabled: {log_dir}")

        # Get model and provider configuration
        provider, api_key, model, base_url = config.get_active_provider()

        # Set API key as environment variable for LangChain/DeepAgents
        # DeepAgents uses LangChain's standard env var names
        if provider == "openai":
            os.environ["OPENAI_API_KEY"] = api_key
            if base_url:
                os.environ["OPENAI_BASE_URL"] = base_url
        elif provider == "anthropic":
            os.environ["ANTHROPIC_API_KEY"] = api_key
        elif provider == "openrouter":
            os.environ["OPENROUTER_API_KEY"] = api_key

        # Initialize Langfuse callback handler if enabled
        langfuse_callback = None
        if config.langfuse.enabled:
            if config.langfuse.public_key and config.langfuse.secret_key:
                try:
                    # Set environment variables for Langfuse auto-configuration
                    # This helps with nested LangChain calls and is required for v4.x
                    os.environ["LANGFUSE_PUBLIC_KEY"] = config.langfuse.public_key
                    os.environ["LANGFUSE_SECRET_KEY"] = config.langfuse.secret_key
                    os.environ["LANGFUSE_HOST"] = config.langfuse.host
                    if config.langfuse.release:
                        os.environ["LANGFUSE_RELEASE"] = config.langfuse.release
                    if config.langfuse.environment:
                        os.environ["LANGFUSE_ENVIRONMENT"] = config.langfuse.environment

                    # Langfuse 4.x: only public_key is passed directly,
                    # other config comes from environment variables

                    langfuse_callback = LangfuseCallbackHandler(
                        public_key=config.langfuse.public_key,
                    )
                    logger.info(
                        f"Langfuse tracing enabled: {config.langfuse.host}")
                except Exception as e:
                    logger.warning(f"Failed to initialize Langfuse: {e}")
            else:
                logger.warning(
                    "Langfuse enabled but credentials not configured")

        _agent = Agent(
            model=model,
            provider=provider,
            base_url=base_url,
            memory=get_memory_store(),
            tools=tools,
            audit=get_audit_log(),
            budget=get_session_budget(),
            prompt_guard=get_prompt_guard(),
            context_builder=ContextBuilder(),
            enable_planning=getattr(
                config.agent.deepagents, "enable_planning", True),
            enable_subagents=getattr(
                config.agent.deepagents, "enable_subagents", True),
            jsonl_logger=jsonl_logger,
            langfuse_callback=langfuse_callback,
        )
    return _agent


def set_agent(agent: Agent) -> None:
    """Set the global Agent instance."""
    global _agent
    _agent = agent
