---
name: tag-recommendations
description: Analyze git history and suggest version tags based on semantic versioning.
---

# Tag Recommendations

Analyze the repository's git history and recommend where version tags should be placed.

## Steps

1. List all existing tags with `git tag --list`
2. Get the full commit log with `git log --oneline --all`
3. Read `manifest.json` (or equivalent) at key commits to check version fields using `git show <hash>:path`
4. Identify untagged commits that represent meaningful version boundaries

## How to decide tag placement

- **Patch bump** (0.1.x): bug fixes, minor corrections, doc updates
- **Minor bump** (0.x.0): new features, new config options, new entities — backwards compatible
- **Major bump** (x.0.0): breaking changes (config entry migrations, removed entities, changed data structures)

Place the tag on the **last commit** of a version's work, not the first. A version tag represents the stable state at that point.

## Output format

Present a table:

| Tag | Commit | Reason |
|-----|--------|--------|

Then note any commits already tagged and whether they look correct.

If `manifest.json` contains version strings, tags should match those versions.
