"""Tests for prompt_weave.core — independently runnable without VS Code."""

from __future__ import annotations

from pathlib import Path

import pytest

from prompt_weave.core import SEPARATOR, load_snippet, regenerate


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
