# Design: Enhanced SkillsMiddleware Integration

## Architecture Overview

### Current State

The current implementation has two separate systems:

1. **Tool Registry System** (`nanoclaw/tools/registry.py`):
   - Uses `@tool` decorator
   - Loads Python files with decorated functions
   - Provides security validation (ownership, permissions)
   - Used for core tools (shell, files, web, memory)
   - Simple, single-function capabilities

2. **SkillsMiddleware System** (DeepAgents):
   - Uses SKILL.md + directory structure
   - Loads from workspace `~/.nanoclaw/workspace/skills/`
   - Provides filesystem-based skill management
   - Used by DeepAgents agent for complex capabilities
   - Multi-file, documented skills

### Problem

The DeepAgents agent (`nanoclaw/core/agent.py`) configures SkillsMiddleware but:
- No example SKILL.md skills are provided
- No clear documentation on how to create SKILL.md skills
- Minimal error handling for skill loading failures
- Unclear distinction between tools and skills
- Python skills in `nanoclaw/skills/` don't work with SkillsMiddleware (different format)

### Solution

**Key Decision**: Only support SKILL.md format for SkillsMiddleware.

**Rationale**:
- SKILL.md is the native format expected by DeepAgents
- Provides clear separation: tools = simple functions, skills = complex capabilities
- SKILL.md includes self-documentation and metadata
- Better for complex, multi-step workflows (e.g., RPA)
- Simplifies architecture by avoiding dual-format support

**Note**: Python skills in `nanoclaw/skills/` using @tool decorator are not loaded by SkillsMiddleware. They may still be used by other parts of the system but are deprecated for DeepAgents use.

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Initialization                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  1. Setup Workspace Directories       │
        │     - ~/.nanoclaw/workspace/skills/   │
        │     - Create if missing               │
        └───────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  2. Copy Example Skills              │
        │     - nanoclaw/skills/examples/ →     │
        │       workspace/skills/examples/      │
        │     - Only if not exists              │
        │     - Log failures, continue          │
        └───────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  3. Configure SkillsMiddleware        │
        │     - Sources: workspace/skills/      │
        │     - FilesystemBackend               │
        │     - Auto-discover SKILL.md dirs     │
        └───────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  4. Load Core Tools                   │
        │     - Via ToolRegistry                │
        │     - Shell, files, web, memory       │
        │     - Separate from skills            │
        └───────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  5. Create DeepAgents Instance        │
        │     - With configured middleware      │
        │     - Core tools available            │
        │     - SKILL.md skills loaded          │
        └───────────────────────────────────────┘
