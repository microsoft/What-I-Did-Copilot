import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as https from 'https';

let output: vscode.OutputChannel;
let running = false;

export function activate(context: vscode.ExtensionContext) {
    output = vscode.window.createOutputChannel('What I Did');

    context.subscriptions.push(
        output,
        vscode.commands.registerCommand('whatidid.openPanel', () =>
            BuilderPanel.show(context)
        ),
        vscode.commands.registerCommand('whatidid.run', () =>
            runReport(context, { mode: 'period', period: '7D', refresh: false, email: false })
        )
    );

    const status = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right,
        100
    );
    status.text = '$(sparkle) What I Did';
    status.tooltip = 'Generate a GitHub Copilot impact report';
    status.command = 'whatidid.openPanel';
    status.show();
    context.subscriptions.push(status);
}

export function deactivate() {
    /* nothing to clean up */
}

interface RunOptions {
    mode: 'period' | 'range';
    period?: string;
    from?: string;
    to?: string;
    refresh: boolean;
    email: boolean;
    emailTo?: string;
    outDir?: string;
}

/** Resolve the Python interpreter to use. */
async function resolvePython(): Promise<string> {
    const cfg = vscode.workspace.getConfiguration('whatidid');
    const explicit = (cfg.get<string>('pythonPath') || '').trim();
    if (explicit) {
        return explicit;
    }

    // Use the Python extension's currently selected interpreter when available.
    try {
        const ext = vscode.extensions.getExtension('ms-python.python');
        if (ext) {
            if (!ext.isActive) {
                await ext.activate();
            }
            const api: any = ext.exports;
            const envPath = api?.environments?.getActiveEnvironmentPath?.();
            if (envPath?.path) {
                return envPath.path;
            }
        }
    } catch {
        /* fall through to defaults */
    }

    const pyCfg = vscode.workspace.getConfiguration('python');
    const defPath = (pyCfg.get<string>('defaultInterpreterPath') || '').trim();
    if (defPath) {
        return defPath;
    }

    return process.platform === 'win32' ? 'python' : 'python3';
}

/** Locate whatidid.py: explicit setting, then bundled copy, then workspace. */
function resolveScript(context: vscode.ExtensionContext): string | undefined {
    const cfg = vscode.workspace.getConfiguration('whatidid');
    const explicit = (cfg.get<string>('scriptPath') || '').trim();
    if (explicit && fs.existsSync(explicit)) {
        return explicit;
    }

    const bundled = path.join(context.extensionPath, 'pysrc', 'whatidid.py');
    if (fs.existsSync(bundled)) {
        return bundled;
    }

    for (const folder of vscode.workspace.workspaceFolders ?? []) {
        const candidate = path.join(folder.uri.fsPath, 'whatidid.py');
        if (fs.existsSync(candidate)) {
            return candidate;
        }
    }
    return undefined;
}

/** Newest report_*.html in the given directory. */
function newestReport(dir: string): string | undefined {
    let newest: string | undefined;
    let newestTime = 0;
    let entries: string[];
    try {
        entries = fs.readdirSync(dir);
    } catch {
        return undefined;
    }
    for (const name of entries) {
        if (!name.startsWith('report_') || !name.endsWith('.html')) {
            continue;
        }
        const full = path.join(dir, name);
        try {
            const mtime = fs.statSync(full).mtimeMs;
            if (mtime > newestTime) {
                newestTime = mtime;
                newest = full;
            }
        } catch {
            /* ignore */
        }
    }
    return newest;
}

/** Open a self-contained HTML report inside a VS Code webview panel. */
function previewReport(reportPath: string) {
    const panel = vscode.window.createWebviewPanel(
        'whatididReport',
        'Copilot Impact Report',
        vscode.ViewColumn.Active,
        { enableScripts: true, retainContextWhenHidden: true }
    );
    try {
        panel.webview.html = fs.readFileSync(reportPath, 'utf8');
    } catch (e) {
        panel.webview.html = `<body style="font-family:sans-serif;padding:2rem">Could not read report: ${String(
            e
        )}</body>`;
    }
}

