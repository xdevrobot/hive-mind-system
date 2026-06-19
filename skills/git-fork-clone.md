# Git Fork & Clone Skill

Fork and clone repositories following Hive Mind patterns.

## Fork via CLI
```bash
gh repo fork <owner/repo> --clone=false
```

## Clone
```bash
git clone https://github.com/<owner>/<repo>.git
cd <repo>
```

## Add upstream remote
```bash
git remote add upstream https://github.com/<original-owner>/<repo>.git
git fetch upstream
```

## Sync fork
```bash
git checkout main
git fetch upstream
git merge upstream/main
git push origin main
```

## Rules

1. Always fork before cloning
2. Set upstream remote
3. Sync before creating feature branches
4. Push to origin, not upstream
