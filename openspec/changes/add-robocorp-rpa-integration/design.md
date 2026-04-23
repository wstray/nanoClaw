## Context

Robocorp is a popular open-source RPA (Robotic Process Automation) platform that allows users to automate repetitive tasks using Python. The RCC (Robocorp Control Center) CLI tool is used to run robots defined in `robot.yaml` files.

Current state: There is a `robocorp.py` skill in `nanoclaw/skills/` that implements basic robocorp functionality, but:
1. It's in the skills folder which is being deprecated for DeepAgents
2. It's not integrated as a core tool
3. The `rpa_tools.py` file in `nanoclaw/tools/` is empty

## Goals

1. Provide seamless RPA robot execution from nanoClaw agent conversations
2. Support robot registration, listing, execution, and management
3. Enable passing variables and selecting tasks for multi-task robots
4. Parse and return structured robot output

## Non-Goals

1. Creating/managing robot.yaml files (user responsibility)
2. Robot development environment setup
3. Robot publishing to Robocorp Cloud
4. Advanced RCC features (credentials, work items, etc.) - can be added later

## Decisions

### Decision: Move from Skills to Core Tools
**Choice**: Move robocorp functionality from `nanoclaw/skills/robocorp.py` to `nanoclaw/tools/rpa_tools.py`

**Rationale**:
- Skills folder is being deprecated for DeepAgents integration
- Core tools have better integration with ToolRegistry
- RPA is a fundamental capability like shell_exec and file_read
- Consistent with existing tool architecture

**Alternatives considered**:
- Keep as skill: Rejected due to deprecation of skills folder
- Create SKILL.md wrapper: Rejected as unnecessary abstraction

### Decision: Use RCC CLI (not Robocorp Cloud API)
**Choice**: Execute robots via local RCC CLI rather than Robocorp Cloud API

**Rationale**:
- Works offline without cloud dependency
- No API keys required
- Consistent with nanoClaw's local-first philosophy
- Simpler implementation

**Alternatives considered**:
- Robocorp Cloud API: Requires internet, API keys, more complex auth

### Decision: JSON Registry File
**Choice**: Store robot registry in `~/.nanoclaw/robots.json`

**Rationale**:
- Simple, human-readable format
- Easy to backup and version control
- No database dependencies
- Matches existing pattern in old implementation

### Decision: Async Subprocess Execution
**Choice**: Use `asyncio.create_subprocess_exec` for robot execution

**Rationale**:
- Non-blocking I/O for agent responsiveness
- Timeout support for long-running robots
- Proper stdout/stderr capture

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| RCC not installed | High | Clear error message with install instructions |
| Robot execution timeout | Medium | Configurable timeout, clear timeout error |
| Large robot output | Low | Truncate output, refer to log files |
| Robot registry corruption | Low | JSON validation, backup on write |

## Migration Plan

1. New RPA tools will have names: `rpa_register`, `rpa_list`, `rpa_run`, `rpa_unregister`
2. Old skill tools (`robocorp_*`) will log deprecation warnings
3. Robot registry format remains compatible (same JSON structure)
4. Users can migrate by using new tool names (functionality identical)

## Open Questions

1. Should we support robot output streaming (real-time progress)?
   - **Decision**: No for initial implementation. Return complete output.
2. Should we cache robot execution results?
   - **Decision**: No. RPA runs can have side effects, always execute fresh.
3. Should we validate robot.yaml syntax before execution?
   - **Decision**: No. RCC will handle validation with clear errors.
