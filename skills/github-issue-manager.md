# GitHub Issue Manager Skill

Manage GitHub issues following Hive Mind patterns.

## Create issue
```bash
gh issue create --title "Title" --body "Description" --label "bug"
```

## List issues
```bash
gh issue list --state open --label "bug"
gh issue list --assignee @me
```

## View issue
```bash
gh issue view <number>
```

## Close issue
```bash
gh issue close <number>
```

## Add comment
```bash
gh issue comment <number> --body "Comment"
```

## Rules

1. Use labels for categorization
2. Link PRs to issues with Fixes/Closes
3. Add comments for progress updates
4. Close when done