/**
 * Run whatidid.py with the given options, streaming output. When a builder
 * panel is open, progress is mirrored into it.
 */
async function runReport(
    context: vscode.ExtensionContext,
    opts: RunOptions,
    panel?: BuilderPanel
): Promise<void> {
    if (running) {
        vscode.window.showWarningMessage(
            'A report is already being generated. Please wait for it to finish.'
        );
        return;
    }

    const script = resolveScript(context);
    if (!script) {
        const msg =
            'Could not find whatidid.py. Set "whatidid.scriptPath" in settings, or open the What-I-Did-Copilot folder.';
        vscode.window.showErrorMessage(msg);
        panel?.post({ type: 'done', code: 1, error: msg });
        return;
    }

    const python = await resolvePython();
    const cwd = path.dirname(script);

    // Where the HTML report is written. Defaults to the first workspace folder
    // (the user's repo root) so reports land next to their project rather than
    // inside the extension's bundled script directory.
    const outDir =
        (opts.outDir || '').trim() ||
        vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ||
        cwd;

    const args = [script];
    if (opts.mode === 'range' && opts.from) {
        args.push('--from', opts.from);
        if (opts.to) {
            args.push('--to', opts.to);
        }
    } else {
        args.push('--date', opts.period || '7D');
    }
    if (opts.refresh) {
        args.push('--refresh');
    }
    if (opts.email) {
        const to = (opts.emailTo || '').trim();
        if (to) {
            args.push('--email', to);
        } else {
            args.push('--email');
        }
    }
    args.push('--out-dir', outDir);
    // Always run headless — the report builder has no terminal for the user
    // to answer prompts in, so the CLI must never block on input().
    args.push('--non-interactive');

    running = true;
    output.clear();
    output.show(true);
    const cmdLine = `${python} ${args.join(' ')}`;
    output.appendLine(`> ${cmdLine}\n`);
    panel?.post({ type: 'status', state: 'running', text: 'Generating report…' });
    panel?.post({ type: 'log', text: `> ${cmdLine}\n\n` });

    let proc: cp.ChildProcessWithoutNullStreams;
    try {
        proc = cp.spawn(python, args, { cwd, env: process.env });
    } catch (e) {
        running = false;
        const msg = `Failed to start Python: ${String(e)}`;
        output.appendLine(msg);
        panel?.post({ type: 'done', code: 1, error: msg });
        return;
    }

    // No interactive terminal is attached. Close the child's stdin so any
    // unexpected input() in the Python tool gets EOF and falls back instead
    // of hanging the run forever.
    proc.stdin.end();
    proc.stdout.on('data', (d: Buffer) => {
        const text = d.toString();
        output.append(text);
        panel?.post({ type: 'log', text });
    });
    proc.stderr.on('data', (d: Buffer) => {
        const text = d.toString();
        output.append(text);
        panel?.post({ type: 'log', text });
    });

    proc.on('close', (code) => {
        running = false;
        const ok = code === 0;
        let reportPath: string | undefined;
        if (ok) {
            reportPath = newestReport(outDir);
            const openInEditor = vscode.workspace
                .getConfiguration('whatidid')
                .get<boolean>('openInEditor', true);
            if (reportPath && openInEditor) {
                previewReport(reportPath);
            }
        } else {
            vscode.window.showErrorMessage(
                `Report generation failed (exit code ${code}). See the "What I Did" output for details.`
            );
        }
        panel?.post({ type: 'done', code: code ?? 1, reportPath });
    });
}

