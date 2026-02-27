---
name: prompt-weave
type: vscode-extension
language: python
status: planning
created: 2026-02-26
author: andre
---

# Prompt Weave — VS Code Extension Plan

## Overview

`prompt-weave` is a VS Code extension that dynamically assembles `.github/copilot-instructions.md` from a library of reusable Markdown snippets. It allows users to maintain a single source of truth for Copilot instructions across all their projects, with per-workspace customization and user-owned additions preserved across regeneration.

## Motivation

GitHub Copilot's instruction system has three problems:
1. **No user-level instructions file** — only per-workspace `.github/copilot-instructions.md` and ugly JSON strings in `settings.json`
2. **No composability** — no way to say "always include my base rules, plus Docker rules if this is a Docker project"
3. **No living documents** — a one-shot script breaks the moment snippets are updated

`prompt-weave` solves all three.

## Architecture

### Storage Layers

| What | Where | Mechanism |
|---|---|---|
| Per-workspace snippet selection | `.vscode/settings.json` | `promptWeave.include[]` |
| Generated output | `.github/copilot-instructions.md` | Extension writes this |
| User custom additions | Bottom of same file | Preserved across regeneration |

### Snippet Path Resolution

Snippet search paths are **hard-coded** — no configuration needed. Three tiers are searched in order, first match wins:

| Tier | Location | Purpose |
|---|---|---|
| **Built-in** | `<extension>/snippets/` | Sensible defaults, shipped with extension, read-only |
| **User** | `~/.prompt-weave/snippets/` | Personal conventions, available in all workspaces |
| **Workspace** | `.prompt-weave/snippets/` | Project-specific overrides, highest priority |

### Snippet Format

Each snippet is a Markdown file with YAML front matter:

```markdown
---
name: docker
description: Docker and container development conventions
tags: [docker, containers]
version: 1
---

## Docker Conventions
...content...
```

### The Magic Separator

```markdown
<!-- prompt-weave:generated - do not edit above this line -->
```

- HTML comment — invisible when rendered, machine-readable
- Everything **above**: generated, overwritten on each run
- Everything **below**: user-owned, preserved across regeneration

## Extension Contributions

### Commands

| Command | Description |
|---|---|
| `Prompt Weave: Regenerate Instructions` | Manually regenerate `.github/copilot-instructions.md` |
| `Prompt Weave: Add Snippet to Workspace Prompt` | Fuzzy quick-pick over all discovered snippets (name + description + source tier); adds selection to `include[]` and regenerates |
| `Prompt Weave: Remove Snippet from Workspace Prompt` | Fuzzy quick-pick over currently included snippets; removes selection from `include[]` and regenerates |
| `Prompt Weave: New User Snippet` | Create a new snippet in `~/.prompt-weave/snippets/` with YAML front matter template, then open in editor |
| `Prompt Weave: New Workspace Snippet` | Create a new snippet in `.prompt-weave/snippets/` with YAML front matter template, then open in editor |
| `Prompt Weave: Open Snippet Library` | Open the user global snippets folder in VS Code |

> **Note**: Add/Remove commands are the *primary* interface for managing `include[]`. The raw `settings.json` array is the source of truth but editing it directly requires knowing exact snippet names — use the commands for discovery.

### Settings

```jsonc
{
    // Auto-regenerate copilot-instructions.md on workspace open.
    // Type: boolean
    "promptWeave.regenerateOnOpen": true,
    // Names of snippets to include, matched against front matter 'name:' field.
    // Type: string[] — order determines concatenation order in output file.
    // Use the Add/Remove commands rather than editing this directly.
    "promptWeave.include": []
}
```

### Copilot Tool (Killer Feature)

The extension exposes a tool callable by Copilot itself:

```
update_snippet(name, content, reason)
```

This allows Copilot to say:
> *"I notice you always prefer YAML front matter in Markdown files. Want me to add that as a permanent instruction?"*

And then actually do it — teaching itself to improve its own future context.

## Snippet Library Structure

```
<extension>/snippets/     ← built-in, read-only
  base.md
  docker.md
  python.md
  node.md

~/.prompt-weave/snippets/ ← user, writable (New User Snippet)
  yaml-frontmatter.md    # personal conventions
  powershell.md
  cuda.md
  ...

.prompt-weave/snippets/   ← workspace, writable (New Workspace Snippet)
  my-override.md         # project-specific overrides
  ...
```

## File Generation Logic

1. Read `promptWeave.include[]` from workspace settings (ordered list of snippet names)
2. For each snippet name, search `promptWeave.snippetPaths` in order — first match wins
3. Strip YAML front matter from each matched snippet
4. Concatenate snippet bodies in `include[]` order
5. Append separator line
6. If `.github/copilot-instructions.md` exists, preserve everything after existing separator
7. Write file

## Implementation Notes

- Written in **Python** (bundled with extension via pip)
- YAML front matter parsing: `python-frontmatter` library
- Extension shell: TypeScript (standard VS Code extension requirement) calling Python
- Python script is the core logic, TypeScript is the thin VS Code integration layer

## Milestones

### V1 — Core Functionality
- [ ] Scaffold VS Code extension (TypeScript shell)
- [ ] Python core: snippet loading, front matter parsing, file assembly
- [ ] Magic separator: preserve user content below it
- [ ] `Regenerate Instructions` command
- [ ] `regenerateOnOpen` setting
- [ ] Basic snippet library (base, docker, python, powershell)

### V2 — Discoverability
- [ ] `Add Snippet to Workspace` command with picker UI
- [ ] `New Snippet` command with front matter template
- [ ] Snippet validation (warn on missing `name`, `description`)

### V3 — Copilot Integration
- [ ] Expose `update_snippet` as a Copilot tool
- [ ] Let Copilot suggest new snippets based on observed patterns

## General Instructions

- Stop after each milestone and let the user examine, test, and approve
- Tag each milestone upon approval
- Follow VS Code extension publishing conventions
- Python core logic must be independently testable without VS Code
- Use YAML front matter in all Markdown documents in this project