# Proposal: Enhance SkillsMiddleware Integration

## Summary

Improve the integration and usage of `SkillsMiddleware` in `nanoclaw/core/agent.py` to properly support SKILL.md format skills with robust error handling and clear architecture.

## Motivation

### Current Issues
1. **Incomplete Integration**: SkillsMiddleware is only configured to load from workspace skills directory, needs to support both user and built-in SKILL.md skills
2. **No Built-in SKILL.md Skills**: Built-in Python skills (`@tool` decorator) are not compatible with SkillsMiddleware which expects SKILL.md format
3. **Commented Implementation**: Lines 138-150 in agent.py contain incomplete code for copying built-in skills to workspace
4. **No Error Handling**: Missing validation and error handling for skill loading failures
5. **Unclear Architecture**: No clear documentation on how SKILL.md skills should be created and loaded

### Impact
- Users must manually create SKILL.md skills in workspace directory
- No built-in example skills to reference
- Skill loading failures are silent or unclear
- Difficult to maintain and extend the skill system

## Proposed Solution

### Phase 1: Stabilization
1. Complete the workspace skills directory setup
2. Add proper error handling and logging for skill loading
3. Validate SKILL.md format compatibility

### Phase 2: Built-in Example Skills
1. Create example SKILL.md skills in `nanoclaw/skills/` directory
2. Copy example skills to workspace on first run
3. Provide templates for common skill patterns

### Phase 3: Enhanced Integration
1. Add skill hot-reloading for development
2. Implement skill validation and testing
3. Add comprehensive logging and debugging support

## Alternatives Considered

### Option A: Support Both SKILL.md and Python Skills
**Pros**: Flexible, supports existing Python skills
**Cons**:
- Complex architecture with dual systems
- Confusing for users (which format to use?)
- Maintenance burden of two systems

### Option B: SKILL.md Only (Chosen)
**Pros**:
- Simple, unified format
- Clear separation between tools and skills
- Better documentation and examples
- Aligned with DeepAgents architecture
**Cons**:
- Existing Python skills need to be converted to SKILL.md
- New format to learn for users

## Dependencies

- DeepAgents framework (already integrated)
- Workspace directory structure (already exists)
- Existing core tools via ToolRegistry (separate from skills)

## Risks

- **Low**: Breaking existing functionality - Python skills in `nanoclaw/skills/` will no longer be loaded
- **Low**: Performance impact from skill loading overhead
- **Low**: Users need to learn new SKILL.md format

## Mitigation

- Python skills in `nanoclaw/skills/` are deprecated (already not working with DeepAgents)
- Provide example SKILL.md skills as templates
- Create migration guide for converting Python skills to SKILL.md
- Extensive logging for debugging skill loading issues

## Success Criteria

1. Example SKILL.md skills are provided and copied to workspace
2. Workspace skills load correctly via SkillsMiddleware
3. Clear error messages when skill loading fails
4. Documentation explains how to create SKILL.md skills
5. Existing Python skills in `nanoclaw/skills/` are documented as deprecated

## Out of Scope

- Converting existing Python skills to SKILL.md format (users can do this)
- Skill marketplace or distribution system
- Skill versioning and dependency management
- Backward compatibility with `@tool` decorator skills (use ToolRegistry for tools)
