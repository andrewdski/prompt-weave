"""Core logic: snippet loading, front matter parsing, and file assembly."""

from __future__ import annotations

import subprocess
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

    Uses ``git check-ignore`` to ask Git directly whether the generated file
    would be ignored.  Returns an empty list when Git is unavailable, the
    directory is not a Git repository, or the file is already covered by an
    ignore rule.  Returns a one-element warning list when Git confirms the
    file would be tracked.
    """
    output_rel = ".github/copilot-instructions.md"
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", output_rel],
            cwd=workspace,
            capture_output=True,
        )
    except FileNotFoundError:
        # git is not installed — nothing to warn about
        return []

    if result.returncode == 0:
        # File is ignored by git — no warning needed
        return []
    if result.returncode == 1:
        # File is NOT ignored by git — warn the user
        return [
            f"{output_rel} may be tracked by Git: "
            "add an entry to .gitignore to suppress this warning."
        ]
    # Any other exit code (e.g. 128 = not a git repository) — stay silent
    return []
