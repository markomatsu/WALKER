const dropZone = document.querySelector('[data-dropzone]');
const fileListEl = document.querySelector('[data-filelist]');
const codeInput = document.querySelector('[data-code]');
const outputEl = document.querySelector('[data-output]');
const runButton = document.querySelector('[data-run]');
const pickButton = document.querySelector('[data-pick]');
const clearFilesButton = document.querySelector('[data-clear-files]');
const clearCodeButton = document.querySelector('[data-clear-code]');
const statusEl = document.querySelector('[data-status]');
const severityFilterEl = document.querySelector('[data-filter-severity]');
const topicFilterEl = document.querySelector('[data-filter-topic]');
const toggleSectionsButton = document.querySelector('[data-toggle-sections]');
const exportJsonButton = document.querySelector('[data-export-json]');
const exportTextButton = document.querySelector('[data-export-text]');
const copyAllButton = document.querySelector('[data-copy-all]');
const printAllButton = document.querySelector('[data-print-all]');
const sourceFileEl = document.querySelector('[data-source-file]');
const sourceCodeEl = document.querySelector('[data-source-code]');
const outputActionButtons = [copyAllButton, printAllButton, exportJsonButton, exportTextButton, toggleSectionsButton];

let selectedFiles = [];
let latestResults = [];
let collapseSections = false;
const sourceCache = new Map();

const CPP_FILE_RE = /\.(cpp|cc|cxx|c|h|hpp)$/i;

function isCppFile(path) {
  return CPP_FILE_RE.test(path || '');
}

function renderFileList() {
  fileListEl.innerHTML = '';
  if (!selectedFiles.length) {
    fileListEl.textContent = 'No files selected.';
    updateClearButtonsVisibility();
    return;
  }

  const ul = document.createElement('ul');
  ul.className = 'file-list';
  selectedFiles.forEach((file) => {
    const li = document.createElement('li');
    const name = file.split(/[\\/]/).pop();
    li.textContent = name || file;
    ul.appendChild(li);
  });
  fileListEl.appendChild(ul);
  updateClearButtonsVisibility();
}

function setStatus(message, tone = 'neutral') {
  statusEl.textContent = message || '';
  statusEl.dataset.tone = tone;
}

function clearOutput() {
  outputEl.innerHTML = '';
}

function clearSourcePreview() {
  if (!sourceFileEl || !sourceCodeEl) return;
  sourceFileEl.textContent = 'No source selected.';
  sourceCodeEl.textContent = 'Click a line label in the results to preview the source here.';
}

function setElementVisible(element, visible) {
  if (!element) return;
  element.hidden = !visible;
}

function updateClearButtonsVisibility() {
  setElementVisible(clearFilesButton, selectedFiles.length > 0);
  const hasCode = !!(codeInput && codeInput.value.length);
  setElementVisible(clearCodeButton, hasCode);
}

function clearCodeInput() {
  if (!codeInput) return;
  if (!codeInput.value) return;
  codeInput.value = '';
  codeInput.focus();
  updateClearButtonsVisibility();
  setStatus('Pasted code cleared.', 'neutral');
}

function clearSelectedFiles() {
  if (!selectedFiles.length) return;
  selectedFiles = [];
  renderFileList();
  setStatus('Selected files cleared.', 'neutral');
}

async function loadSourceContent(entry) {
  if (!entry) {
    return { ok: false, error: 'No result entry selected.' };
  }

  if (entry.is_pasted) {
    return { ok: true, key: '__pasted__', content: codeInput?.value || '' };
  }

  if (!entry.path) {
    return { ok: false, error: 'No source path available for this result.' };
  }

  if (sourceCache.has(entry.path)) {
    return { ok: true, key: entry.path, content: sourceCache.get(entry.path) };
  }

  if (!window.walker || typeof window.walker.readSource !== 'function') {
    return { ok: false, error: 'Source reader is unavailable.' };
  }

  const loaded = await window.walker.readSource(entry.path);
  if (!loaded || !loaded.ok) {
    return { ok: false, error: loaded?.error || 'Failed to load source file.' };
  }

  sourceCache.set(entry.path, loaded.content || '');
  return { ok: true, key: entry.path, content: loaded.content || '' };
}

