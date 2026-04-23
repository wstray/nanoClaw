# Skill Creation Guide

This guide will walk you through creating your first nanoClaw skill step by step.

## What You'll Create

By the end of this guide, you'll have a working skill that:
- Has proper SKILL.md format
- Includes clear documentation
- Can be invoked by nanoClaw
- Follows best practices

## Prerequisites

- nanoClaw installed and running
- Basic understanding of Markdown
- Text editor (VS Code, Notepad++, etc.)
- 10-15 minutes

## Step 1: Plan Your Skill

Before writing code, plan what your skill will do.

### Questions to Ask:

1. **What problem does it solve?**
   - Example: "Organize downloaded files"

2. **What information does it need?**
   - Example: "File types to organize, destination directories"

3. **What are the steps?**
   - Example: "Scan files → Categorize → Move → Report"

4. **What could go wrong?**
   - Example: "Permission errors, duplicate filenames"

### Exercise: Plan Your Skill

Take 2 minutes to answer these questions for your skill idea:

```
Skill Name: ___________________
Problem: _____________________
Information Needed: __________
Steps: ________________________
Potential Issues: ____________
```

## Step 2: Create Skill Directory

Skills live in `~/.nanoclaw/workspace/skills/`.

### On Linux/Mac:

```bash
mkdir -p ~/.nanoclaw/workspace/skills/my-first-skill
cd ~/.nanoclaw/workspace/skills/my-first-skill
```

### On Windows (PowerShell):

```powershell
New-Item -ItemType Directory -Path "$env:USERPROFILE\.nanoclaw\workspace\skills\my-first-skill"
Set-Location "$env:USERPROFILE\.nanoclaw\workspace\skills\my-first-skill"
```

### On Windows (Git Bash):

```bash
mkdir -p ~/.nanoclaw/workspace/skills/my-first-skill
cd ~/.nanoclaw/workspace/skills/my-first-skill
```

## Step 3: Create SKILL.md

Create a file named `SKILL.md` in your skill directory.

### Template

Copy this template into `SKILL.md`:

```markdown
---
name: my-first-skill
description: |
  Brief description of what your skill does.
  Explain when users should use this skill.
---

# My First Skill

## Overview

Detailed description of what your skill does and why it's useful.

## When to Use This Skill

Use this skill when you need to:
- Task 1
- Task 2
- Task 3

## Prerequisites

List any prerequisites:
- Software requirements
- Configuration needed
- Permissions required

## How It Works

### Step 1: First Step

Description of what happens in step 1.

### Step 2: Second Step

Description of what happens in step 2.

### Step 3: Third Step

Description of what happens in step 3.

## Example Usage

Provide a concrete example:

```
You: "Use my-first-skill to do X"

AI will:
1. Do step 1
2. Do step 2
3. Report results
```

## Troubleshooting

### Issue: "Error message"

**Cause**: Why it happens

**Solution**: How to fix it

## Tips

- Tip 1
- Tip 2
- Tip 3
```

### Fill in the Template

Replace the template content with your skill's details:

```markdown
---
name: my-first-skill
description: |
  A simple example skill that demonstrates the SKILL.md format.
  Use this to learn how to create your own skills.
---

# My First Skill

## Overview

This is a simple skill that demonstrates the basic structure. It doesn't perform any actual operations but shows you how to structure a real skill.

## When to Use This Skill

Use this skill as a template when creating your own skills.

## Prerequisites

None! This is a documentation-only example.

## How It Works

### Step 1: Read Documentation

The AI agent reads this SKILL.md file to understand what to do.

### Step 2: Follow Instructions

The agent follows the step-by-step instructions provided.

### Step 3: Report Results

The agent reports back what was done.

## Example Usage

```
You: "Show me how my-first-skill works"

AI will:
1. Read the SKILL.md file
2. Explain the structure
3. Show you the format
```

## Troubleshooting

### Issue: "Skill not loading"

**Cause**: SKILL.md file missing or in wrong location

**Solution**:
- Ensure SKILL.md is in the skill directory
- Check the directory is in `~/.nanoclaw/workspace/skills/`
- Verify YAML frontmatter is valid

### Issue: "Invalid YAML"

**Cause**: Syntax error in frontmatter

**Solution**:
- Check for proper indentation (use spaces, not tabs)
- Ensure all fields have values
- Validate YAML syntax

## Tips

- Use clear, descriptive names for your skill
- Be specific in your descriptions
- Provide step-by-step instructions
- Include examples
- Document potential issues
```

