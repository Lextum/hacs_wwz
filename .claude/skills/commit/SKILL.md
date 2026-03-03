---
name: commit
description: Stage and commit changes using Conventional Commits format.
argument-hint: [optional message override]
---

# Commit

Create a git commit using the Conventional Commits specification.

## Steps

1. Run `git status` and `git diff` (staged + unstaged) to understand all changes
2. Analyze the changes and select the appropriate type
3. Stage the relevant files (prefer specific files over `git add -A`)
4. Commit with the format below

## Commit message format

```
<type>: <summary>
```

Summary line only. No body, no Co-Authored-By. Keep the summary under 72 characters, lowercase, imperative mood.

If `$ARGUMENTS` is provided, use it as the summary instead of generating one.

## Types

- **feat**: new feature or capability
- **fix**: bug fix
- **refactor**: code restructuring without behavior change
- **docs**: documentation only
- **style**: formatting, whitespace, no code change
- **test**: adding or updating tests
- **chore**: maintenance, deps, config, CI
- **perf**: performance improvement

## Rules

- Never commit files that may contain secrets (.env, credentials, tokens)
- Never use `--no-verify` or `--amend` unless explicitly asked
- Use a HEREDOC to pass the commit message
- Run `git status` after committing to verify success
