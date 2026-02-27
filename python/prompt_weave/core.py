"""Core logic: snippet loading, front matter parsing, and file assembly."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import frontmatter

# The magic separator — invisible when rendered, machine-readable.
# Everything above is generated; everything below is user-owned.
SEPARATOR = "<!-- prompt-weave:generated - do not edit above this line -->"

# Fixed user-level snippets directory (no configuration needed).
USER_SNIPPETS_DIR = Path.home() / ".prompt-weave" / "snippets"


def _strip_frontmatter(path: Path) -> str:
    """Load a Markdown file and return only the content (front matter stripped)."""
    post = frontmatter.load(str(path))
    return str(post.content)


def load_snippet(name: str, builtin_dir: Path, workspace_snippets_dir: Path) -> Optional[str]:
    """Return the body of the first snippet file found for *name*.

    Search order (highest priority first):
      1. Workspace:  <workspace>/.prompt-weave/snippets/<name>.md
      2. User:       ~/.prompt-weave/snippets/<name>.md
      3. Built-in:   <extension>/snippets/<name>.md

    Returns None if the snippet is not found in any tier.
    """
    search_dirs = [workspace_snippets_dir, USER_SNIPPETS_DIR, builtin_dir]
    for directory in search_dirs:
        candidate = directory / f"{name}.md"
        if candidate.exists():
            return _strip_frontmatter(candidate)
    return None


def regenerate(
    workspace: Path,
    builtin_snippets_dir: Path,
    include: list[str],
) -> None:
    """Assemble and write .github/copilot-instructions.md for *workspace*.

    1. Resolve each snippet name in *include* order.
    2. Concatenate their bodies (front matter stripped).
    3. Append the magic separator.
    4. Preserve any user content that was already below the separator.
    5. Write the result, creating parent directories as needed.
    """
    workspace_snippets_dir = workspace / ".prompt-weave" / "snippets"
    output_path = workspace / ".github" / "copilot-instructions.md"

    # --- Build generated section ------------------------------------------
    bodies: list[str] = []
    missing: list[str] = []

    for name in include:
        content = load_snippet(name, builtin_snippets_dir, workspace_snippets_dir)
        if content is None:
            missing.append(name)
        else:
            bodies.append(content.strip())

    if missing:
        print(
            f"Warning: the following snippets were not found and were skipped: "
            f"{', '.join(missing)}",
            file=sys.stderr,
        )

    generated_section = "\n\n".join(bodies)

    # --- Preserve user content below separator ----------------------------
    user_section = ""
    if output_path.exists():
        existing = output_path.read_text(encoding="utf-8")
        if SEPARATOR in existing:
            user_section = existing.split(SEPARATOR, 1)[1]

    # --- Assemble output --------------------------------------------------
    parts: list[str] = []

    if generated_section:
        parts.append(generated_section)
        parts.append("")          # blank line before separator

    parts.append(SEPARATOR)

    stripped_user = user_section.strip()
    if stripped_user:
        parts.append("")          # blank line after separator
        parts.append(stripped_user)

    output = "\n".join(parts) + "\n"

    # --- Write ------------------------------------------------------------
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")
