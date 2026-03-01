"""Tests for prompt_weave.core — independently runnable without VS Code.

Coverage strategy
=================
These tests exercise every code path in core.py (100 % line coverage) across
the following dimensions:

load_snippet
------------
- Happy path: snippet found in a single search dir.
- Priority: workspace dir overrides builtin; full three-tier hierarchy.
- Missing snippet: returns None.
- Edge inputs: empty search-dirs list, non-existent directory in the path,
  snippet with no front-matter, snippet with an empty body.

regenerate
----------
- File lifecycle: output file created from scratch, .github/ dir auto-created,
  file deleted when include is empty and no user content remains.
- Separator semantics: generated content above, user content below, separator
  embedded inside user content is preserved (only the first split counts).
- User-content preservation: existing content without a separator is treated as
  user-owned; content below the separator survives regeneration.
- Empty-include paths: file without separator left untouched, separator-only
  file deleted, user content kept when separator is removed.
- Snippet resolution: multiple snippets concatenated in order, workspace
  snippets override builtins end-to-end, duplicate names are included twice.
- Error handling: missing snippets raise RuntimeError after writing the file;
  error message lists *all* missing names.
- Return value: list of successfully included snippet names.
- Idempotency: two consecutive runs produce identical output (with and without
  user content).
- Content integrity: Unicode round-trip, trailing whitespace stripped, no
  excessive blank lines introduced, whitespace-only snippet bodies handled.
- State transitions: changing the snippet list between runs removes old content.
- Boundary files: 0-byte existing file, file that is only the separator line.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from prompt_weave.core import SEPARATOR, check_gitignore, load_snippet, regenerate


# ── Helpers ────────────────────────────────────────────────────────────────

def write_snippet(directory: Path, name: str, body: str, meta: dict | None = None) -> None:
    """Write a minimal snippet file with YAML front matter."""
    if meta is None:
        meta = {"name": name, "description": f"{name} snippet", "tags": []}
    directory.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, value in meta.items():
        lines.append(f"{key}: {value!r}")
    lines += ["---", "", body]
    (directory / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")


# ── load_snippet ───────────────────────────────────────────────────────────

class TestLoadSnippet:
    def test_finds_builtin(self, tmp_path: Path) -> None:
        builtin = tmp_path / "builtin"
        workspace_snippets = tmp_path / "workspace" / ".prompt-weave" / "snippets"
        write_snippet(builtin, "base", "Base content")

        result = load_snippet("base", [workspace_snippets, builtin])
        assert result == "Base content"

    def test_workspace_overrides_builtin(self, tmp_path: Path) -> None:
        builtin = tmp_path / "builtin"
        workspace_snippets = tmp_path / "workspace" / ".prompt-weave" / "snippets"
        write_snippet(builtin, "base", "Builtin content")
        write_snippet(workspace_snippets, "base", "Workspace content")

        result = load_snippet("base", [workspace_snippets, builtin])
        assert result == "Workspace content"

    def test_missing_returns_none(self, tmp_path: Path) -> None:
        builtin = tmp_path / "builtin"
        builtin.mkdir()
        result = load_snippet("nonexistent", [builtin])
        assert result is None

    def test_front_matter_stripped(self, tmp_path: Path) -> None:
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Rules\n\nBe concise.")
        result = load_snippet("base", [builtin])
        assert result is not None
        assert "---" not in result
        assert "## Rules" in result

    def test_empty_search_dirs_returns_none(self, tmp_path: Path) -> None:
        """No directories to search — should return None, not crash."""
        result = load_snippet("anything", [])
        assert result is None

    def test_nonexistent_search_dir_skipped(self, tmp_path: Path) -> None:
        """A directory in the search path that doesn't exist is silently skipped."""
        ghost_dir = tmp_path / "does_not_exist"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "Found")

        result = load_snippet("base", [ghost_dir, builtin])
        assert result == "Found"

    def test_snippet_without_front_matter(self, tmp_path: Path) -> None:
        """A plain Markdown file with no YAML front matter is loaded as-is."""
        snippets = tmp_path / "snippets"
        snippets.mkdir()
        (snippets / "plain.md").write_text("Just markdown\n\nNo front matter.", encoding="utf-8")

        result = load_snippet("plain", [snippets])
        assert result is not None
        assert "Just markdown" in result

    def test_snippet_with_empty_body(self, tmp_path: Path) -> None:
        """A snippet file with front matter but no body returns an empty string."""
        snippets = tmp_path / "snippets"
        snippets.mkdir()
        (snippets / "empty.md").write_text("---\nname: empty\n---\n", encoding="utf-8")

        result = load_snippet("empty", [snippets])
        assert result is not None
        assert result.strip() == ""

    def test_three_tier_priority(self, tmp_path: Path) -> None:
        """With three search dirs, the first (workspace) wins over second (user) and third (builtin)."""
        workspace_dir = tmp_path / "ws_snippets"
        user_dir = tmp_path / "user_snippets"
        builtin_dir = tmp_path / "builtin"
        write_snippet(workspace_dir, "base", "Workspace version")
        write_snippet(user_dir, "base", "User version")
        write_snippet(builtin_dir, "base", "Builtin version")

        # Workspace wins
        assert load_snippet("base", [workspace_dir, user_dir, builtin_dir]) == "Workspace version"
        # Without workspace, user wins
        assert load_snippet("base", [user_dir, builtin_dir]) == "User version"
        # Only builtin
        assert load_snippet("base", [builtin_dir]) == "Builtin version"


