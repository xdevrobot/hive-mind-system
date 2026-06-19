# GitHub PR Creator Skill

Create Pull Requests following Hive Mind patterns.

## Create PR
```bash
gh pr create --title "{title}" --body "{body}"
gh pr create --draft --title "{title}" --body "{body}"
```

## PR Body Template
```markdown
## Summary
{Brief description}

## Changes
- {Change 1}
- {Change 2}

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass

## Related Issues
Fixes #{issue-number}
```

## Check CI
```bash
gh pr checks {pr-number}
gh pr checks {pr-number} --watch
```

## Rules

1. Draft PR for WIP
2. Fixes/Closes in body
3. Describe changes
4. Check CI before merge
5. One PR = one task
