# Capability: Skill Validation

## ADDED Requirements

### Requirement: SKILL.md Format Validation

The agent MUST validate SKILL.md files before attempting to load them.

**Rationale**: Invalid or malformed SKILL.md files should be detected early with clear error messages.

#### Scenario: Valid SKILL.md format is accepted

**Given** a workspace skill has a valid SKILL.md file
**When** SkillsMiddleware loads the skill
**Then** the skill is loaded successfully
**And** no validation errors are raised

#### Scenario: Invalid SKILL.md format is rejected

**Given** a workspace skill has a malformed SKILL.md file
**When** SkillsMiddleware attempts to load the skill
**Then** a clear error message is logged
**And** the skill is skipped
**And** other skills continue to load

#### Scenario: Missing SKILL.md is logged

**Given** a directory in skills/ doesn't have SKILL.md
**When** SkillsMiddleware scans for skills
**Then** a debug message is logged
**And** the directory is skipped

#### Scenario: SKILL.md has required frontmatter fields

**Given** a SKILL.md file exists
**When** the file is validated
**Then** it must contain frontmatter with `name` field
**And** it must contain `description` field
**And** missing required fields are logged as errors
**And** skills with missing fields are skipped

### Requirement: Skill Directory Structure Validation

The agent MUST validate that skill directories follow the expected structure.

**Rationale**: SkillsMiddleware expects specific directory structure for skills.

#### Scenario: Valid skill directory structure is accepted

**Given** a skill directory has SKILL.md in root
**And** optional scripts/ subdirectory exists
**When** the skill is validated
**Then** validation passes
**And** the skill is loaded

#### Scenario: Directory without SKILL.md is skipped

**Given** a directory exists in skills/ folder
**And** it doesn't contain SKILL.md file
**When** SkillsMiddleware scans for skills
**Then** the directory is skipped
**And** a debug message is logged

### Requirement: Security Validation

The agent MUST validate skill file permissions for security.

**Rationale**: Skills should only be loaded from files owned by the user and not writable by others.

#### Scenario: Skills with unsafe permissions are rejected

**Given** a skill file is writable by group or others
**When** the skill loader checks permissions (non-Windows)
**Then** the file is skipped
**And** a warning is logged
**And** the reason (permissions) is included in the log

#### Scenario: Skills not owned by user are rejected

**Given** a skill file is owned by a different user
**When** the skill loader checks ownership (non-Windows)
**Then** the file is skipped
**And** a warning is logged
**And** the owner mismatch is noted

#### Scenario: Windows skips permission checks

**Given** the agent is running on Windows
**When** skill files are loaded
**Then** permission checks are skipped
**And** a debug log notes this
**And** all other validation proceeds normally

### Requirement: Skill Content Validation

The agent MUST validate that SKILL.md content is well-formed.

**Rationale**: Poorly formatted SKILL.md files can cause parsing errors.

#### Scenario: SKILL.md with invalid YAML frontmatter is rejected

**Given** a SKILL.md file has malformed YAML frontmatter
**When** the file is parsed
**Then** a YAML parsing error is logged
**And** the skill is skipped
**And** other skills continue to load

#### Scenario: SKILL.md with empty description is accepted but logged

**Given** a SKILL.md file has empty description field
**When** the file is validated
**Then** the skill loads successfully
**And** a warning is logged about empty description

## MODIFIED Requirements

None.

## REMOVED Requirements

### Requirement: Python Skill Validation

**Reason**: This proposal only supports SKILL.md format skills. Python scripts with @tool decorators are handled separately by ToolRegistry and are not loaded via SkillsMiddleware.

#### Scenario: Valid @tool skills load successfully

**Removed**: @tool decorator skills are not loaded by SkillsMiddleware.

#### Scenario: Invalid Python syntax is caught

**Removed**: Python syntax validation is handled by ToolRegistry, not SkillsMiddleware.

#### Scenario: Missing dependencies are reported

**Removed**: Import validation is handled by ToolRegistry, not SkillsMiddleware.
