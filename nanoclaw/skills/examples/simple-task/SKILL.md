---
name: simple-task
description: |
  A simple example skill that demonstrates the basic SKILL.md format.
  This skill shows how to structure a skill with documentation and usage instructions.
  Use this as a template when creating your own skills.
---

# Simple Task Example Skill

## Overview

This is a simple example skill that demonstrates the basic structure of a nanoClaw SKILL.md skill. It serves as a template and learning tool for creating your own skills.

## When to Use This Skill

This example skill demonstrates:
- Basic SKILL.md file structure with frontmatter
- How to document your skill
- Directory organization for skills

**Note**: This is an example/template skill. It doesn't perform any actual operations but shows you how to structure real skills.

## Directory Structure

```
simple-task/
├── SKILL.md           # This file - contains skill documentation
└── scripts/           # Optional: Put your scripts here (Python, Bash, etc.)
```

## How to Create Your Own Skill

### Step 1: Create Skill Directory

Create a new directory in `~/.nanoclaw/workspace/skills/your-skill-name/`

### Step 2: Create SKILL.md File

Create a `SKILL.md` file with the following structure:

```markdown
---
name: your-skill-name
description: |
  Brief description of what your skill does
  and when it should be used.
---

# Your Skill Name

## Overview

Detailed description of your skill...

## When to Use This Skill

Explain when users should invoke this skill...

## How It Works

Step-by-step explanation of what the skill does...
```

### Step 3: Add Scripts (Optional)

If your skill needs scripts, create a `scripts/` directory and add your code files.

### Step 4: Test Your Skill

1. Restart nanoClaw or wait for it to reload
2. The skill will be automatically discovered
3. You can invoke it by describing what you need

## Best Practices

1. **Clear Description**: The `description` field should clearly state what the skill does
2. **When to Use**: Help users understand when to invoke your skill
3. **Step-by-Step Instructions**: Break down complex tasks into clear steps
4. **Error Handling**: Document what errors might occur and how to handle them
5. **Examples**: Provide examples of how to use the skill

## Examples of Real Skills

Look at these examples to learn more:
- **business-trip-application**: RPA skill for filling forms
- **file-organizer**: File management operations
- **web-research**: Web search and data extraction

## Common Patterns

### Pattern 1: Information Collection
If your skill needs information from the user:
1. List required information fields
2. Provide examples of valid inputs
3. Explain what happens with the information

### Pattern 2: Multi-Step Process
If your skill performs multiple steps:
1. Outline each step clearly
2. Show expected output at each step
3. Explain how to verify success

### Pattern 3: External Tools
If your skill uses external tools or APIs:
1. Document prerequisites (tools, accounts, etc.)
2. Provide configuration examples
3. Show how to test connectivity

## Troubleshooting

**Skill not loading?**
- Check that SKILL.md has valid YAML frontmatter
- Ensure the `name` and `description` fields are present
- Verify the directory is in `~/.nanoclaw/workspace/skills/`

**Skill not working as expected?**
- Review the logs for error messages
- Check that all prerequisites are met
- Verify configuration is correct

## Next Steps

- Explore other example skills
- Read the nanoClaw documentation on skills
- Create your own skill based on this template
- Test your skill thoroughly before sharing

## Resources

- nanoClaw Documentation: [link to docs]
- SKILL.md Format Reference: [link to format docs]
- Community Skills Repository: [link to examples]