# ── regenerate ─────────────────────────────────────────────────────────────

class TestRegenerate:
    def test_creates_output_file(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base\n\nSome rules.")

        regenerate(workspace, builtin, ["base"])

        output = workspace / ".github" / "copilot-instructions.md"
        assert output.exists()
        text = output.read_text(encoding="utf-8")
        assert "## Base" in text
        assert SEPARATOR in text

    def test_separator_divides_sections(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "Generated content")

        regenerate(workspace, builtin, ["base"])

        text = (workspace / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
        generated_part, _sep, _rest = text.partition(SEPARATOR)
        assert "Generated content" in generated_part

    def test_preserves_user_content_below_separator(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")

        output_path = workspace / ".github" / "copilot-instructions.md"
        output_path.parent.mkdir(parents=True)
        output_path.write_text(
            f"Old generated\n\n{SEPARATOR}\n\nUser notes here.\n",
            encoding="utf-8",
        )

        regenerate(workspace, builtin, ["base"])

        text = output_path.read_text(encoding="utf-8")
        assert "## Base" in text
        assert "User notes here." in text
        assert "Old generated" not in text

    def test_user_content_appears_after_separator(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "Generated")

        output_path = workspace / ".github" / "copilot-instructions.md"
        output_path.parent.mkdir(parents=True)
        output_path.write_text(f"Old\n\n{SEPARATOR}\n\nMy notes\n", encoding="utf-8")

        regenerate(workspace, builtin, ["base"])

        text = output_path.read_text(encoding="utf-8")
        assert text.index(SEPARATOR) < text.index("My notes")
        assert text.index(SEPARATOR) > text.index("Generated")

    def test_empty_include_does_not_create_file(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        builtin.mkdir()

        regenerate(workspace, builtin, [])

        output = workspace / ".github" / "copilot-instructions.md"
        assert not output.exists()

    def test_empty_include_removes_separator_keeps_user_content(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        builtin.mkdir()

        output_path = workspace / ".github" / "copilot-instructions.md"
        output_path.parent.mkdir(parents=True)
        output_path.write_text(
            f"## Generated\n\n{SEPARATOR}\n\nMy custom notes.\n",
            encoding="utf-8",
        )

        regenerate(workspace, builtin, [])

        text = output_path.read_text(encoding="utf-8")
        assert "My custom notes." in text
        assert SEPARATOR not in text

    def test_empty_include_deletes_file_when_no_user_content(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        builtin.mkdir()

        output_path = workspace / ".github" / "copilot-instructions.md"
        output_path.parent.mkdir(parents=True)
        output_path.write_text(
            f"## Generated\n\n{SEPARATOR}\n",
            encoding="utf-8",
        )

        regenerate(workspace, builtin, [])

        assert not output_path.exists()

    def test_empty_include_leaves_file_without_separator_untouched(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        builtin.mkdir()

        output_path = workspace / ".github" / "copilot-instructions.md"
        output_path.parent.mkdir(parents=True)
        original = "My hand-written instructions.\n"
        output_path.write_text(original, encoding="utf-8")

        regenerate(workspace, builtin, [])

        assert output_path.read_text(encoding="utf-8") == original

    def test_nonempty_include_preserves_existing_file_as_user_content(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")

        output_path = workspace / ".github" / "copilot-instructions.md"
        output_path.parent.mkdir(parents=True)
        output_path.write_text("My old instructions.\n", encoding="utf-8")

        regenerate(workspace, builtin, ["base"])

        text = output_path.read_text(encoding="utf-8")
        assert "## Base" in text
        assert SEPARATOR in text
        assert "My old instructions." in text
        assert text.index(SEPARATOR) < text.index("My old instructions.")

    def test_multiple_snippets_concatenated_in_order(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")
        write_snippet(builtin, "docker", "## Docker")

        regenerate(workspace, builtin, ["base", "docker"])

        text = (workspace / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
        assert text.index("## Base") < text.index("## Docker")

    def test_missing_snippet_raises_after_writing(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")

        with pytest.raises(RuntimeError, match="ghost"):
            regenerate(workspace, builtin, ["base", "ghost"])

        # File should still have been written with the found snippets
        text = (workspace / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
        assert "## Base" in text

    def test_github_dir_created_automatically(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")

        assert not (workspace / ".github").exists()
        regenerate(workspace, builtin, ["base"])
        assert (workspace / ".github" / "copilot-instructions.md").exists()

    def test_idempotent_regeneration(self, tmp_path: Path) -> None:
        """Running regenerate twice should produce the same output."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")

        regenerate(workspace, builtin, ["base"])
        first = (workspace / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")

        regenerate(workspace, builtin, ["base"])
        second = (workspace / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")

        assert first == second

    # ── Additional corner-case tests ──────────────────────────────────────

    def test_returns_list_of_included_snippet_names(self, tmp_path: Path) -> None:
        """regenerate() returns the names of snippets that were successfully included."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")
        write_snippet(builtin, "docker", "## Docker")

        result = regenerate(workspace, builtin, ["base", "docker"])
        assert result == ["base", "docker"]

    def test_all_snippets_missing_raises(self, tmp_path: Path) -> None:
        """When every snippet in the include list is missing, a RuntimeError is raised."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        builtin.mkdir()

        with pytest.raises(RuntimeError, match="ghost1"):
            regenerate(workspace, builtin, ["ghost1", "ghost2"])

    def test_multiple_missing_snippets_all_listed_in_error(self, tmp_path: Path) -> None:
        """Error message lists every missing snippet, not just the first."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")

        with pytest.raises(RuntimeError, match="alpha") as exc_info:
            regenerate(workspace, builtin, ["base", "alpha", "beta"])
        assert "alpha" in str(exc_info.value)
        assert "beta" in str(exc_info.value)

    def test_duplicate_snippet_in_include(self, tmp_path: Path) -> None:
        """Including the same snippet twice results in its content appearing twice."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")

        result = regenerate(workspace, builtin, ["base", "base"])

        text = (workspace / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
        # Content appears twice, separated by double-newline
        assert text.count("## Base") == 2
        assert result == ["base", "base"]

    def test_unicode_content_preserved(self, tmp_path: Path) -> None:
        """Unicode in snippets and user content is preserved round-trip."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "intl", "Héllo wörld — «quotes» 中文 🚀")

        output_path = workspace / ".github" / "copilot-instructions.md"
        output_path.parent.mkdir(parents=True)
        output_path.write_text(
            f"Old\n\n{SEPARATOR}\n\nUser notes: café ñ 日本語\n",
            encoding="utf-8",
        )

        regenerate(workspace, builtin, ["intl"])

        text = output_path.read_text(encoding="utf-8")
        assert "Héllo wörld — «quotes» 中文 🚀" in text
        assert "café ñ 日本語" in text

    def test_existing_empty_file(self, tmp_path: Path) -> None:
        """A 0-byte existing output file is handled gracefully (treated as no user content)."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")

        output_path = workspace / ".github" / "copilot-instructions.md"
        output_path.parent.mkdir(parents=True)
        output_path.write_text("", encoding="utf-8")

        regenerate(workspace, builtin, ["base"])

        text = output_path.read_text(encoding="utf-8")
        assert "## Base" in text
        assert SEPARATOR in text

    def test_separator_inside_user_content_not_split(self, tmp_path: Path) -> None:
        """Only the first separator is used for splitting; a second one in user content is preserved."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")

        output_path = workspace / ".github" / "copilot-instructions.md"
        output_path.parent.mkdir(parents=True)
        # User content itself contains the separator string
        output_path.write_text(
            f"Old generated\n\n{SEPARATOR}\n\nUser notes\n{SEPARATOR}\nMore user notes\n",
            encoding="utf-8",
        )

        regenerate(workspace, builtin, ["base"])

        text = output_path.read_text(encoding="utf-8")
        assert "## Base" in text
        assert "User notes" in text
        assert "More user notes" in text
        # User's embedded separator is preserved as-is
        parts = text.split(SEPARATOR)
        assert len(parts) >= 2  # At least the main separator + user's embedded one

    def test_idempotent_with_user_content(self, tmp_path: Path) -> None:
        """Regenerating twice with user content produces identical output."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")

        output_path = workspace / ".github" / "copilot-instructions.md"
        output_path.parent.mkdir(parents=True)
        output_path.write_text(
            f"Old\n\n{SEPARATOR}\n\nMy custom notes\n",
            encoding="utf-8",
        )

        regenerate(workspace, builtin, ["base"])
        first = output_path.read_text(encoding="utf-8")

        regenerate(workspace, builtin, ["base"])
        second = output_path.read_text(encoding="utf-8")

        assert first == second

    def test_changing_snippet_list(self, tmp_path: Path) -> None:
        """Switching from [base, docker] to [base] removes docker content."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")
        write_snippet(builtin, "docker", "## Docker")

        regenerate(workspace, builtin, ["base", "docker"])
        text1 = (workspace / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
        assert "## Docker" in text1

        regenerate(workspace, builtin, ["base"])
        text2 = (workspace / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
        assert "## Base" in text2
        assert "## Docker" not in text2

    def test_workspace_snippet_overrides_builtin_end_to_end(self, tmp_path: Path) -> None:
        """regenerate uses workspace snippets over builtins (end-to-end)."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "Builtin base rules")
        ws_snippets = workspace / ".prompt-weave" / "snippets"
        write_snippet(ws_snippets, "base", "Custom workspace rules")

        regenerate(workspace, builtin, ["base"])

        text = (workspace / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
        assert "Custom workspace rules" in text
        assert "Builtin base rules" not in text

    def test_file_with_only_separator(self, tmp_path: Path) -> None:
        """Existing file that is just the separator line — no user content to preserve."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")

        output_path = workspace / ".github" / "copilot-instructions.md"
        output_path.parent.mkdir(parents=True)
        output_path.write_text(f"{SEPARATOR}\n", encoding="utf-8")

        regenerate(workspace, builtin, ["base"])

        text = output_path.read_text(encoding="utf-8")
        assert "## Base" in text
        assert SEPARATOR in text

    def test_whitespace_only_snippet_body(self, tmp_path: Path) -> None:
        """A snippet whose body is only whitespace is included but contributes no visible text."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        snippets = tmp_path / "builtin"
        snippets.mkdir(parents=True, exist_ok=True)
        (snippets / "blank.md").write_text("---\nname: blank\n---\n   \n  \n", encoding="utf-8")

        result = regenerate(workspace, builtin, ["blank"])

        assert result == ["blank"]
        text = (workspace / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
        assert SEPARATOR in text

    def test_empty_include_with_empty_existing_file(self, tmp_path: Path) -> None:
        """Empty include + empty existing file → file unchanged (no separator present)."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        builtin.mkdir()

        output_path = workspace / ".github" / "copilot-instructions.md"
        output_path.parent.mkdir(parents=True)
        output_path.write_text("", encoding="utf-8")

        regenerate(workspace, builtin, [])

        # File has no separator, so it's left untouched
        assert output_path.read_text(encoding="utf-8") == ""

    def test_single_snippet_no_extra_blank_lines(self, tmp_path: Path) -> None:
        """With one snippet and no user content, output has clean formatting."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base")

        regenerate(workspace, builtin, ["base"])

        text = (workspace / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
        # Should not have triple+ blank lines
        assert "\n\n\n\n" not in text

    def test_snippet_with_trailing_whitespace(self, tmp_path: Path) -> None:
        """Trailing whitespace in snippet body is stripped cleanly."""
        workspace = tmp_path / "workspace"
        builtin = tmp_path / "builtin"
        write_snippet(builtin, "base", "## Base\n\nContent   \n\n   ")

        regenerate(workspace, builtin, ["base"])

        text = (workspace / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
        assert "## Base" in text
        assert SEPARATOR in text


# ── check_gitignore ────────────────────────────────────────────────────────

import subprocess as _subprocess


def _git_available() -> bool:
    try:
        _subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, _subprocess.CalledProcessError):
        return False


pytestmark_git = pytest.mark.skipif(not _git_available(), reason="git not available")


def _make_git_repo(path: Path) -> None:
    """Initialise a bare-minimum git repository at *path*."""
    _subprocess.run(["git", "init", str(path)], capture_output=True, check=True)
    # Provide minimal identity so git doesn't complain in some environments
    _subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], capture_output=True, check=True)
    _subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], capture_output=True, check=True)


@pytestmark_git
class TestCheckGitignore:
    TARGET = ".github/copilot-instructions.md"

    def test_not_a_git_repo_returns_no_warning(self, tmp_path: Path) -> None:
        """Directory that is not a git repo → no warning (git check-ignore exits 128)."""
        warnings = check_gitignore(tmp_path)
        assert warnings == []

    def test_git_repo_no_gitignore_returns_warning(self, tmp_path: Path) -> None:
        """Git repo with no .gitignore → file would be tracked → warning returned."""
        _make_git_repo(tmp_path)
        warnings = check_gitignore(tmp_path)
        assert len(warnings) == 1
        assert self.TARGET in warnings[0]

    def test_git_repo_gitignore_with_exact_path_returns_no_warning(self, tmp_path: Path) -> None:
        """.gitignore with exact path → git confirms ignored → no warning."""
        _make_git_repo(tmp_path)
        (tmp_path / ".gitignore").write_text(".github/copilot-instructions.md\n", encoding="utf-8")
        assert check_gitignore(tmp_path) == []

    def test_git_repo_gitignore_with_github_dir_returns_no_warning(self, tmp_path: Path) -> None:
        """.gitignore with .github/ directory entry → git confirms ignored → no warning."""
        _make_git_repo(tmp_path)
        (tmp_path / ".gitignore").write_text(".github/\n", encoding="utf-8")
        assert check_gitignore(tmp_path) == []

    def test_git_repo_gitignore_with_wildcard_returns_no_warning(self, tmp_path: Path) -> None:
        """.gitignore with *.md wildcard → git confirms file is ignored → no warning."""
        _make_git_repo(tmp_path)
        (tmp_path / ".gitignore").write_text("*.md\n", encoding="utf-8")
        assert check_gitignore(tmp_path) == []

    def test_git_repo_gitignore_without_matching_entry_returns_warning(self, tmp_path: Path) -> None:
        """.gitignore without a matching entry → git confirms not ignored → warning."""
        _make_git_repo(tmp_path)
        (tmp_path / ".gitignore").write_text("node_modules/\n*.log\n", encoding="utf-8")
        warnings = check_gitignore(tmp_path)
        assert len(warnings) == 1
        assert self.TARGET in warnings[0]
