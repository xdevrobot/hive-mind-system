# Git Branch Manager Skill

Manage Git branches following Hive Mind patterns.

## Create feature branch
```bash
git checkout -b hive/<issue-number>-<description>
```

## List branches
```bash
git branch -a
git branch --contains <commit>
```

## Delete branch
```bash
git branch -d <branch-name>
git push origin --delete <branch-name>
```

## Rename branch
```bash
git branch -m <old-name> <new-name>
git push origin -u <new-name>
```

## Rules

1. Use `hive/` prefix for Hive Mind branches
2. Include issue number in branch name
3. Delete branch after merge
4. Never commit directly to main
