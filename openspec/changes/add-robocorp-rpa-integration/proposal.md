# Proposal: Add Robocorp RPA Integration

## Why

Enable nanoClaw agents to execute Robocorp RPA robots for automating business processes, web scraping, and repetitive tasks. This integration allows users to:
- Register and manage RPA robots by name
- Execute robots with custom variables and tasks
- Retrieve robot execution results and output
- Integrate RPA capabilities into conversational workflows

## What Changes

- **Add** `rpa_run` tool to core tools for executing Robocorp robots
- **Add** `rpa_list` tool to list registered robots
- **Add** `rpa_register` tool to register robot paths
- **Add** Robocorp configuration section to config (`rcc_path`, `default_timeout`)
- **Move** robocorp functionality from `nanoclaw/skills/robocorp.py` (deprecated) to `nanoclaw/tools/rpa_tools.py`
- **Add** RCC CLI detection and validation
- **Add** robot output parsing (JSON and text)

## Impact

- **Affected specs**: New `rpa` capability
- **Affected code**:
  - `nanoclaw/tools/rpa_tools.py` - New RPA tool implementations
  - `nanoclaw/core/config.py` - Add RobocorpConfig
  - `nanoclaw/tools/registry.py` - Register RPA tools in core modules
  - `nanoclaw/skills/robocorp.py` - **DEPRECATED** (mark as legacy)
- **Dependencies**: Requires `rcc` CLI tool installed (Robocorp Control Center)
