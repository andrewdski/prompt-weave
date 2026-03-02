"""Core logic: snippet loading, front matter parsing, and file assembly."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import NamedTuple
from typing import Optional

import frontmatter

# The magic separator — invisible when rendered, machine-readable.
# Everything above is generated; everything below is user-owned.
SEPARATOR = "<!-- prompt-weave:generated - do not edit above this line -->"

# Fixed user-level snippets directory (no configuration needed).
USER_SNIPPETS_DIR = Path.home() / ".prompt-weave" / "snippets"

# Matches a stamped blob header that includes a sha256 digest.
# Old-format headers (without sha256) do not match and are treated as stale.
_BLOB_HEADER_RE = re.compile(
    r'^<!-- prompt-weave:line \d+ "[^"]*" sha256 ([0-9a-f]{64}) -->$'
)


class ResolvedSnippet(NamedTuple):
    """Resolved snippet content and provenance metadata."""

    content: str
    source_label: str
    source_line: int
    source_path: Path


def _strip_frontmatter(path: Path) -> str:
    """Load a Markdown file and return only the content (front matter stripped)."""
    post = frontmatter.load(str(path))
    return str(post.content)


def _sha256_hex(path: Path) -> str:
    """Return the SHA-256 hex digest of *path*'s raw bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract_blob_sha256s(text: str) -> list[str]:
    """Return ordered sha256 digests from stamped blob headers in *text*.

    Old-format headers (without sha256) yield no entry, so the resulting list
    will differ from current digests and trigger regeneration — the safe
    default when a header is missing or unparsable.
    """
    result = []
    for line in text.splitlines():
        m = _BLOB_HEADER_RE.match(line)
        if m:
            result.append(m.group(1))
    return result


def _content_start_line(path: Path) -> int:
    """Return 1-based line where snippet body starts in a Markdown file."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if lines and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:], start=2):
            if line.strip() == "---":
                return index + 1

    return 1


def _source_label(
    directory: Path,
    candidate: Path,
    workspace_snippets_dir: Path,
    builtin_snippets_dir: Path,
) -> str:
    """Return stable source label used in generated line directives."""
    if directory == workspace_snippets_dir:
        return f"workspace:{candidate.name}"
    if directory == USER_SNIPPETS_DIR:
        return f"user:{candidate.name}"
    if directory == builtin_snippets_dir:
        return f"builtin:{candidate.name}"
    return candidate.name


def resolve_snippet(
    name: str,
    search_dirs: list[Path],
    workspace_snippets_dir: Path,
    builtin_snippets_dir: Path,
) -> Optional[ResolvedSnippet]:
    """Resolve a snippet and include provenance metadata for generation."""
    for directory in search_dirs:
        candidate = directory / f"{name}.md"
        if candidate.exists():
            return ResolvedSnippet(
                content=_strip_frontmatter(candidate),
                source_label=_source_label(
                    directory=directory,
                    candidate=candidate,
                    workspace_snippets_dir=workspace_snippets_dir,
                    builtin_snippets_dir=builtin_snippets_dir,
                ),
                source_line=_content_start_line(candidate),
                source_path=candidate,
            )
    return None


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
    2. Concatenate their bodies (front matter stripped), each prefixed with a
       per-blob header stamped with the SHA-256 of the source file's raw bytes.
    3. Append the magic separator.
    4. Preserve any user content that was already below the separator.
    5. Skip writing when the stamped SHA-256 digests all match (no source change).
    6. Write the result, creating parent directories as needed.
    """
    workspace_snippets_dir = workspace / ".prompt-weave" / "snippets"
    output_path = workspace / ".github" / "copilot-instructions.md"

    # --- Extract existing user content below separator --------------------
    user_section = ""
    existing_text = ""
    if output_path.exists():
        existing_text = output_path.read_text(encoding="utf-8")
        if SEPARATOR in existing_text:
            user_section = existing_text.split(SEPARATOR, 1)[1].strip()
        else:
            # No separator — entire file is user content
            user_section = existing_text.strip()

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
    sha256s: list[str] = []

    for name in include:
        resolved = resolve_snippet(
            name=name,
            search_dirs=search_dirs,
            workspace_snippets_dir=workspace_snippets_dir,
            builtin_snippets_dir=builtin_snippets_dir,
        )
        if resolved is None:
            missing.append(name)
        else:
            included.append(name)
            digest = _sha256_hex(resolved.source_path)
            sha256s.append(digest)
            body = resolved.content.strip()
            directive = (
                f'<!-- prompt-weave:line {resolved.source_line}'
                f' "{resolved.source_label}" sha256 {digest} -->'
            )
            if body:
                bodies.append(f"{directive}\n{body}")
            else:
                bodies.append(directive)

    # --- Skip rewrite when all source digests match -----------------------
    if not missing and existing_text and SEPARATOR in existing_text:
        generated_existing = existing_text.split(SEPARATOR, 1)[0]
        if _extract_blob_sha256s(generated_existing) == sha256s:
            return included

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