/** Best-effort detection of the user's email, mirroring whatidid.py. */
function detectEmail(cwd: string): Promise<string> {
    return new Promise((resolve) => {
        const exec = (cmd: string, args: string[]): Promise<string> =>
            new Promise((res) => {
                try {
                    const p = cp.execFile(
                        cmd,
                        args,
                        { cwd, timeout: 5000, windowsHide: true },
                        (err, stdout) => res(err ? '' : (stdout || '').trim())
                    );
                    p.on('error', () => res(''));
                } catch {
                    res('');
                }
            });

        const fromGitHub = async (): Promise<string> => {
            const token = await exec('gh', ['auth', 'token']);
            if (!token) {
                return '';
            }
            return new Promise<string>((res) => {
                const req = https.request(
                    'https://api.github.com/user/emails',
                    {
                        method: 'GET',
                        headers: {
                            Authorization: `token ${token}`,
                            'User-Agent': 'what-i-did-copilot',
                            Accept: 'application/vnd.github+json',
                        },
                        timeout: 6000,
                    },
                    (resp) => {
                        let body = '';
                        resp.on('data', (c) => (body += c));
                        resp.on('end', () => {
                            try {
                                const list = JSON.parse(body);
                                if (!Array.isArray(list)) {
                                    return res('');
                                }
                                const primary = list.find(
                                    (e: any) => e.primary && e.verified
                                );
                                const verified = list.find((e: any) => e.verified);
                                res(
                                    (primary && primary.email) ||
                                        (verified && verified.email) ||
                                        (list[0] && list[0].email) ||
                                        ''
                                );
                            } catch {
                                res('');
                            }
                        });
                    }
                );
                req.on('error', () => res(''));
                req.on('timeout', () => {
                    req.destroy();
                    res('');
                });
                req.end();
            });
        };

        (async () => {
            const gh = await fromGitHub();
            if (gh) {
                return resolve(gh);
            }
            const git = await exec('git', ['config', 'user.email']);
            resolve(git);
        })();
    });
}

/** The webview form for choosing options and launching a run. */
class BuilderPanel {
    public static current: BuilderPanel | undefined;
    private readonly panel: vscode.WebviewPanel;
    private readonly context: vscode.ExtensionContext;
    private disposables: vscode.Disposable[] = [];

    static show(context: vscode.ExtensionContext) {
        if (BuilderPanel.current) {
            BuilderPanel.current.panel.reveal(vscode.ViewColumn.Active);
            return;
        }
        const panel = vscode.window.createWebviewPanel(
            'whatididBuilder',
            'What I Did — Report Builder',
            vscode.ViewColumn.Active,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [
                    vscode.Uri.joinPath(context.extensionUri, 'media'),
                ],
            }
        );
        BuilderPanel.current = new BuilderPanel(panel, context);
    }

    private constructor(
        panel: vscode.WebviewPanel,
        context: vscode.ExtensionContext
    ) {
        this.panel = panel;
        this.context = context;
        this.panel.webview.html = this.html();

        this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
        this.panel.webview.onDidReceiveMessage(
            (msg) => this.onMessage(msg),
            null,
            this.disposables
        );

        const cwd =
            vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd();
        detectEmail(cwd).then((email) => {
            if (email) {
                this.post({ type: 'detectedEmail', email });
            }
        });
        this.post({ type: 'defaultOutDir', path: cwd });
    }

    post(message: unknown) {
        this.panel.webview.postMessage(message);
    }

    private async onMessage(msg: any) {
        switch (msg?.type) {
            case 'run': {
                const mode = msg.mode === 'range' ? 'range' : 'period';
                await runReport(
                    this.context,
                    {
                        mode,
                        period: String(msg.period || '7D'),
                        from: String(msg.from || '').trim(),
                        to: String(msg.to || '').trim(),
                        refresh: !!msg.refresh,
                        email: !!msg.email,
                        emailTo: String(msg.emailTo || '').trim(),
                        outDir: String(msg.outDir || '').trim(),
                    },
                    this
                );
                break;
            }
            case 'openReport': {
                if (msg.reportPath) {
                    previewReport(String(msg.reportPath));
                }
                break;
            }
            case 'openExternal': {
                if (msg.reportPath) {
                    vscode.env.openExternal(vscode.Uri.file(String(msg.reportPath)));
                }
                break;
            }
            case 'pickFolder': {
                const picked = await vscode.window.showOpenDialog({
                    canSelectFolders: true,
                    canSelectFiles: false,
                    canSelectMany: false,
                    openLabel: 'Save reports here',
                    title: 'Choose where to save reports',
                });
                if (picked && picked[0]) {
                    this.post({ type: 'pickedFolder', path: picked[0].fsPath });
                }
                break;
            }
        }
    }

    private html(): string {
        const webview = this.panel.webview;
        const nonce = getNonce();
        const readMedia = (name: string): string => {
            try {
                return fs.readFileSync(
                    vscode.Uri.joinPath(this.context.extensionUri, 'media', name).fsPath,
                    'utf8'
                );
            } catch {
                return '';
            }
        };
        const css = readMedia('main.css');
        const js = readMedia('main.js');
        const logoUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this.context.extensionUri, 'media', 'icon.png')
        );
        return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy"
    content="default-src 'none'; img-src ${webview.cspSource}; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<style nonce="${nonce}">${css}</style>