function renderSourcePreview(entry, line, content) {
  if (!sourceFileEl || !sourceCodeEl) return;

  const name = entry?.file || 'unknown.cpp';
  const where = Number.isInteger(line) ? ` (line ${line})` : '';
  sourceFileEl.textContent = `${name}${where}`;

  const lines = String(content || '').split(/\r?\n/);
  sourceCodeEl.innerHTML = '';

  if (!lines.length) {
    sourceCodeEl.textContent = '[empty source]';
    return;
  }

  const frag = document.createDocumentFragment();
  lines.forEach((text, idx) => {
    const ln = idx + 1;
    const row = document.createElement('div');
    row.className = 'source-row';
    if (Number.isInteger(line) && ln === line) {
      row.classList.add('active');
    }

    const no = document.createElement('span');
    no.className = 'source-line-no';
    no.textContent = String(ln);

    const code = document.createElement('span');
    code.className = 'source-line-text';
    code.textContent = text.length ? text : ' ';

    row.appendChild(no);
    row.appendChild(code);
    frag.appendChild(row);
  });

  sourceCodeEl.appendChild(frag);

  if (Number.isInteger(line)) {
    const active = sourceCodeEl.querySelector('.source-row.active');
    if (active) {
      active.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }
}

async function openSourceAt(entry, line) {
  const loaded = await loadSourceContent(entry);
  if (!loaded.ok) {
    setStatus(loaded.error || 'Failed to load source preview.', 'error');
    return;
  }

  renderSourcePreview(entry, line, loaded.content);
}

function formatDuration(ms) {
  if (!Number.isFinite(ms) || ms < 0) return '0.00 s';
  const seconds = ms / 1000;
  if (seconds < 1) return `${seconds.toFixed(3)} s`;
  return `${seconds.toFixed(2)} s`;
}

function formatConfidence(value) {
  if (!Number.isFinite(value)) return null;
  return `${Math.round(value * 100)}%`;
}

function normalizeFiles(files) {
  const unique = new Set();
  files.forEach((file) => {
    if (isCppFile(file)) {
      unique.add(file);
    }
  });
  return Array.from(unique);
}

function getDroppedFilePath(file) {
  if (window.walker && typeof window.walker.getDroppedFilePath === 'function') {
    try {
      return window.walker.getDroppedFilePath(file) || '';
    } catch (_err) {
      // Fall back to legacy file.path below.
    }
  }

  if (file && typeof file.path === 'string') {
    return file.path;
  }

  return '';
}

function handleDrop(event) {
  event.preventDefault();
  dropZone.classList.remove('drag-active');
  const files = Array.from(event.dataTransfer.files || [])
    .map((f) => getDroppedFilePath(f))
    .filter(Boolean);
  if (!files.length) {
    setStatus('Could not read dropped file paths. Try Select Files.', 'error');
    return;
  }
  const accepted = files.filter(isCppFile);
  const rejected = files.length - accepted.length;
  if (rejected > 0) {
    setStatus(`Ignored ${rejected} non-C/C++ file(s).`, 'error');
  }
  if (!accepted.length) {
    return;
  }
  selectedFiles = normalizeFiles([...selectedFiles, ...accepted]);
  renderFileList();
}

function handleDrag(event) {
  event.preventDefault();
  dropZone.classList.add('drag-active');
}

function handleDragLeave(event) {
  event.preventDefault();
  if (event.target === dropZone) {
    dropZone.classList.remove('drag-active');
  }
}

async function pickFiles() {
  const result = await window.walker.selectFiles();
  if (!result || !result.ok) {
    setStatus(result?.error || 'Failed to open file picker.', 'error');
    return;
  }
  if (!result.files.length) {
    return;
  }
  const accepted = result.files.filter(isCppFile);
  const rejected = result.files.length - accepted.length;
  if (rejected > 0) {
    setStatus(`Ignored ${rejected} non-C/C++ file(s).`, 'error');
  }
  selectedFiles = normalizeFiles([...selectedFiles, ...accepted]);
  renderFileList();
}

function classifyFallback(message) {
  if (!message) return 'info';
  if (message.startsWith('[ERROR]') || message.startsWith('❌')) return 'error';
  if (message.startsWith('[WARN]') || message.startsWith('⚠')) return 'warning';
  return 'info';
}

function normalizeTopic(item) {
  return item.topic || 'other';
}

function applyFilters(items) {
  const severity = severityFilterEl?.value || 'all';
  const topic = topicFilterEl?.value || 'all';

  return items.filter((item) => {
    if (severity !== 'all' && item.severity !== severity) {
      return false;
    }
    if (topic !== 'all' && normalizeTopic(item) !== topic) {
      return false;
    }
    return true;
  });
}

function renderSection(title, tone, items, entry) {
  const section = document.createElement('details');
  section.className = `result-section ${tone}`;
  section.open = !collapseSections;

  const summary = document.createElement('summary');
  summary.textContent = `${title} (${items.length})`;
  section.appendChild(summary);

  const ul = document.createElement('ul');
  ul.className = 'result-list';

  items.forEach((item) => {
    const li = document.createElement('li');
    li.className = 'result-item';
    const message = document.createElement('div');
    message.className = 'result-item-message';
    if (Number.isInteger(item.line)) {
      const lineLink = document.createElement('button');
      lineLink.type = 'button';
      lineLink.className = 'result-line-link';
      lineLink.textContent = `line ${item.line}`;
      lineLink.addEventListener('click', async () => {
        await openSourceAt(entry, item.line);
      });
      message.appendChild(lineLink);

      const text = document.createElement('span');
      text.textContent = `: ${item.message}`;
      message.appendChild(text);
    } else {
      message.textContent = item.message;
    }
    li.appendChild(message);

    const confidence = formatConfidence(item.confidence);
    const topic = normalizeTopic(item);
    if (topic || confidence) {
      const meta = document.createElement('div');
      meta.className = 'result-item-meta';
      const parts = [];
      if (topic) parts.push(`Topic: ${topic}`);
      if (confidence) parts.push(`Confidence: ${confidence}`);
      meta.textContent = parts.join(' • ');
      li.appendChild(meta);
    }

    if (item.suggestion) {
      const suggestion = document.createElement('div');
      suggestion.className = 'result-item-suggestion';
      suggestion.textContent = `Suggested fix: ${item.suggestion}`;
      li.appendChild(suggestion);
    }

    ul.appendChild(li);
  });

  section.appendChild(ul);
  return section;
}

function renderTiming(entry, parent) {
  const timing = entry?.timing_ms;
  if (!timing) return;

  const timingRow = document.createElement('div');
  timingRow.className = 'result-timing';
  timingRow.innerHTML = `
    <span class="chip timing">Parse: ${formatDuration(timing.parse)}</span>
    <span class="chip timing">Traversal: ${formatDuration(timing.traversal)}</span>
    <span class="chip timing">Interpretation: ${formatDuration(timing.interpretation)}</span>
    <span class="chip timing">Total: ${formatDuration(timing.total)}</span>
  `;
  parent.appendChild(timingRow);
}

function renderResults(results) {
  latestResults = Array.isArray(results) ? results : [];
  outputEl.innerHTML = '';

  latestResults.forEach((entry) => {
    const fileBlock = document.createElement('article');
    fileBlock.className = 'result-file';

    const header = document.createElement('div');
    header.className = 'result-header';
    const file = document.createElement('h3');
    file.textContent = entry.file || 'unknown.cpp';
    header.appendChild(file);

    const items = itemsForEntry(entry);
    const visibleItems = visibleItemsForEntry(entry);

    const chips = document.createElement('div');
    chips.className = 'result-chips';
    chips.innerHTML = `
      <span class="chip error">Errors: ${visibleItems.filter((i) => i.severity === 'error').length}</span>
      <span class="chip warning">Warnings: ${visibleItems.filter((i) => i.severity === 'warning').length}</span>
      <span class="chip info">Info: ${visibleItems.filter((i) => i.severity !== 'error' && i.severity !== 'warning').length}</span>
    `;
    header.appendChild(chips);
    fileBlock.appendChild(header);
    renderTiming(entry, fileBlock);

    if (entry.ok === false) {
      const error = document.createElement('p');
      error.className = 'result-failure';
      error.textContent = entry.error || 'Failed to analyze file.';
      fileBlock.appendChild(error);
      outputEl.appendChild(fileBlock);
      return;
    }

    const errors = visibleItems.filter((i) => i.severity === 'error');
    const warnings = visibleItems.filter((i) => i.severity === 'warning');
    const info = visibleItems.filter((i) => i.severity !== 'error' && i.severity !== 'warning');

    if (errors.length) fileBlock.appendChild(renderSection('Errors', 'error', errors, entry));
    if (warnings.length) fileBlock.appendChild(renderSection('Warnings', 'warning', warnings, entry));
    if (info.length) fileBlock.appendChild(renderSection('Explanations', 'info', info, entry));

    if (items.length && !visibleItems.length) {
      const filtered = document.createElement('p');
      filtered.className = 'result-filter-note';
      filtered.textContent = 'No items match the current filters.';
      fileBlock.appendChild(filtered);
    }

    if (!items.length) {
      const empty = document.createElement('p');
      empty.textContent = 'No output generated.';
      fileBlock.appendChild(empty);
    }

    outputEl.appendChild(fileBlock);
  });

  updateOutputActionButtonsVisibility();
}

function itemsForEntry(entry) {
  return Array.isArray(entry.items) && entry.items.length
    ? entry.items
    : (entry.explanations || []).map((message) => ({ severity: classifyFallback(message), message }));
}

function visibleItemsForEntry(entry) {
  return applyFilters(itemsForEntry(entry));
}

function updateOutputActionButtonsVisibility() {
  const hasOutput = latestResults.some((entry) => {
    if (!entry) return false;
    if (entry.ok === false) return true;
    return itemsForEntry(entry).length > 0;
  });
  outputActionButtons.forEach((button) => setElementVisible(button, hasOutput));
}

function currentFilterState() {
  return {
    severity: severityFilterEl?.value || 'all',
    topic: topicFilterEl?.value || 'all',
  };
}

function collectExportResults() {
  return latestResults.map((entry) => {
    const items = visibleItemsForEntry(entry);
    const summary = {
      error: items.filter((i) => i.severity === 'error').length,
      warning: items.filter((i) => i.severity === 'warning').length,
      info: items.filter((i) => i.severity !== 'error' && i.severity !== 'warning').length,
      total: items.length,
    };

    return {
      file: entry.file,
      path: entry.path || null,
      is_pasted: !!entry.is_pasted,
      ok: entry.ok !== false,
      error: entry.error || null,
      timing_ms: entry.timing_ms || null,
      summary,
      items,
    };
  });
}

function buildJsonReport() {
  return {
    generatedAt: new Date().toISOString(),
    filters: currentFilterState(),
    results: collectExportResults(),
  };
}

function buildTextReport() {
  const lines = [];
  const generatedAt = new Date().toISOString();
  const filters = currentFilterState();
  lines.push(`Walker Report`);
  lines.push(`Generated: ${generatedAt}`);
  lines.push(`Filters: severity=${filters.severity}, topic=${filters.topic}`);
  lines.push('');

  collectExportResults().forEach((entry) => {
    lines.push(`=== ${entry.file || 'unknown.cpp'} ===`);
    if (entry.path) {
      lines.push(`Path: ${entry.path}`);
    }
    if (entry.ok === false) {
      lines.push(`Failed: ${entry.error || 'Unknown error'}`);
      lines.push('');
      return;
    }

    lines.push(
      `Summary: errors=${entry.summary.error}, warnings=${entry.summary.warning}, info=${entry.summary.info}, total=${entry.summary.total}`
    );
    if (entry.timing_ms) {
      lines.push(
        `Timing: parse=${formatDuration(entry.timing_ms.parse)}, traversal=${formatDuration(entry.timing_ms.traversal)}, interpretation=${formatDuration(entry.timing_ms.interpretation)}, total=${formatDuration(entry.timing_ms.total)}`
      );
    }
    lines.push('');

    entry.items.forEach((item) => {
      const line = Number.isInteger(item.line) ? `line ${item.line}: ` : '';
      lines.push(`[${item.severity.toUpperCase()}] ${line}${item.message}`);
      const topic = normalizeTopic(item);
      const confidence = formatConfidence(item.confidence);
      if (topic || confidence) {
        const parts = [];
        if (topic) parts.push(`topic=${topic}`);
        if (confidence) parts.push(`confidence=${confidence}`);
        lines.push(`  ${parts.join(', ')}`);
      }
      if (item.suggestion) {
        lines.push(`  suggestion: ${item.suggestion}`);
      }
    });
    lines.push('');
  });

  return lines.join('\n');
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function copyTextToClipboard(text) {
  if (!text) return false;

  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function' && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return true;
  }

  const temp = document.createElement('textarea');
  temp.value = text;
  temp.setAttribute('readonly', 'readonly');
  temp.style.position = 'fixed';
  temp.style.opacity = '0';
  temp.style.pointerEvents = 'none';
  document.body.appendChild(temp);
  temp.select();
  temp.setSelectionRange(0, temp.value.length);

  try {
    return document.execCommand('copy');
  } finally {
    temp.remove();
  }
}

async function copyAllOutput() {
  if (!latestResults.length) {
    setStatus('Run analysis first before copying output.', 'error');
    return;
  }

  const report = buildTextReport();
  try {
    const copied = await copyTextToClipboard(report);
    if (!copied) {
      setStatus('Could not copy output to clipboard.', 'error');
      return;
    }
    setStatus('Copied output to clipboard.', 'success');
  } catch (_err) {
    setStatus('Could not copy output to clipboard.', 'error');
  }
}

function printAllOutput() {
  if (!latestResults.length) {
    setStatus('Run analysis first before printing output.', 'error');
    return;
  }

  const report = buildTextReport();
  const printFrame = document.createElement('iframe');
  printFrame.style.position = 'fixed';
  printFrame.style.width = '0';
  printFrame.style.height = '0';
  printFrame.style.border = '0';
  printFrame.style.right = '0';
  printFrame.style.bottom = '0';
  printFrame.style.visibility = 'hidden';
  document.body.appendChild(printFrame);

  const frameWindow = printFrame.contentWindow;
  if (!frameWindow) {
    printFrame.remove();
    setStatus('Could not open print dialog.', 'error');
    return;
  }

  const doc = frameWindow.document;
  doc.open();
  doc.write(`<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Walker Report</title>
    <style>
      @page { size: auto; margin: 12mm; }
      body { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #111; background: #fff; }
      h1 { margin: 0 0 12px; font-size: 18px; }
      pre { white-space: pre-wrap; line-height: 1.4; font-size: 12px; margin: 0; }
    </style>
  </head>
  <body>
    <h1>Walker Report</h1>
    <pre>${escapeHtml(report)}</pre>
  </body>
</html>`);
  doc.close();

  setTimeout(() => {
    try {
      frameWindow.focus();
      frameWindow.print();
      setStatus('Print dialog opened.', 'success');
    } catch (_err) {
      setStatus('Could not open print dialog.', 'error');
    } finally {
      setTimeout(() => printFrame.remove(), 250);
    }
  }, 75);
}

async function exportReport(format) {
  if (!latestResults.length) {
    setStatus('Run analysis first before exporting.', 'error');
    return;
  }
  if (!window.walker || typeof window.walker.exportReport !== 'function') {
    setStatus('Export is unavailable in this environment.', 'error');
    return;
  }

  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const isJson = format === 'json';
  const content = isJson ? JSON.stringify(buildJsonReport(), null, 2) : buildTextReport();
  const defaultName = `walker-report-${stamp}.${isJson ? 'json' : 'txt'}`;

  const result = await window.walker.exportReport({
    format: isJson ? 'json' : 'txt',
    defaultName,
    content,
  });

  if (!result || !result.ok) {
    const err = result?.error || 'Failed to export report.';
    if (err !== 'Export canceled.') {
      setStatus(err, 'error');
    }
    return;
  }

  setStatus(`Report exported to ${result.path}`, 'success');
}

function updateToggleButton() {
  if (!toggleSectionsButton) return;
  toggleSectionsButton.textContent = collapseSections ? 'Expand Sections' : 'Collapse Sections';
}

async function runAnalysis() {
  const startedAt = performance.now();
  setStatus('Running analysis...', 'neutral');
  latestResults = [];
  updateOutputActionButtonsVisibility();
  clearOutput();
  clearSourcePreview();
  sourceCache.clear();

  const code = codeInput.value;
  const payload = {
    files: selectedFiles,
    code,
  };

  const result = await window.walker.runAnalysis(payload);
  if (!result.ok) {
    latestResults = [];
    updateOutputActionButtonsVisibility();
    const elapsed = formatDuration(performance.now() - startedAt);
    setStatus(`${result.error || 'Failed to run analysis.'} (${elapsed})`, 'error');
    if (result.stdout) {
      outputEl.textContent = result.stdout;
    }
    return;
  }

  const data = result.data;
  const results = data?.results || [];
  if (!results.length) {
    latestResults = [];
    updateOutputActionButtonsVisibility();
    const elapsed = formatDuration(performance.now() - startedAt);
    setStatus(`No results returned. (${elapsed})`, 'error');
    clearOutput();
    return;
  }

  renderResults(results);
  const elapsed = formatDuration(performance.now() - startedAt);
  setStatus(`Analysis complete in ${elapsed}.`, 'success');
}

if (dropZone) {
  dropZone.addEventListener('drop', handleDrop);
  dropZone.addEventListener('dragover', handleDrag);
  dropZone.addEventListener('dragenter', handleDrag);
  dropZone.addEventListener('dragleave', handleDragLeave);
}

if (severityFilterEl) {
  severityFilterEl.addEventListener('change', () => {
    renderResults(latestResults);
  });
}

if (topicFilterEl) {
  topicFilterEl.addEventListener('change', () => {
    renderResults(latestResults);
  });
}

if (codeInput) {
  codeInput.addEventListener('input', () => {
    updateClearButtonsVisibility();
  });
}

if (toggleSectionsButton) {
  toggleSectionsButton.addEventListener('click', () => {
    collapseSections = !collapseSections;
    updateToggleButton();
    renderResults(latestResults);
  });
}

if (exportJsonButton) {
  exportJsonButton.addEventListener('click', async () => {
    await exportReport('json');
  });
}

if (exportTextButton) {
  exportTextButton.addEventListener('click', async () => {
    await exportReport('txt');
  });
}

if (copyAllButton) {
  copyAllButton.addEventListener('click', async () => {
    await copyAllOutput();
  });
}

if (printAllButton) {
  printAllButton.addEventListener('click', () => {
    printAllOutput();
  });
}

if (clearCodeButton) {
  clearCodeButton.addEventListener('click', () => {
    clearCodeInput();
  });
}

if (clearFilesButton) {
  clearFilesButton.addEventListener('click', () => {
    clearSelectedFiles();
  });
}

pickButton.addEventListener('click', pickFiles);
runButton.addEventListener('click', runAnalysis);

// Prevent browser from navigating away when files are dropped outside the dropzone.
window.addEventListener('dragover', (event) => event.preventDefault());
window.addEventListener('drop', (event) => {
  event.preventDefault();
  if (dropZone) {
    dropZone.classList.remove('drag-active');
  }
});

updateToggleButton();
clearSourcePreview();
renderFileList();
updateOutputActionButtonsVisibility();
