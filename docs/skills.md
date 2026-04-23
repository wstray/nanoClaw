# Skills Documentation

## Overview

Skills in nanoClaw are complex, multi-file capabilities that extend the agent's functionality. Unlike simple tools (which are single functions), skills are self-contained packages that can include documentation, scripts, and resources.

## Tools vs Skills

### Tools (ToolRegistry)
- **Format**: Python functions with `@tool` decorator
- **Purpose**: Simple, atomic operations
- **Examples**: `shell_exec`, `file_read`, `web_search`
- **Location**: `nanoclaw/tools/` or `~/.nanoclaw/skills/`
- **Use for**: Quick operations that don't need complex logic

### Skills (SkillsMiddleware)
- **Format**: Directory with `SKILL.md` file
- **Purpose**: Complex, multi-step workflows
- **Examples**: RPA automation, research tasks, file organization
- **Location**: `~/.nanoclaw/workspace/skills/`
- **Use for**: Complex workflows that benefit from documentation and structure

## SKILL.md Format

### Required Structure

Every skill must have a `SKILL.md` file in its root directory with the following structure:

```markdown
---
name: skill-name
description: |
  A brief description of what this skill does
  and when it should be used.
---

# Skill Name

## Overview

Detailed description of the skill...

## When to Use This Skill

Explain when users should invoke this skill...

## How It Works

Step-by-step explanation...
```

### Frontmatter Fields

The YAML frontmatter (between `---` markers) must include:

#### `name` (required)
- The unique identifier for this skill
- Must be a valid directory name (no spaces, special characters)
- Use lowercase with hyphens: `my-skill`, `file-organizer`
- **Example**: `name: business-trip-application`

#### `description` (required)
- Brief description of what the skill does
- Multi-line descriptions use `|` prefix
- Should explain when to use the skill
- **Example**:
  ```yaml
  description: |
    File organization skill that helps sort, categorize,
    and organize files in the workspace.
  ```

### Optional Frontmatter Fields

You can add additional fields to the frontmatter:

```yaml
---
name: my-skill
description: |
  Description of the skill
version: "1.0"
author: Your Name
tags: [category1, category2]
requires:
  - python-package-1
  - external-tool
---
```

## Directory Structure

### Basic Skill

```
my-skill/
└── SKILL.md           # Required: Skill documentation
```

### Skill with Scripts

```
my-skill/
├── SKILL.md           # Required: Skill documentation
└── scripts/           # Optional: Your code files
    ├── main.py
    ├── helper.sh
    └── config.json
```

### Complex Skill

```
my-skill/
├── SKILL.md           # Required: Skill documentation
├── scripts/           # Optional: Code and automation
│   ├── main.py
│   ├── setup.sh
│   └── config.yaml
├── references/        # Optional: Reference materials
│   ├── example1.md
│   └── template.txt
└── output/            # Optional: Generated output (created at runtime)
    ├── results.json
    └── logs/
```

## Creating a New Skill

### Step 1: Create Skill Directory

```bash
mkdir -p ~/.nanoclaw/workspace/skills/my-skill
cd ~/.nanoclaw/workspace/skills/my-skill
```

### Step 2: Create SKILL.md

Create a `SKILL.md` file:

```markdown
---
name: my-skill
description: |
  Description of what this skill does
  and when to use it.
---

# My Skill

## Overview

Detailed description...

## When to Use This Skill

Use this skill when...

## How It Works

Step-by-step instructions...
```

### Step 3: Add Scripts (Optional)

If your skill needs code:

```bash
mkdir scripts
# Add your scripts here
```

### Step 4: Test

Restart nanoClaw or wait for skill reload. The skill will be automatically discovered.

## Best Practices

### 1. Clear Documentation

- **Description**: Be specific about what the skill does
- **When to Use**: Help users understand when to invoke your skill
- **Examples**: Provide concrete usage examples
- **Troubleshooting**: Document common issues

### 2. Structured Content

Organize your `SKILL.md` with clear sections:

```markdown
## Overview
## When to Use This Skill
## Prerequisites
## How It Works
## Usage Examples
## Troubleshooting
```

### 3. Step-by-Step Instructions

Break complex workflows into clear steps:

```markdown
## How It Works

### Step 1: Information Collection
Describe what information is needed...

### Step 2: Processing
Explain what happens with the information...

### Step 3: Output
Show what the skill produces...
```

### 4. Error Handling

Document potential errors and solutions:

```markdown
## Troubleshooting

### Issue: "Error message"
**Cause**: Why it happens
**Solution**: How to fix it
```

## Common Patterns

### Pattern 1: Information Collection

Skills that need user input:

```markdown
## Required Information

This skill needs the following information:

| Field | Description | Example |
|-------|-------------|---------|
| Name  | Field name | Example value |
```

### Pattern 2: Multi-Step Process

Skills with multiple steps:

```markdown
## Process

1. **Step One**: Description
2. **Step Two**: Description
3. **Step Three**: Description
```

### Pattern 3: External Tools

Skills that use external tools:

```markdown
## Prerequisites

- Tool 1: [link]
- Tool 2: [link]
- Configuration: steps

## Verification

Run this command to verify setup:
```bash
command --version
```
```

## Validation

### Required Fields

A valid `SKILL.md` must have:
- `name` field in frontmatter
- `description` field in frontmatter
- Valid YAML syntax in frontmatter

### Common Validation Errors

#### Error: Missing Required Field

```
Error: Missing required field 'name'
```

**Solution**: Add the `name` field to frontmatter

#### Error: Invalid YAML

```
Error: Invalid YAML in frontmatter
```

**Solution**: Check YAML syntax:
- Use spaces, not tabs
- Ensure proper indentation
- Escape special characters if needed

