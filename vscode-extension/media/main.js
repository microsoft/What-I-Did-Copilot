// @ts-check
(function () {
    const vscode = acquireVsCodeApi();

    const presets = document.getElementById('presets');
    const presetInputs = /** @type {NodeListOf<HTMLInputElement>} */ (
        document.querySelectorAll('input[name="preset"]')
    );
    const rangeFields = document.getElementById('rangeFields');
    const fromDate = /** @type {HTMLInputElement} */ (document.getElementById('fromDate'));
    const toDate = /** @type {HTMLInputElement} */ (document.getElementById('toDate'));
    const rangeError = document.getElementById('rangeError');
    const refresh = /** @type {HTMLInputElement} */ (document.getElementById('refresh'));
    const email = /** @type {HTMLInputElement} */ (document.getElementById('email'));
    const emailTo = /** @type {HTMLInputElement} */ (document.getElementById('emailTo'));
    const emailToWrap = document.getElementById('emailToWrap');
    const outDir = /** @type {HTMLInputElement} */ (document.getElementById('outDir'));
    const browseOut = /** @type {HTMLButtonElement} */ (document.getElementById('browseOut'));
    const generate = /** @type {HTMLButtonElement} */ (document.getElementById('generate'));
    const openLast = /** @type {HTMLButtonElement} */ (document.getElementById('openLast'));
    const openExternal = /** @type {HTMLButtonElement} */ (document.getElementById('openExternal'));
    const statusRow = document.getElementById('statusRow');
    const statusText = document.getElementById('statusText');
    const spinner = document.getElementById('spinner');
    const details = document.getElementById('details');
    const log = document.getElementById('log');

    let lastReport = '';

    const today = new Date().toISOString().slice(0, 10);
    fromDate.max = today;
    toDate.max = today;
    if (!toDate.value) {
        toDate.value = today;
    }

    function selectedPreset() {
        for (const r of presetInputs) {
            if (r.checked) {
                return r.value;
            }
        }
        return '7D';
    }

    function setPreset(value) {
        for (const r of presetInputs) {
            r.checked = r.value === value;
        }
        markSelected();
    }

    function markSelected() {
        for (const r of presetInputs) {
            const label = presets.querySelector('label[for="' + r.id + '"]');
            if (label) {
                label.classList.toggle('is-selected', r.checked);
            }
        }
    }

    function ymd(d) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + day;
    }

    function applyPresetDates() {
        const value = selectedPreset();
        if (value === 'custom') {
            return;
        }
        const now = new Date();
        toDate.value = ymd(now);
        if (value === 'today') {
            fromDate.value = ymd(now);
        } else {
            const match = /^(\d+)D$/.exec(value);
            const days = match ? parseInt(match[1], 10) : 7;
            const start = new Date();
            start.setDate(start.getDate() - days);
            fromDate.value = ymd(start);
        }
    }

    // Restore prior selections.
    const prev = vscode.getState() || {};
    if (prev.preset) {
        setPreset(prev.preset);
    }
    markSelected();
    if (prev.from) {
        fromDate.value = prev.from;
    }
    if (prev.to) {
        toDate.value = prev.to;
    }
    refresh.checked = !!prev.refresh;
    email.checked = !!prev.email;
    if (prev.emailTo) {
        emailTo.value = prev.emailTo;
    }
    if (prev.outDir) {
        outDir.value = prev.outDir;
    }
    if (prev.lastReport) {
        lastReport = prev.lastReport;
        openLast.classList.remove('hidden');
        openExternal.classList.remove('hidden');
    }
    applyPresetDates();
    syncEmail();

    function saveState() {
        vscode.setState({
            preset: selectedPreset(),
            from: fromDate.value,
            to: toDate.value,
            refresh: refresh.checked,
            email: email.checked,
            emailTo: emailTo.value,
            outDir: outDir.value,
            lastReport,
        });
    }

    function syncEmail() {
        emailToWrap.classList.toggle('hidden', !email.checked);
    }

    presets.addEventListener('change', () => {
        markSelected();
        applyPresetDates();
        rangeError.classList.add('hidden');
        saveState();
    });
    fromDate.addEventListener('input', () => {
        rangeError.classList.add('hidden');
        setPreset('custom');
        saveState();
    });
    toDate.addEventListener('input', () => {
        setPreset('custom');
        saveState();
    });
    refresh.addEventListener('change', saveState);
    email.addEventListener('change', () => {
        syncEmail();
        saveState();
    });
    emailTo.addEventListener('input', saveState);
    outDir.addEventListener('input', saveState);
    browseOut.addEventListener('click', () => {
        vscode.postMessage({ type: 'pickFolder' });
    });

    generate.addEventListener('click', () => {
        if (!fromDate.value) {
            rangeError.classList.remove('hidden');
            fromDate.focus();
            return;
        }

        log.textContent = '';
        details.classList.remove('hidden');
        details.open = false;
        statusRow.classList.remove('hidden');
        spinner.classList.remove('done');
        statusText.textContent = 'Reading your Copilot sessions and building the report…';
        generate.disabled = true;
        saveState();

        vscode.postMessage({
            type: 'run',
            mode: 'range',
            from: fromDate.value,
            to: toDate.value,
            refresh: refresh.checked,
            email: email.checked,
            emailTo: emailTo.value,
            outDir: outDir.value,
        });
    });

    openLast.addEventListener('click', () => {
        if (lastReport) {
            vscode.postMessage({ type: 'openReport', reportPath: lastReport });
        }
    });

    openExternal.addEventListener('click', () => {
        if (lastReport) {
            vscode.postMessage({ type: 'openExternal', reportPath: lastReport });
        }
    });

    window.addEventListener('message', (event) => {
        const msg = event.data;
        switch (msg.type) {
            case 'detectedEmail':
                if (msg.email) {
                    emailTo.placeholder = msg.email;
                    if (!emailTo.value.trim()) {
                        emailTo.value = msg.email;
                        saveState();
                    }
                }
                break;
            case 'defaultOutDir':
                if (msg.path) {
                    outDir.placeholder = msg.path;
                    if (!outDir.value.trim()) {
                        outDir.value = msg.path;
                        saveState();
                    }
                }
                break;
            case 'pickedFolder':
                if (msg.path) {
                    outDir.value = msg.path;
                    saveState();
                }
                break;
            case 'log':
                log.textContent += msg.text;
                log.scrollTop = log.scrollHeight;
                break;
            case 'status':
                statusText.textContent = msg.text || '';
                break;
            case 'done':
                generate.disabled = false;
                spinner.classList.add('done');
                if (msg.code === 0) {
                    statusText.textContent = '\u2713 Your report is ready \u2014 it just opened in a new tab.';
                    if (msg.reportPath) {
                        lastReport = msg.reportPath;
                        openLast.classList.remove('hidden');
                        openExternal.classList.remove('hidden');
                        saveState();
                    }
                } else {
                    statusText.textContent =
                        '\u2717 ' + (msg.error || 'Something went wrong. Open "Show progress log" to see what happened.');
                    details.open = true;
                }
                break;
        }
    });
})();
