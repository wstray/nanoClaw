## 1. Configuration

- [x] 1.1 Add `RobocorpConfig` class to `nanoclaw/core/config.py`
  - `rcc_path`: Path to RCC executable (optional, auto-detect if not set)
  - `default_timeout`: Default robot execution timeout (default: 300s)
  - `robots_file`: Path to robot registry JSON file
- [x] 1.2 Add robocorp section to `ToolsConfig`

## 2. Core RPA Tools Implementation

- [x] 2.1 Implement `rpa_register` tool
  - Register robot by name with path to robot.yaml directory
  - Persist to JSON registry file
  - Validate robot.yaml exists
- [x] 2.2 Implement `rpa_list` tool
  - List all registered robots with status (exists/missing)
  - Show robot metadata if available
- [x] 2.3 Implement `rpa_run` tool
  - Execute robot by name using RCC CLI
  - Support task parameter for multi-task robots
  - Support variables parameter (JSON) for input variables
  - Parse output.json for structured results
  - Handle timeout and error cases
  - Return formatted execution report
- [x] 2.4 Implement `rpa_unregister` tool
  - Remove robot from registry

## 3. Integration

- [x] 3.1 Add `nanoclaw.tools.rpa_tools` to `_CORE_TOOL_MODULES` in registry
- [x] 3.2 Add RPA tool names to `_CORE_TOOL_NAMES` set
- [x] 3.3 Mark `nanoclaw/skills/robocorp.py` as deprecated with warning log

## 4. Testing

- [x] 4.1 Write tests for `rpa_register` (mock filesystem)
- [x] 4.2 Write tests for `rpa_list` (mock registry)
- [x] 4.3 Write tests for `rpa_run` (mock subprocess)
- [x] 4.4 Write tests for `rpa_unregister`
- [x] 4.5 Write integration test for full workflow

## 5. Documentation

- [x] 5.1 Add RPA setup instructions to README (see design.md)
- [x] 5.2 Document RCC installation requirements (see design.md)
- [x] 5.3 Provide example robot.yaml structure (see design.md)
- [x] 5.4 Add configuration examples to config.example.json
