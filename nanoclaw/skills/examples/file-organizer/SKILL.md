---
name: file-organizer
description: |
  File organization skill that helps sort, categorize, and organize files in the workspace.
  Use this when you need to organize files by type, date, name, or custom criteria.
  This skill demonstrates file operations and workspace management.
---

# File Organizer Skill

## Overview

The File Organizer skill helps organize files in your nanoClaw workspace. It can sort files by type, date, size, or custom criteria, making it easier to maintain an organized workspace.

## When to Use This Skill

Use this skill when you need to:
- Organize downloaded files into appropriate directories
- Sort files by type (images, documents, code, etc.)
- Clean up a cluttered workspace directory
- Move files based on naming patterns or dates
- Create organized directory structures

## Prerequisites

- Files must be in the nanoClaw workspace directory
- Sufficient permissions to read and move files
- Enough disk space for reorganization

## Organization Patterns

### By File Type

Organizes files into directories based on their extension:

```
workspace/
├── images/
│   ├── png/
│   ├── jpg/
│   └── svg/
├── documents/
│   ├── pdf/
│   ├── docx/
│   └── txt/
├── code/
│   ├── py/
│   ├── js/
│   └── html/
└── archives/
    ├── zip/
    └── tar/
```

### By Date

Organizes files into directories based on creation or modification date:

```
workspace/
├── 2026/
│   ├── 01-January/
│   ├── 02-February/
│   └── 03-March/
└── 2025/
    └── 12-December/
```

### Custom Pattern

Organizes files based on a custom pattern or criteria you specify.

## How to Use

### Option 1: Quick Organization (Default)

Simply say: "Organize my files" or "Clean up my workspace"

The skill will:
1. Scan the workspace for unorganized files
2. Ask which organization pattern you prefer
3. Show you a preview of the changes
4. Organize files after confirmation

### Option 2: Specific Pattern

Specify how you want files organized:

"Organize my files by type"
"Sort files by date into monthly folders"
"Move all PDFs to a documents folder"

### Option 3: Custom Organization

Provide specific criteria:

"Put all files starting with 'report' in a reports folder"
"Organize images into folders by resolution"
"Group code files by programming language"

## Usage Examples

### Example 1: Organize Downloads

```
You: "I have a lot of files in my downloads folder, can you organize them?"

AI will:
1. Ask: "How would you like them organized? (by type, by date, or custom)"
2. You choose: "By type please"
3. AI shows: Preview of organization plan
4. You confirm: "Yes, go ahead"
5. AI organizes: Creates directories and moves files
6. AI reports: Summary of what was done
```

### Example 2: Sort Images

```
You: "Can you organize all my images by type?"

AI will:
1. Find all image files (png, jpg, gif, etc.)
2. Create appropriate subdirectories
3. Move files to matching directories
4. Report: "Moved 47 images into organized folders"
```

### Example 3: Date-Based Organization

```
You: "Organize my files by date"

AI will:
1. Check file modification dates
2. Create year/month directories
3. Move files to appropriate date folders
4. Report: "Organized 123 files into date folders"
```

## What the Skill Does

### Step 1: Scan

The skill scans the workspace directory to:
- Count total files
- Identify file types
- Check file sizes
- Note file dates

### Step 2: Plan

Based on your chosen pattern, the skill:
- Creates directory structure plan
- Determines where each file will go
- Estimates time required
- Checks for potential conflicts (duplicate names, etc.)

### Step 3: Preview

Before making changes, the skill shows:
- Number of files to be moved
- New directory structure
- Any potential issues or warnings
- Asks for your confirmation

### Step 4: Organize

After confirmation, the skill:
- Creates necessary directories
- Moves files to organized locations
- Handles naming conflicts
- Logs all operations

### Step 5: Report

After completion, the skill reports:
- Number of files organized
- New directory structure created
- Any issues encountered
- Suggestions for maintenance

## Safety Features

### Confirmation Required

The skill always asks for confirmation before:
- Creating new directories
- Moving files
- Overwriting existing files

### Conflict Handling

If conflicts are detected (e.g., duplicate filenames):
- The skill warns you
- Shows the conflict details
- Asks how to proceed (rename, skip, or overwrite)

### Dry Run Mode

You can preview what will happen without making changes:
"Show me how you would organize my files but don't do it yet"

## Configuration

### Default Settings

The skill uses these defaults:
- **Organization pattern**: By file type
- **Conflict handling**: Ask user
- **Confirmation**: Always required
- **Logging**: Detailed log of all operations

### Custom Configuration

You can create a `.organizer-config` file in your workspace:

```yaml
# File organizer configuration
default_pattern: by_type
create_date_folders: false
conflict_resolution: ask
dry_run_by_default: false
```

## Troubleshooting

### Issue: "No files found to organize"

**Cause**: Workspace directory is empty or already organized

**Solution**:
- Check that files are in the workspace directory
- Verify you're looking in the right location
- Try a different organization pattern

### Issue: "Permission denied when moving files"

**Cause**: File permissions issue

**Solution**:
- Check file ownership and permissions
- Ensure nanoClaw has write access
- Close any programs using the files

### Issue: "Duplicate filename detected"

**Cause**: Two files would have the same name after moving

**Solution**:
- The skill will ask how to handle it
- Options: Rename, skip, or overwrite
- Choose "rename" to keep both files

## Tips for Best Results

1. **Start with Dry Run**: Preview changes before applying
2. **Backup Important Files**: Before major reorganization
3. **Use Descriptive Names**: Organize into clearly named folders
4. **Regular Maintenance**: Run organizer periodically
5. **Customize Patterns**: Create organization schemes that fit your workflow

## Advanced Usage

### Batch Operations

Organize specific file types:
"Organize all PDF files into a reports folder"

### Conditional Organization

Organize based on file properties:
"Put files larger than 10MB into a large-files folder"

### Integration with Other Skills

This skill works well with:
- **search-files**: Find files before organizing
- **batch-rename**: Rename files during organization
- **archive**: Create archives after organizing

## Limitations

- Only works within nanoClaw workspace directory
- Cannot organize files outside workspace
- Requires appropriate file permissions
- Large file sets may take time to process

## Future Enhancements

Planned features for future versions:
- Undo functionality
- Scheduled automatic organization
- Machine learning-based smart organization
- Integration with cloud storage
- File deduplication

## See Also

- **simple-task**: Basic skill structure example
- **web-research**: Research and data organization
- nanoClaw documentation on file operations