<title>What I Did</title>
</head>
<body>
<div class="page">

  <header class="hero">
    <img class="logo" src="${logoUri}" alt="What I Did with Copilot logo" />
    <div class="hero-text">
      <h1>What I Did with Copilot</h1>
      <p class="tagline">See — and share — everything GitHub Copilot helped you get done.</p>
    </div>
  </header>

  <p class="lead">
    This turns your private Copilot chat history into a polished, easy-to-read
    report: the projects you worked on, what got built, and an estimate of the
    time it saved you. No spreadsheets, no jargon — just a clear story you can
    read in a minute or send to your team.
  </p>

  <section class="card info">
    <h2 class="card-title">What's inside your report</h2>
    <ul class="feature-list">
      <li><span class="ico">&#128202;</span>
        <div><strong>Headline impact</strong>
          <p>An at-a-glance summary of how much time Copilot saved you across the period.</p></div></li>
      <li><span class="ico">&#128221;</span>
        <div><strong>Plain-language story</strong>
          <p>A short narrative of what you worked on — written so anyone can follow it.</p></div></li>
      <li><span class="ico">&#128640;</span>
        <div><strong>Projects &amp; what got built</strong>
          <p>Each project you touched, the features shipped, and the skills you leaned on.</p></div></li>
      <li><span class="ico">&#129534;</span>
        <div><strong>How the estimate is made</strong>
          <p>Transparent, research-backed math behind the time-saved number — no black box.</p></div></li>
    </ul>
  </section>

  <section class="card info">
    <h2 class="card-title">How it works</h2>
    <ol class="steps">
      <li><span class="step-n">1</span>
        <div><strong>Pick a range</strong><p>Choose a preset or set custom start and end dates in the builder below.</p></div></li>
      <li><span class="step-n">2</span>
        <div><strong>Generate</strong><p>Your Copilot sessions are read locally and summarized into a single page.</p></div></li>
      <li><span class="step-n">3</span>
        <div><strong>Read or share</strong><p>The report opens right here. Open it in a browser or email yourself a copy.</p></div></li>
    </ol>
    <p class="privacy">
      <span class="ico">&#128274;</span><strong>Private by design.</strong> Everything is
      generated on your own computer from your local Copilot logs. Nothing is
      uploaded, tracked, or shared unless you choose to send it.
    </p>
    <p class="fineprint">
      Credit and cost figures in the report are estimates, calculated from the
      token counts in your local session logs and GitHub's published per-model
      rates. They give an accurate picture of the shape of your AI usage, but
      your actual GitHub bill can differ depending on your plan, included credit
      allowance, and billing details that aren't visible in local logs.
    </p>
  </section>

  <section class="card builder">
    <h2 class="card-title">Build your report</h2>

    <div class="field">
      <label class="field-label">1 &nbsp;Pick a time range</label>
      <div class="segmented" id="presets" role="group" aria-label="Time range presets">
        <input type="radio" name="preset" id="p-today" value="today" />
        <label for="p-today">Today</label>
        <input type="radio" name="preset" id="p-7" value="7D" checked />
        <label for="p-7">7 days</label>
        <input type="radio" name="preset" id="p-14" value="14D" />
        <label for="p-14">14 days</label>
        <input type="radio" name="preset" id="p-30" value="30D" />
        <label for="p-30">30 days</label>
        <input type="radio" name="preset" id="p-90" value="90D" />
        <label for="p-90">90 days</label>
        <input type="radio" name="preset" id="p-custom" value="custom" />
        <label for="p-custom">Custom range</label>
      </div>
      <p class="hint">Pick a preset to fill the dates below, or edit the dates
        directly for a custom range.</p>
    </div>

    <div class="field range-fields" id="rangeFields">
      <div class="range-grid">
        <label class="date-field">
          <span>Start date</span>
          <input id="fromDate" type="date" />
        </label>
        <label class="date-field">
          <span>End date</span>
          <input id="toDate" type="date" />
        </label>
      </div>
      <p class="hint">Leave the end date on today to report right up to now.</p>
      <p class="error hidden" id="rangeError">Please choose a start date for your custom range.</p>
    </div>

    <div class="field">
      <label class="field-label">2 &nbsp;Options</label>

      <label class="toggle">
        <input id="email" type="checkbox" />
        <span class="switch" aria-hidden="true"></span>
        <span class="toggle-text">
          <strong>Email me a copy</strong>
          <small>Opens the finished report as a prefilled draft in your mail app,
            addressed below — review it and click Send.</small>
        </span>
      </label>

      <div class="range-fields hidden" id="emailToWrap">
        <label class="date-field">
          <span>Send to</span>
          <input id="emailTo" type="text" placeholder="Detecting your email&hellip;"
            autocomplete="off" spellcheck="false" />
        </label>
        <p class="hint" id="emailToHint">This is your
          GitHub account's primary email (or your <code>git config user.email</code> if
          GitHub isn't available). Add more recipients separated by commas or
          semicolons.</p>
      </div>

      <label class="toggle">
        <input id="refresh" type="checkbox" />
        <span class="switch" aria-hidden="true"></span>
        <span class="toggle-text">
          <strong>Re-analyze from scratch</strong>
          <small>Ignore cached AI analysis and re-run it on every session. Slower, but
            reflects changes to the analysis prompts or your sessions.</small>
        </span>
      </label>
    </div>

    <div class="field">
      <label class="field-label" for="outDir">3 &nbsp;Save location</label>
      <div class="out-dir-row">
        <label class="date-field out-dir-field">
          <span>Folder</span>
          <input id="outDir" type="text" spellcheck="false" autocomplete="off"
            placeholder="Detecting your workspace folder&hellip;" />
        </label>
        <button type="button" id="browseOut" class="btn-ghost browse-btn">Browse&hellip;</button>
      </div>
      <p class="hint">The report is saved here as
        <code>report_&lt;range&gt;.html</code>. Defaults to your workspace folder.</p>
    </div>

    <div class="actions">
      <button id="generate" class="btn-primary">
        <span class="btn-spark">&#10022;</span> Generate my report
      </button>
      <button id="openLast" class="btn-ghost hidden">Open last report</button>
      <button id="openExternal" class="btn-ghost hidden">Open in browser</button>
    </div>

    <div id="statusRow" class="status hidden">
      <span class="spinner" id="spinner"></span>
      <span id="statusText"></span>
    </div>

    <details id="details" class="details hidden">
      <summary>Show progress log</summary>
      <pre id="log" class="log" aria-live="polite"></pre>
    </details>
  </section>

</div>
<script nonce="${nonce}">${js}</script>
</body>
</html>`;
    }

    dispose() {
        BuilderPanel.current = undefined;
        this.panel.dispose();
        while (this.disposables.length) {
            this.disposables.pop()?.dispose();
        }
    }
}

function getNonce(): string {
    let text = '';
    const chars =
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return text;
}