```

## Tool vs Skill Separation

**Tools (ToolRegistry)**
- Simple, single-function capabilities
- Python functions with @tool decorator
- Registered globally and available everywhere
- Examples: `shell_exec`, `file_read`, `web_search`
- Fast, lightweight, no dependencies

**Skills (SkillsMiddleware)**
- Complex, multi-step workflows
- SKILL.md format with documentation
- Directory-based with optional scripts
- Examples: RPA workflows, research tasks
- Self-contained, documented capabilities

**Why Separate?**
- Clear separation of concerns
- Tools for atomic operations
- Skills for complex workflows
- Different use cases need different formats
- Simpler architecture than unified system

## Key Design Decisions

### 1. Maintain Dual Systems

**Decision**: Keep both ToolRegistry and SkillsMiddleware systems.

**Rationale**:
- **Backward Compatibility**: Existing built-in skills use @tool decorator
- **Use Case Differences**:
  - @tool: Simple, single-function skills (github, weather, news)
  - SkillsMiddleware: Complex, multi-file skills (RPA workflows)
- **Migration Path**: Allows gradual migration of skills to new format
- **Flexibility**: Users can choose the format that fits their skill

**Trade-offs**:
- **Pro**: No breaking changes, supports both use cases
- **Con**: More complex architecture, two systems to maintain

## Key Design Decisions

### 1. SKILL.md Only for SkillsMiddleware

**Decision**: Only support SKILL.md format skills, not Python @tool skills.

**Rationale**:
- **Native Format**: SKILL.md is what DeepAgents/SkillsMiddleware expects
- **Self-Documenting**: Skills include their own documentation
- **Better for Complex Workflows**: RPA, multi-step processes benefit from structure
- **Clear Separation**: Tools = simple functions, Skills = complex capabilities
- **Simpler Architecture**: One format for skills, one for tools

**Trade-offs**:
- **Pro**: Clear, consistent format for all skills
- **Pro**: Skills include documentation and examples inline
- **Pro**: Better for complex, multi-file capabilities
- **Con**: Python skills in nanoclaw/skills/ don't work (different format)
- **Mitigation**: Provide example skills and migration guide

### 2. Provide Example Skills

**Decision**: Include example SKILL.md skills in `nanoclaw/skills/examples/` and copy to workspace on first run.

**Rationale**:
- **Learning**: Users need examples to understand the format
- **Templates**: Examples serve as templates for new skills
- **Validation**: Examples demonstrate best practices
- **Quick Start**: Users can see skills working immediately

### 3. Graceful Degradation

**Decision**: Skill loading failures should not prevent agent startup.

**Rationale**:
- Core tools (shell, files, web) are more critical than skills
- A single bad skill shouldn't break the entire agent
- Users can still use the agent while debugging skill issues

**Trade-offs**:
- **Pro**: Agent remains functional even with skill issues
- **Pro**: Easier to debug individual skill problems
- **Con**: Silent failures might go unnoticed
- **Mitigation**: Comprehensive logging with clear error messages

### 4. Load Order

**Decision**: Load in order: core tools → built-in skills → workspace skills.

**Rationale**:
- Core tools are dependencies for other skills
- Built-in skills provide base functionality
- Workspace skills can override built-in skills if needed

**Implementation**:
```python
# 1. Core tools (already loaded by get_tool_registry)
# 2. Built-in skills
tools.load_skills(str(builtin_skills))
# 3. User skills
tools.load_skills(str(user_skills))
# 4. Workspace skills via SkillsMiddleware
```

## Integration Points

### ToolRegistry Integration

**Current State**: Core tools are loaded via ToolRegistry and adapted for DeepAgents
**Changes Needed**: None - this works correctly
**Note**: ToolRegistry handles tools, SkillsMiddleware handles skills

### SkillsMiddleware Configuration

**Current State**: Configured with workspace root
**Changes Needed**: Ensure proper sources configuration
**Implementation**: Explicitly configure workspace/skills/ as source

### Example Skills Copying

**Current State**: Commented-out code exists (lines 138-150) for copying Python skills
**Changes Needed**: Adapt to copy example SKILL.md skills instead
**Implementation**: New logic to copy from nanoclaw/skills/examples/

## Security Considerations

### 1. Skill File Validation

Both systems should validate:
- File ownership (on Unix)
- File permissions (not writable by group/others)
- Python syntax before importing
- SKILL.md format validity

### 2. Sandboxing

- Skills run in workspace directory (isolated)
- ShellToolMiddleware provides command execution guard
- FileGuard limits file access to workspace
- Skills should validate their own inputs

### 3. Audit Logging

- All skill loads should be logged
- Failed skill validation should be audited
- Skill execution should be traceable

## Performance Considerations

### 1. Startup Time

**Current**: Fast (no skill copying)
**Proposed**: Slower (copy + validation), but acceptable
- Skill copying: ~10-50ms for typical skills
- Skill validation: ~5-20ms per skill
- Total impact: <100ms for 5-10 skills

### 2. Memory Usage

**Impact**: Minimal
- Skills are lazy-loaded
- Only loaded skills consume memory
- No significant increase over current state

### 3. Runtime Performance

**Impact**: None
- Skills are cached after first load
- No performance difference once loaded
- Tool call overhead unchanged

## Testing Strategy

### 1. Unit Tests

- Test skill copying with various scenarios
- Test skill validation with valid/invalid files
- Test error handling for each failure mode
- Test load order and overrides

### 2. Integration Tests

- Test full agent initialization with both skill types
- Test that @tool skills are available to DeepAgents
- Test that workspace skills load correctly
- Test error recovery from skill failures

### 3. Manual Tests

- Create test skills in both formats
- Verify they appear in agent's tool list
- Test that they can be called successfully
- Test error messages for invalid skills

## Migration Path

### Phase 1: Foundation (This Change)
- Complete workspace directory setup
- Provide example SKILL.md skills
- Add error handling and logging for skill loading
- Validate SKILL.md format

### Phase 2: Enhanced Support (Future)
- Add skill hot-reloading for development
- Add skill testing framework
- Add more example skills
- Improve SKILL.md validation

### Not In Scope
- Converting Python skills to SKILL.md (users can do this if needed)
- Supporting Python @tool skills in SkillsMiddleware
- Unified tool/skill system (the separation is intentional)

## Rollout Plan

1. **Implement**: Add changes to agent.py
2. **Test**: Comprehensive testing of skill loading
3. **Document**: Update documentation with new architecture
4. **Monitor**: Watch for skill loading issues in logs
5. **Iterate**: Fix issues and refine based on feedback

## Monitoring and Observability

### Key Metrics
- Skill loading success rate
- Skill loading time
- Number of skills loaded per session
- Skill validation failure rate

### Logging Levels
- **DEBUG**: Normal skill loading operations
- **INFO**: Successful skill loads
- **WARNING**: Failed skill loads (non-critical)
- **ERROR**: Critical failures that prevent skill loading

### Log Examples

```
[DEBUG] Creating workspace skills directory: ~/.nanoclaw/workspace/skills/
[INFO] Copying example skills from nanoclaw/skills/examples/
[INFO] Copied example skill: simple-task
[INFO] Copied example skill: file-organizer
[DEBUG] SkillsMiddleware configured with source: workspace/skills/
[INFO] Loaded skill: simple-task (from workspace/skills/examples/simple-task/)
[INFO] Loaded skill: business-trip-application (from workspace/skills/business-trip-application/)
[INFO] DeepAgents instance created with 10 tools and 2 skills
```

## Future Considerations

### 1. More Example Skills
- Web research skill
- Data analysis skill
- Report generation skill
- API integration skill

### 2. Skill Development Tools
- Skill scaffolding CLI (create new skill from template)
- SKILL.md validation tool
- Skill testing framework
- Skill documentation generator

### 3. Performance Optimization
- Parallel skill loading
- Skill caching across sessions
- Lazy loading for large skill sets

## Example SKILL.md Structure

```markdown
---
name: my-skill
description: |
  A brief description of what this skill does
  and when it should be used.
---

# My Skill

## Overview

Detailed description of the skill...

## Usage

When to use this skill...

## Directory Structure

```
my-skill/
├── SKILL.md           # This file
├── scripts/           # Optional scripts or code
│   └── main.py
└── output/            # Optional output directory
```

## How It Works

Step-by-step explanation...
```
