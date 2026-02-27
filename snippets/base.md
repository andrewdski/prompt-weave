---
name: base
description: General coding conventions and communication style
tags: [general, style, code-quality]
version: 1
---

## General Conventions

- Prefer simple, explicit code over clever one-liners.
- Name variables, functions, and classes for what they *do*, not how they work.
- Keep functions short; if a function needs a comment to explain what it does, consider splitting it.
- Avoid abbreviations in names unless they are universally understood (e.g., `id`, `url`, `html`).
- Delete dead code rather than commenting it out; version control preserves history.

## Comments

- Write comments that explain *why*, not *what* — the code explains what.
- Use TODO comments sparingly and include a tracking reference when possible: `# TODO(#123): ...`.
- Do not leave debugging `print` / `console.log` / `fmt.Println` statements in committed code.

## Error Handling

- Surface errors early; avoid swallowing them silently.
- Prefer typed, descriptive errors over generic ones.
- Never use exceptions for normal control flow.

## Files and Commits

- One logical change per commit.
- Commit messages: imperative mood, ≤ 72 chars subject, blank line before body.
- Keep files focused; one primary concept per file.
