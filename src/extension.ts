import * as vscode from 'vscode';
import * as path from 'path';
import { runPythonCore } from './pythonRunner';

export async function activate(context: vscode.ExtensionContext): Promise<void> {

    const regenerate = async (): Promise<void> => {
        const folders = vscode.workspace.workspaceFolders;
        if (!folders || folders.length === 0) {
            vscode.window.showWarningMessage('Prompt Weave: No workspace folder open.');
            return;
        }

        const workspacePath = folders[0].uri.fsPath;
        const config = vscode.workspace.getConfiguration('promptWeave');
        const include: string[] = config.get<string[]>('include') ?? [];
        const snippetsDir = path.join(context.extensionPath, 'snippets');

        const args = [
            'regenerate',
            '--workspace', workspacePath,
            '--builtin-snippets', snippetsDir,
        ];
        if (include.length > 0) {
            args.push('--include', ...include);
        }

        try {
            const { output, warnings } = await runPythonCore(context.extensionPath, args);
            const message = output || 'Instructions regenerated.';
            vscode.window.showInformationMessage(`Prompt Weave: ${message}`);
            for (const w of warnings) {
                vscode.window.showWarningMessage(`Prompt Weave: ${w}`);
            }
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            vscode.window.showErrorMessage(`Prompt Weave: ${msg}`);
        }
    };

    context.subscriptions.push(
        vscode.commands.registerCommand('promptWeave.regenerate', regenerate)
    );

    const config = vscode.workspace.getConfiguration('promptWeave');
    if (config.get<boolean>('regenerateOnOpen') === true) {
        const include = config.get<string[]>('include') ?? [];
        if (include.length > 0) {
            await regenerate();
        }
    }
}

export function deactivate(): void { }
