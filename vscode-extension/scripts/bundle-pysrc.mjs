// Copies the Python sources from the repo root into pysrc/ so the packaged
// .vsix is self-contained and users never have to clone the repo.
import { cpSync, mkdirSync, rmSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const extRoot = join(here, '..');
const repoRoot = join(extRoot, '..');
const dest = join(extRoot, 'pysrc');

const PY_FILES = [
    'whatidid.py',
    'harvest.py',
    'analyze.py',
    'report.py',
    'best_practices.py',
    'email_send.py',
];
const DIRS = ['prompts', 'skills', 'docs'];

rmSync(dest, { recursive: true, force: true });
mkdirSync(dest, { recursive: true });

for (const f of PY_FILES) {
    const src = join(repoRoot, f);
    if (existsSync(src)) {
        cpSync(src, join(dest, f));
    } else {
        console.warn(`[bundle-pysrc] skipped missing file: ${f}`);
    }
}

for (const d of DIRS) {
    const src = join(repoRoot, d);
    if (existsSync(src)) {
        cpSync(src, join(dest, d), { recursive: true });
    }
}

console.log(`[bundle-pysrc] Python sources copied to ${dest}`);
