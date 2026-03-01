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


def load_snippet(name: str, search_dirs: list[Path]) -> Optional[str]:
    """Return the body of the first snippet file found for *name*.

    Searches *search_dirs* in order; first match wins.
    Returns None if the snippet is not found in any directory.
    """
    for directory in search_dirs:
        candidate = directory / f"{name}.md"
        if candidate.exists():
            return _strip_frontmatter(candidate)
    return None


def regenerate(
    workspace: Path,
    builtin_snippets_dir: Path,
    include: list[str],
) -> list[str]:
    """Assemble and write .github/copilot-instructions.md for *workspace*.

    1. Resolve each snippet name in *include* order.
    2. Concatenate their bodies (front matter stripped).
    3. Append the magic separator.
    4. Preserve any user content that was already below the separator.
    5. Write the result, creating parent directories as needed.
    """
    workspace_snippets_dir = workspace / ".prompt-weave" / "snippets"
    output_path = workspace / ".github" / "copilot-instructions.md"

    # --- Extract existing user content below separator --------------------
    user_section = ""
    if output_path.exists():
        existing = output_path.read_text(encoding="utf-8")
        if SEPARATOR in existing:
            user_section = existing.split(SEPARATOR, 1)[1].strip()
        else:
            # No separator — entire file is user content
            user_section = existing.strip()

    # --- Empty include: revert to plain user file -------------------------
    if not include:
        if output_path.exists() and SEPARATOR in output_path.read_text(encoding="utf-8"):
            if user_section:
                output_path.write_text(user_section + "\n", encoding="utf-8")
            else:
                output_path.unlink()
        return []

    # Search order: workspace (highest priority) → user home → built-in
    search_dirs = [workspace_snippets_dir, USER_SNIPPETS_DIR, builtin_snippets_dir]

    # --- Build generated section ------------------------------------------
    bodies: list[str] = []
    included: list[str] = []
    missing: list[str] = []

    for name in include:
        content = load_snippet(name, search_dirs)
        if content is None:
            missing.append(name)
        else:
            included.append(name)
            bodies.append(content.strip())

    generated_section = "\n\n".join(bodies)

    # --- Assemble output --------------------------------------------------
    parts: list[str] = []

    if generated_section:
        parts.append(generated_section)
        parts.append("")          # blank line before separator

    parts.append(SEPARATOR)

    if user_section:
        parts.append("")          # blank line after separator
        parts.append(user_section)

    output = "\n".join(parts) + "\n"

    # --- Write ------------------------------------------------------------
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")

    if missing:
        raise RuntimeError(
            f"Regenerated, but the following snippets were not found: "
            f"{', '.join(missing)}"
        )

    return included


def check_gitignore(workspace: Path) -> list[str]:
    """Return warning messages if .github/copilot-instructions.md is not git-ignored.

    Checks whether the workspace's .gitignore exists and contains an entry
    covering ``.github/copilot-instructions.md``.  Returns a list with a
    single warning string when the file may be tracked by Git, or an empty
    list when everything looks fine.
    """
    output_rel = ".github/copilot-instructions.md"
    gitignore_path = workspace / ".gitignore"

    if not gitignore_path.exists():
        return [
            f"{output_rel} may be tracked by Git: "
            "no .gitignore found in the workspace."
        ]

    lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
    # Intentionally simple: check only the most common literal patterns that
    # cover the file.  `.github/` correctly covers all files under that
    # directory in gitignore semantics (trailing slash means "match as dir").
    if stripped in (output_rel, "copilot-instructions.md", ".github/"):
            return []

    return [
        f"{output_rel} may be tracked by Git: "
        "add an entry to .gitignore to suppress this warning."
    ]
