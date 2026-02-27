---
name: readme
description: Project README
---

# Prompt Weave

A VS Code extension that dynamically assembles `.github/copilot-instructions.md` from a library of reusable Markdown snippets.

## Status

Under active development — V1 (core functionality) in progress.

## What it does

- Maintains a **library of Markdown snippets**, each describing a set of Copilot instructions (e.g. `base`, `docker`, `python`).
- Assembles them into `.github/copilot-instructions.md` in the order you choose, per workspace.
- **Preserves anything you write below the magic separator** — your custom additions survive every regeneration.
- Runs automatically on workspace open (configurable).

## Requirements

- [uv](https://docs.astral.sh/uv/) on your PATH — handles Python and dependencies automatically.

## Quick start

1. Install the extension (not yet published).
2. Add snippet names to your workspace settings:
   ```jsonc
   "promptWeave.include": ["base", "python"]
   ```
3. Run **Prompt Weave: Regenerate Instructions** from the command palette, or let it run on open.

## Snippet tiers

| Tier | Location | Priority |
|---|---|---|
| Workspace | `.prompt-weave/snippets/` | Highest |
| User | `~/.prompt-weave/snippets/` | Middle |
| Built-in | `<extension>/snippets/` | Lowest |

Built-in snippets: `base`, `docker`, `python`, `powershell`.

## Development

```sh
# Install Node dependencies and compile TypeScript
npm install && npm run compile

# Run Python tests
cd python && uv run pytest -v
```

Press **F5** in VS Code to launch the Extension Development Host.