#### Error: Skill Not Loading

Skill directory exists but isn't loaded.

**Possible causes**:
- `SKILL.md` file missing
- Invalid frontmatter syntax
- Directory not in workspace

**Solution**:
- Verify `SKILL.md` exists
- Check YAML syntax
- Ensure directory is in `~/.nanoclaw/workspace/skills/`

## Examples

### Example 1: Simple Skill

```markdown
---
name: hello-world
description: |
  A simple skill that greets the user.
  Demonstrates basic SKILL.md structure.
---

# Hello World

## Overview

This skill demonstrates the basic structure of a nanoClaw skill.

## When to Use This Skill

Use this to learn how to create your own skills.

## How It Works

1. User invokes the skill
2. Skill displays a greeting
3. Done!
```

### Example 2: File Processing

```markdown
---
name: process-files
description: |
  Processes files in the workspace directory.
  Use when you need to batch process multiple files.
---

# File Processor

## Overview

Batch process files with various operations.

## When to Use This Skill

Use when you need to:
- Convert multiple files
- Apply transformations to files
- Batch rename files

## Prerequisites

- Files in workspace directory
- Required file permissions

## How It Works

1. Scan workspace for files
2. Apply operation to each file
3. Log results
4. Report summary
```

### Example 3: Web Research

```markdown
---
name: web-research
description: |
  Performs web research on a given topic.
  Use when you need to gather information from the web.
---

# Web Researcher

## Overview

Research skills that search, analyze, and summarize web content.

## When to Use This Skill

Use when you need to:
- Research a topic
- Find current information
- Compare sources
- Summarize findings

## How It Works

1. Accept research topic
2. Search for relevant sources
3. Analyze and extract information
4. Synthesize findings
5. Provide summary with sources
```

## Testing Your Skill

### Manual Testing

1. Create your skill in `~/.nanoclaw/workspace/skills/my-skill/`
2. Create `SKILL.md` with proper frontmatter
3. Restart nanoClaw
4. Check logs for loading confirmation
5. Test the skill by asking nanoClaw to use it

### Validation Checklist

- [ ] `SKILL.md` exists in skill directory
- [ ] Frontmatter has `name` field
- [ ] Frontmatter has `description` field
- [ ] YAML syntax is valid
- [ ] Skill appears in nanoClaw logs
- [ ] Skill can be invoked
- [ ] Documentation is clear
- [ ] Examples are provided

## Troubleshooting

### Skill Not Appearing

**Symptoms**: Skill doesn't load, not in logs

**Check**:
1. Directory is in `~/.nanoclaw/workspace/skills/`
2. `SKILL.md` file exists
3. YAML frontmatter is valid
4. `name` and `description` fields present

### Skill Loads But Doesn't Work

**Symptoms**: Skill appears in logs but doesn't function

**Check**:
1. Review error logs
2. Verify prerequisites are met
3. Check documentation for missing steps
4. Test scripts independently

### Permission Errors

**Symptoms**: Can't create files or directories

**Solution**:
- Check workspace directory permissions
- Ensure nanoClaw has write access
- Run with appropriate user permissions

## Advanced Topics

### Skill Configuration

You can add configuration to your skill:

```yaml
---
name: my-skill
description: |
  Description of the skill
config:
  option1: value1
  option2: value2
---
```

### Dependencies

Document required dependencies:

```yaml
---
name: my-skill
description: |
  Description of the skill
requires:
  - python-package-name>=1.0
  - external-tool
  - Another skill
---
```

### Skill Composition

Skills can reference other skills:

```markdown
## Related Skills

This skill works well with:
- **file-organizer**: For organizing results
- **web-research**: For gathering data
```

## Migration from Python Skills

If you have existing Python skills using `@tool` decorator:

1. **Create SKILL.md**: Add documentation
2. **Move Scripts**: Put Python code in `scripts/`
3. **Update**: Add frontmatter to SKILL.md
4. **Test**: Verify functionality

### Example Migration

**Before** (Python tool):
```python
@tool(
    name="my_tool",
    description="Does something",
    parameters={"arg": {"type": "string"}}
)
async def my_tool(arg: str) -> str:
    return result
```

**After** (SKILL.md skill):
```markdown
---
name: my-tool
description: |
  Does something
---

# My Tool

## How to Use

Simply ask: "Please do something with X"
```

With `scripts/main.py`:
```python
# Implementation here
```

## Resources

### Example Skills

Look at these examples to learn more:
- **simple-task**: Basic structure
- **file-organizer**: File operations
- **business-trip-application**: RPA automation

### Documentation

- nanoClaw Documentation: [link]
- DeepAgents Documentation: [link]
- SKILL.md Reference: [link]

### Community

- nanoClaw Discord: [link]
- Example Skills Repository: [link]
- Issue Tracker: [link]

## FAQ

### Q: Can I use Python in skills?

**A**: Yes! Put Python scripts in the `scripts/` directory.

### Q: Do I need to write code?

**A**: No. Many skills work with just documentation. The AI agent follows the instructions in SKILL.md.

### Q: Can skills use other skills?

**A**: Yes. Skills can reference and use other skills.

### Q: How do I share my skill?

**A**: Share the skill directory. Others can place it in their workspace.

### Q: Can I version control skills?

**A**: Yes. Skills are just directories with markdown files. Use git or any VCS.

### Q: What if my skill needs a database?

**A**: Document the requirement in SKILL.md. Skills can use any resource available to nanoClaw.

### Q: Can skills have user interfaces?

**A**: Skills can create files, logs, or output that other tools can display.

## Changelog

### Version 1.0
- Initial SKILL.md format specification
- Basic frontmatter requirements
- Directory structure conventions
