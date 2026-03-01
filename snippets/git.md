---
name: git
description: Git and commit workflow conventions
tags: [git, commits, workflow]
version: 1
---

## Files and Commits

- One logical change per commit.
- Use Conventional Commits-style prefixes when writing commit subjects (e.g., `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`); prefer `docs:` for documentation commits (`doc:` is allowed for legacy consistency).
- Commit messages: imperative mood, ≤ 72 chars subject, blank line before body.
- Keep files focused; one primary concept per file.