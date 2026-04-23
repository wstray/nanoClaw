# Capability: Skill Loading

## ADDED Requirements

### Requirement: Workspace Skills Directory Setup

The agent MUST automatically create and set up the workspace skills directory during initialization.

**Rationale**: SkillsMiddleware requires a properly structured workspace directory to load SKILL.md skills.

#### Scenario: Workspace skills directory is created if missing

**Given** the workspace skills directory doesn't exist
**When** the agent initializes
**Then** `~/.nanoclaw/workspace/skills/` directory is created
**And** subdirectories are created as needed
**And** proper permissions are set

### Requirement: Example Skills Installation

The agent MUST copy example SKILL.md skills to workspace on first run.

**Rationale**: Users need example skills to understand the format and get started.

#### Scenario: Example skills are copied on first agent initialization

**Given** a new agent session is starting
**When** the agent initializes DeepAgents instance
**And** no example skills exist in workspace
**Then** example skills from `nanoclaw/skills/examples/` are copied to `~/.nanoclaw/workspace/skills/examples/`
**And** the copy only happens if the destination doesn't exist (no overwrites)
**And** successful copies are logged
**And** failed copies log warnings but don't prevent agent startup

#### Scenario: Workspace skills directory is created if missing

**Given** the workspace skills directory doesn't exist
**When** the agent initializes
**Then** `~/.nanoclaw/workspace/skills/` directory is created
**And** subdirectories `builtin/` and `user/` are created
**And** proper permissions are set

### Requirement: SkillsMiddleware Configuration

The agent MUST configure SkillsMiddleware with all necessary skill sources.

**Rationale**: SkillsMiddleware needs to know where to load SKILL.md skills from.

#### Scenario: SkillsMiddleware is configured with workspace sources

**Given** an agent is initializing a DeepAgents instance
**When** creating the SkillsMiddleware instance
**Then** it is configured with sources including:
  - `~/.nanoclaw/workspace/skills/` (root directory)
  - Any subdirectories containing SKILL.md files
**And** the FilesystemBackend is properly configured with workspace root

### Requirement: Error Handling and Logging

The agent MUST handle skill loading errors gracefully without preventing agent startup.

**Rationale**: Skill loading issues should not prevent the agent from functioning; core tools should still work.

#### Scenario: Failed example skill copy is logged but doesn't fail initialization

**Given** an example skill cannot be copied (permissions, I/O error)
**When** the copy operation fails
**Then** a warning is logged with the skill name and error reason
**And** agent initialization continues
**And** other skills are still copied

#### Scenario: Missing example skills directory is handled gracefully

**Given** the example skills directory doesn't exist
**When** the agent tries to copy skills
**Then** a debug message is logged
**And** no error is raised
**And** agent initialization continues normally

#### Scenario: Skill loading errors are logged with context

**Given** SkillsMiddleware fails to load a SKILL.md skill
**When** the error occurs
**Then** the error is logged with:
  - Skill name/path
  - Error type and message
  - Stack trace for debugging
**And** other skills continue to load

## MODIFIED Requirements

### Requirement: Agent Initialization Process

The agent initialization MUST include workspace setup and SkillsMiddleware configuration steps.

**Rationale**: SKILL.md skills need to be available when DeepAgents is created.

#### Scenario: Agent initialization includes skill setup

**Given** a new Agent instance is created
**When** `_get_deepagent_instance` is called
**Then** workspace directories are created/validated
**And** example skills are copied to workspace (if needed)
**And** SkillsMiddleware is configured with all skill sources
**And** DeepAgents instance is created with middleware

## REMOVED Requirements

None.
