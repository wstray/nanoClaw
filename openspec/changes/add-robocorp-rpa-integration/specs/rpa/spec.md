## ADDED Requirements

### Requirement: Robot Registration
Users SHALL be able to register Robocorp robots with a name for later execution.

#### Scenario: Register a valid robot
- **GIVEN** a directory containing a valid `robot.yaml` file
- **WHEN** the user calls `rpa_register` with name "invoice-bot" and the directory path
- **THEN** the robot is registered and persisted to the registry
- **AND** a success message is returned

#### Scenario: Register invalid path
- **GIVEN** a path that does not exist or lacks robot.yaml
- **WHEN** the user attempts to register it
- **THEN** an error message is returned indicating the path is invalid

### Requirement: Robot Listing
Users SHALL be able to list all registered robots with their current status.

#### Scenario: List registered robots
- **GIVEN** robots are registered in the system
- **WHEN** the user calls `rpa_list`
- **THEN** a list of robot names, paths, and existence status is returned

#### Scenario: List empty registry
- **GIVEN** no robots are registered
- **WHEN** the user calls `rpa_list`
- **THEN** a message indicating no robots are registered is returned

### Requirement: Robot Execution
Users SHALL be able to execute registered robots by name with optional parameters.

#### Scenario: Execute robot with default task
- **GIVEN** a registered robot "scraper"
- **WHEN** the user calls `rpa_run` with name "scraper"
- **THEN** the robot executes via RCC
- **AND** the exit code, output, and any results are returned

#### Scenario: Execute robot with specific task
- **GIVEN** a robot with multiple tasks defined
- **WHEN** the user calls `rpa_run` with name and task parameter
- **THEN** only the specified task is executed

#### Scenario: Execute robot with variables
- **GIVEN** a robot accepting input variables
- **WHEN** the user calls `rpa_run` with variables JSON
- **THEN** the variables are passed to the robot
- **AND** the robot executes with those inputs

#### Scenario: Handle missing robot
- **GIVEN** a robot name not in registry
- **WHEN** the user attempts to run it
- **THEN** an error message lists available robots

#### Scenario: Handle RCC not installed
- **GIVEN** RCC CLI is not available
- **WHEN** the user attempts to run a robot
- **THEN** an error message provides installation instructions

#### Scenario: Handle robot timeout
- **GIVEN** a robot running longer than configured timeout
- **WHEN** execution exceeds timeout
- **THEN** the process is terminated
- **AND** a timeout error is returned

### Requirement: Robot Unregistration
Users SHALL be able to remove robots from the registry.

#### Scenario: Unregister existing robot
- **GIVEN** a registered robot "old-bot"
- **WHEN** the user calls `rpa_unregister` with name "old-bot"
- **THEN** the robot is removed from registry
- **AND** a success message is returned

#### Scenario: Unregister non-existent robot
- **GIVEN** a robot name not in registry
- **WHEN** the user attempts to unregister it
- **THEN** an informative message is returned

### Requirement: Output Parsing
The system SHALL parse and return robot execution results.

#### Scenario: Parse JSON output
- **GIVEN** a robot generates `output/output.json`
- **WHEN** execution completes
- **THEN** the JSON content is included in the response

#### Scenario: Parse text output
- **GIVEN** a robot produces stdout/stderr
- **WHEN** execution completes
- **THEN** both streams are captured and returned

### Requirement: Configuration
The system SHALL support configurable RPA settings.

#### Scenario: Configure RCC path
- **GIVEN** RCC is installed in non-standard location
- **WHEN** user sets `rcc_path` in config
- **THEN** the specified path is used for RCC execution

#### Scenario: Configure timeout
- **GIVEN** robots need longer execution time
- **WHEN** user sets `default_timeout` in config
- **THEN** the timeout is applied to robot executions
