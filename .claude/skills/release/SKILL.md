---
name: release
description: Bump manifest version, commit, tag, and publish a GitHub release. Use when the user wants to release, publish, cut a release, bump the version, tag a version, ship a new version, or create a GitHub release.
argument-hint: <major|minor|patch>
compatibility: gh CLI (GitHub CLI) must be installed and authenticated
---

# Release

Create a versioned release by bumping the manifest, committing, tagging, and publishing via `gh`.

## Steps

1. Parse `$ARGUMENTS` to determine the bump type (`major`, `minor`, or `patch`). If missing or invalid, ask the user.
2. Read `custom_components/wwz_energy/manifest.json` and extract the current `version` field.
3. Compute the new version by bumping the appropriate segment (reset lower segments to 0).
4. Update the `version` field in `manifest.json` with the new version.
5. Stage and commit:
   ```
   git add custom_components/wwz_energy/manifest.json
   git commit -m "chore: release v<new_version>"
   ```
6. Tag the commit:
   ```
   git tag v<new_version>
   ```
7. Push the commit and tag:
   ```
   git push && git push --tags
   ```
8. Write release notes and create the GitHub release (see format below):
   ```
   gh release create v<new_version> --notes "$(cat <<'EOF'
   <release notes>
   EOF
   )"
   ```
9. Print the release URL when done.

## Release notes format

Write concise, human-readable release notes. Use these sections as needed (omit empty sections):

```
## Breaking Changes
- Description of what broke and what users need to do to migrate

## Features
- Description of new functionality

## Fixes
- Description of bug fixes
```

Guidelines:
- Summarize user-facing impact, not commit messages — group related commits into a single bullet.
- Always include a **Breaking Changes** section when: entities are removed or renamed, config flow changes require re-setup, data structures change in ways that lose history, or behavior changes that users will notice.
- Keep each bullet to one line.
- Do not include chore/docs/CI changes unless they affect users.

## Rules

- Never use `--no-verify` or `--force` unless explicitly asked.
- If there are uncommitted changes beyond `manifest.json`, warn the user before proceeding.
- Use a HEREDOC for the commit message.
