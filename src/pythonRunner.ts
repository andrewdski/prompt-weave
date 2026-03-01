import * as cp from 'child_process';
import * as path from 'path';

export interface PythonOutput {
    output: string;
    warnings: string[];
}

/**
 * Invoke the Python core via `uv run` and return stdout parsed into
 * informational output and warning lines (prefixed with "Warning: ").
 * stderr is collected and thrown as an Error on non-zero exit.
 *
 * uv automatically:
 *  - resolves the correct Python version
 *  - creates / reuses a cached venv
 *  - installs dependencies declared in pyproject.toml
 */
export function runPythonCore(extensionPath: string, args: string[]): Promise<PythonOutput> {
    return new Promise((resolve, reject) => {
        const pythonProjectDir = path.join(extensionPath, 'python');

        // `uv run --directory <dir>` sets the project root so uv finds pyproject.toml
        // and installs declared dependencies into an isolated venv automatically.
        const uvArgs = ['run', '--directory', pythonProjectDir, 'python', '-m', 'prompt_weave.cli', ...args];

        const proc = cp.spawn('uv', uvArgs, {
            stdio: ['ignore', 'pipe', 'pipe'],
            windowsHide: true,
        });

        let stdout = '';
        let stderr = '';

        proc.stdout.on('data', (data: Buffer) => { stdout += data.toString(); });
        proc.stderr.on('data', (data: Buffer) => { stderr += data.toString(); });

        proc.on('close', (code: number | null) => {
            if (code === 0) {
                const lines = stdout.trim().split(/\r?\n/).filter(l => l.length > 0);
                const warnings = lines
                    .filter(l => l.startsWith('Warning: '))
                    .map(l => l.slice('Warning: '.length));
                const output = lines
                    .filter(l => !l.startsWith('Warning: '))
                    .join('\n')
                    .trim();
                resolve({ output, warnings });
            } else {
                const detail = stderr.trim() || `Process exited with code ${code ?? 'null'}`;
                reject(new Error(detail));
            }
        });

        proc.on('error', (err: NodeJS.ErrnoException) => {
            if (err.code === 'ENOENT') {
                reject(new Error(
                    'uv not found on PATH. Install it from https://docs.astral.sh/uv/ and make sure it is available in your shell.'
                ));
            } else {
                reject(new Error(`Failed to launch uv: ${err.message}`));
            }
        });
    });
}
