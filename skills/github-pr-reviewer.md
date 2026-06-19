# GitHub PR Review Skill

Review Pull Requests following Hive Mind patterns.

## View PR
```bash
gh pr view {pr-number}
gh pr diff {pr-number}
```

## Review via CLI
```bash
gh pr review {pr-number} --approve --body "LGTM!"
gh pr review {pr-number} --request-changes --body "Please fix..."
```

## Review Checklist
- [ ] No syntax errors
- [ ] Code style matches project
- [ ] No code duplication
- [ ] Error handling and edge cases
- [ ] Unit tests for new functionality
- [ ] No hardcoded secrets
- [ ] Input validation
- [ ] All CI checks passed

## Rules

1. CI first - don't review if CI failed
2. Constructive feedback
3. LGTM with comments is OK
4. Request changes for serious issues
5. Verify tests
