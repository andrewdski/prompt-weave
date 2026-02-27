---
name: powershell
description: PowerShell scripting conventions and best practices
tags: [powershell, windows, scripting]
version: 1
---

## PowerShell Conventions

### Style

- Use approved verb-noun cmdlet names (`Get-Item`, not `GrabItem`).
- Use full parameter names in scripts, not aliases or positional shortcuts — aliases are
  fine interactively, but scripts must be readable by strangers.
- Use `PascalCase` for function names and `$camelCase` for local variables.
- Indent with 4 spaces; keep lines ≤ 120 characters.

### Strictness

- Always begin scripts with `Set-StrictMode -Version Latest` and `$ErrorActionPreference = 'Stop'`.
- Never use `-ErrorAction SilentlyContinue` to hide errors — handle them explicitly.
- Test path existence with `Test-Path` before reading; check null before dereferencing.

### Output

- Use `Write-Verbose` for diagnostic output and `Write-Error` for errors.
- Do not use `Write-Host` in reusable functions — it bypasses the pipeline and cannot be
  captured. Prefer `Write-Output` or returning objects.
- Return typed objects from functions, not formatted strings; let the caller decide presentation.

### Error Handling

- Wrap risky operations in `try / catch / finally`.
- Re-throw with `throw $_` to preserve the original error record, not `throw $_.Exception`.

### Cross-Platform

- Use `Join-Path` and `$PSScriptRoot` instead of hard-coded path separators.
- Prefer PowerShell Core (`pwsh`) over Windows PowerShell (`powershell`) for new scripts.
- Test scripts on both Windows and Linux when targeting cross-platform environments.
