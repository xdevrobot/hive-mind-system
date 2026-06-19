# GitHub PR Merger Skill

Merge Pull Requests following Hive Mind patterns.

## Merge via CLI
```bash
gh pr merge {pr-number} --squash --delete-branch
gh pr merge {pr-number} --merge --delete-branch
gh pr merge {pr-number} --rebase --delete-branch
```

## Auto-merge
```bash
gh pr merge {pr-number} --auto --squash --delete-branch
```

## Pre-merge checklist
```bash
gh pr checks {pr-number}
gh pr view {pr-number} --json reviews --jq '.reviews[].state'
gh pr view {pr-number} --json mergeable
```

## Merge strategies
- **Squash** (recommended): One commit, clean history
- **Merge**: Preserves full branch history
- **Rebase**: Linear history, no merge commit

## Rules

1. CI must be green
2. At least 1 approve
3. Always use --delete-branch
4. Squash for feature branches
5. Fixes/Closes for auto-close
