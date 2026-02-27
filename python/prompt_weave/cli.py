"""Command-line interface — invoked by the TypeScript extension shell via `uv run`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import regenerate


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m prompt_weave.cli",
        description="prompt-weave: assemble .github/copilot-instructions.md from snippets",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── regenerate ─────────────────────────────────────────────────────────
    regen = subparsers.add_parser(
        "regenerate",
        help="Regenerate .github/copilot-instructions.md for a workspace",
    )
    regen.add_argument(
        "--workspace",
        required=True,
        type=Path,
        metavar="PATH",
        help="Absolute path to the workspace root",
    )
    regen.add_argument(
        "--builtin-snippets",
        required=True,
        type=Path,
        metavar="PATH",
        help="Absolute path to the extension's built-in snippets directory",
    )
    regen.add_argument(
        "--include",
        nargs="*",
        default=[],
        metavar="NAME",
        help="Ordered list of snippet names to include",
    )

    args = parser.parse_args()

    if args.command == "regenerate":
        try:
            included = regenerate(
                workspace=args.workspace,
                builtin_snippets_dir=args.builtin_snippets,
                include=args.include,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        else:
            if included:
                names = ", ".join(included)
                print(f"Regenerated with {len(included)} snippet(s): {names}")


if __name__ == "__main__":
    main()