## Step 4: Validate Your SKILL.md

Before testing, validate the format:

### Checklist:

- [ ] File is named `SKILL.md` (capital letters, .md extension)
- [ ] File is in skill directory root
- [ ] YAML frontmatter starts with `---`
- [ ] Has `name:` field in frontmatter
- [ ] Has `description:` field in frontmatter
- [ ] YAML frontmatter ends with `---`
- [ ] No syntax errors in YAML
- [ ] Content after frontmatter is in Markdown

### Test YAML Syntax

You can test YAML syntax online:
- [YAMLLint](https://www.yamllint.com/)
- [YAML Validator](https://codebeautify.org/yaml-validator)

## Step 5: Test Your Skill

### Restart nanoClaw

Restart nanoClaw so it discovers your new skill:

```bash
# Stop nanoClaw
# Start nanoClaw again
```

### Check Logs

Look for confirmation that your skill loaded:

```
[INFO] Loaded skill: my-first-skill
```

### Invoke Your Skill

Ask nanoClaw to use your skill:

```
You: "Use my-first-skill"
```

Or describe what you want:

```
You: "Help me with [what your skill does]"
```

### Expected Behavior

The AI agent should:
1. Read your SKILL.md file
2. Understand what the skill does
3. Follow the instructions you provided
4. Report the results

## Step 6: Iterate and Improve

Based on testing, refine your skill:

### Common Improvements:

1. **Add More Detail**
   - Expand instructions
   - Add more examples
   - Include edge cases

2. **Add Error Handling**
   - Document what could go wrong
   - Provide solutions
   - Add troubleshooting section

3. **Add Scripts** (Optional)
   - Create `scripts/` directory
   - Add Python, Bash, or other scripts
   - Reference scripts in SKILL.md

4. **Add Configuration** (Optional)
   - Create config file
   - Document settings
   - Provide examples

## Step 7: Add Scripts (Optional)

If your skill needs code, add scripts:

### Create Scripts Directory

```bash
mkdir scripts
```

### Add a Python Script

Create `scripts/main.py`:

```python
#!/usr/bin/env python3
"""Main script for my-first-skill."""

def main():
    """Main function."""
    print("Hello from my-first-skill!")

if __name__ == "__main__":
    main()
```

### Reference Script in SKILL.md

Update your SKILL.md:

```markdown
## How It Works

### Step 1: Execute Script

The agent runs the main script:

```bash
cd ~/.nanoclaw/workspace/skills/my-first-skill
python scripts/main.py
```

### Step 2: Process Results

The agent processes the output...
```

## Step 8: Document Your Skill

Good documentation makes skills usable:

### Essential Sections:

1. **Overview**: What does it do?
2. **When to Use**: When should I use it?
3. **Prerequisites**: What do I need?
4. **How It Works**: Step-by-step process
5. **Examples**: Concrete usage examples
6. **Troubleshooting**: Common issues and fixes

### Optional Sections:

1. **Configuration**: How to configure
2. **Advanced Usage**: Power user features
3. **Related Skills**: Other useful skills
4. **Changelog**: Version history
5. **Contributing**: How to contribute

## Step 9: Share Your Skill (Optional)

Once your skill works well:

### Package Your Skill

```bash
# Archive the skill directory
cd ~/.nanoclaw/workspace/skills/
tar -czf my-first-skill.tar.gz my-first-skill/

# Or on Windows:
# Compress the my-first-skill folder
```

### Share

- Send to friends
- Upload to a repository
- Share in nanoClaw community
- Contribute to example skills

## Step 10: Learn from Examples

Study existing skills to learn patterns:

### Simple Examples

- **simple-task**: Basic structure
- **hello-world**: Minimal working example

### Intermediate Examples

- **file-organizer**: File operations
- **note-taker**: Data management

### Advanced Examples

- **business-trip-application**: RPA automation
- **web-researcher**: Web scraping and analysis
- **report-generator**: Document generation

## Common Patterns

### Pattern 1: Information Collection

```markdown
## Required Information

Please provide:

1. **Field 1**: Description
   - Example: value

2. **Field 2**: Description
   - Example: value
```

### Pattern 2: Step-by-Step Process

```markdown
## Process

1. **Preparation**: Get ready
2. **Execution**: Do the work
3. **Verification**: Check results
4. **Cleanup**: Clean up
```

### Pattern 3: Error Handling

```markdown
## Troubleshooting

### If you see "Error X"
- Check: Y
- Solution: Z

### If you see "Error A"
- Check: B
- Solution: C
```

## Best Practices

### DO ✅

- Use clear, descriptive names
- Write detailed documentation
- Provide examples
- Handle errors gracefully
- Test thoroughly
- Keep it simple
- Follow the template

### DON'T ❌

- Use vague names
- Skip documentation
- Assume knowledge
- Ignore edge cases
- Overcomplicate
- Use formats other than SKILL.md
- Mix tools and skills

## Troubleshooting Guide

### Skill Not Loading

**Symptoms**: Skill doesn't appear in logs

**Checks**:
1. Directory is in `~/.nanoclaw/workspace/skills/`
2. `SKILL.md` file exists
3. YAML frontmatter is valid
4. `name` and `description` fields present

**Solution**: Fix any issues found and restart nanoClaw

### Skill Loads But Doesn't Work

**Symptoms**: Skill appears but doesn't function

**Checks**:
1. Instructions are clear
2. Examples are accurate
3. All steps are documented
4. Prerequisites are met

**Solution**: Improve documentation and test again

### YAML Errors

**Symptoms**: "Invalid YAML" or parsing errors

**Common Issues**:
- Using tabs instead of spaces
- Missing colons after field names
- Unclosed quotes
- Invalid special characters

**Solution**:
- Use spaces for indentation
- Ensure proper YAML syntax
- Validate with online YAML validator
- Escape special characters if needed

## Resources

### Documentation

- [SKILL.md Format Reference](skills.md)
- [nanoClaw Architecture](../openspec/project.md)
- [DeepAgents Documentation](https://deepagents.dev)

### Tools

- [YAMLLint](https://www.yamllint.com/)
- [Markdown Guide](https://www.markdownguide.org/)
- [VS Code](https://code.visualstudio.com/)

### Community

- nanoClaw Discord
- GitHub Issues
- Community Forum

## Next Steps

Now that you've created your first skill:

1. **Create More Skills**: Practice makes perfect
2. **Study Examples**: Learn from existing skills
3. **Share**: Contribute to the community
4. **Document**: Help others learn
5. **Iterate**: Improve based on feedback

## Checklist

Use this checklist before publishing your skill:

### Functionality

- [ ] Skill loads without errors
- [ ] Skill performs intended function
- [ ] Instructions are clear and accurate
- [ ] Examples work as documented
- [ ] Edge cases are handled

### Documentation

- [ ] SKILL.md has all required fields
- [ ] Overview is clear and concise
- [ ] When to Use is specific
- [ ] How It Works is detailed
- [ ] Examples are provided
- [ ] Troubleshooting section exists

### Quality

- [ ] No YAML syntax errors
- [ ] No spelling/grammar errors
- [ ] Code is formatted (if applicable)
- [ ] Naming follows conventions
- [ ] Best practices are followed

### Testing

- [ ] Tested on fresh nanoClaw install
- [ ] Tested with various inputs
- [ ] Error conditions tested
- [ ] Documentation verified

## Congratulations! 🎉

You've created your first nanoClaw skill!

### What You Learned:

✅ How to structure a skill
✅ How to write SKILL.md files
✅ How to test and validate
✅ Best practices and patterns

### What's Next:

- Create more complex skills
- Add scripts to your skills
- Share with the community
- Contribute examples

---

**Need Help?**

- Check the [SKILL.md Format Reference](skills.md)
- Review [Example Skills](../nanoclaw/skills/examples/)
- Ask in the nanoClaw community

**Found a Bug?**

- Report it on GitHub Issues
- Include your SKILL.md file
- Describe expected vs actual behavior
