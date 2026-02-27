---
name: python
description: Python coding conventions, tooling, and style
tags: [python, style, tooling]
version: 1
---

## Python Conventions

### Style

- Follow PEP 8. Line length: 88 characters (Black default).
- Use `black` for formatting and `ruff` for linting — enforce both in CI.
- Prefer f-strings over `.format()` or `%`-formatting.
- Use `from __future__ import annotations` for deferred annotation evaluation.

### Types

- Add type annotations to all public functions and methods.
- Use `typing` / `collections.abc` types for generics (`list[str]`, not `List[str]`).
- Avoid `Any` except at integration boundaries with untyped third-party code.
- Run `mypy` or `pyright` in strict mode on new code.

### Project Structure

- Manage dependencies and virtual environments with `uv`.
- Declare dependencies in `pyproject.toml`; do not use `requirements.txt` for new projects.
- Use `src/` layout: package code lives in `src/<package_name>/`, not at the repo root.
- Tests live in `tests/` at the repo root, not inside the package.

### Testing

- Use `pytest`. Keep fixtures in `conftest.py`.
- Aim for test names that read as sentences: `test_load_snippet_prefers_workspace_over_builtin`.
- Mock at the boundary (filesystem, network, time) — not inside the unit under test.

### Error Handling

- Raise specific exception types (subclass `Exception` when needed).
- Use `contextlib.suppress` for intentionally ignored exceptions, not bare `except: pass`.
- Do not catch `BaseException` unless you immediately re-raise it.
