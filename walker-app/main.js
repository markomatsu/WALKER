const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');

const APP_ROOT = __dirname;
const DEFAULT_WORKSPACE_ROOT = path.resolve(APP_ROOT, '..', 'walker');
const DEFAULT_PY = process.platform === 'win32'
  ? path.join(DEFAULT_WORKSPACE_ROOT, '.venv', 'Scripts', 'python.exe')
  : path.join(DEFAULT_WORKSPACE_ROOT, '.venv', 'bin', 'python');
const DEFAULT_SCRIPT = path.join(DEFAULT_WORKSPACE_ROOT, 'test_engine.py');
const allowedSourcePaths = new Set();

function normalizeExistingPath(candidatePath) {
  if (!candidatePath || typeof candidatePath !== 'string') {
    return null;
  }
  try {
    const resolved = path.resolve(candidatePath);
    return fs.realpathSync(resolved);
  } catch (_err) {
    return null;
  }
}

function refreshAllowedSourcePaths(fileArgs, tempFile) {
  allowedSourcePaths.clear();
  const tempReal = normalizeExistingPath(tempFile);
  fileArgs.forEach((filePath) => {
    const normalized = normalizeExistingPath(filePath);
    if (!normalized) return;
    if (tempReal && normalized === tempReal) return;
    allowedSourcePaths.add(normalized);
  });
}

function mergeAllowedSourcePathsFromResults(parsed) {
  const entries = Array.isArray(parsed?.results) ? parsed.results : [];
  entries.forEach((entry) => {
    const normalized = normalizeExistingPath(entry?.path);
    if (normalized) {
      allowedSourcePaths.add(normalized);
    }
  });
}

function getBackendCommand() {
  if (app.isPackaged) {
    const backendRoot = path.join(process.resourcesPath, 'backend');
    const exeName = process.platform === 'win32' ? 'walker-backend.exe' : 'walker-backend';
    const backendDir = path.join(backendRoot, 'walker-backend');
    const backendPath = path.join(backendDir, exeName);
    const libclangName = process.platform === 'win32' ? 'libclang.dll' : 'libclang.dylib';
    const pathPrefix = process.platform === 'win32'
      ? `${backendDir};${process.env.PATH || ''}`
      : process.env.PATH;
    const env = {
      ...process.env,
      LIBCLANG_FILE: path.join(backendDir, libclangName),
      DYLD_LIBRARY_PATH: backendDir,
      PATH: pathPrefix,
    };
    return {
      command: backendPath,
      args: [],
      cwd: backendDir,
      env,
    };
  }

  const scriptPath = process.env.WALKER_SCRIPT || DEFAULT_SCRIPT;
  let pythonPath = process.env.WALKER_PY || DEFAULT_PY;
  if (!fs.existsSync(pythonPath)) {
    pythonPath = 'python3';
  }
  return {
    command: pythonPath,
    args: [scriptPath],
    cwd: path.dirname(scriptPath),
    env: process.env,
  };
}

function createWindow(options = {}) {
  const { show = true } = options;
  const win = new BrowserWindow({
    width: 1100,
    height: 720,
    minWidth: 900,
    minHeight: 600,
    show,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadFile(path.join(__dirname, 'index.html'));
  return win;
}

async function runLinePreviewE2ETest() {
  const win = createWindow({ show: false });

  try {
    const result = await win.webContents.executeJavaScript(`
      (async () => {
        const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

        const codeInput = document.querySelector('[data-code]');
        const runButton = document.querySelector('[data-run]');
        if (!codeInput || !runButton) {
          return { ok: false, error: 'UI controls not found.' };
        }

        codeInput.value = [
          '#include <iostream>',
          'using namespace std;',
          '',
          'int main() {',
          '  int x = 0;',
          '  cout << "Grade: ";',
          '  cin >> x;',
          '  if (x > 1) {',
          '    cout << "ok";',
          '  }',
          '  return 0;',
          '}',
        ].join('\\n');

        runButton.click();

        const deadline = Date.now() + 30000;
        let lineButton = null;
        while (Date.now() < deadline) {
          lineButton = document.querySelector('.result-line-link');
          const failure = document.querySelector('.result-failure');
          if (lineButton) break;
          if (failure) {
            return { ok: false, error: 'Analysis failed: ' + failure.textContent };
          }
          await sleep(200);
        }

        if (!lineButton) {
          return { ok: false, error: 'Timed out waiting for line links.' };
        }

        lineButton.click();
        await sleep(300);

        const activeRow = document.querySelector('.source-row.active');
        if (!activeRow) {
          return { ok: false, error: 'No highlighted source row after clicking a line label.' };
        }

        const sourceFile = document.querySelector('[data-source-file]')?.textContent || '';
        const lineNo = activeRow.querySelector('.source-line-no')?.textContent || '';
        if (!sourceFile || sourceFile.includes('No source selected')) {
          return { ok: false, error: 'Source preview header was not updated.' };
        }

        return { ok: true, sourceFile, lineNo };
      })();
    `);

    if (!result || !result.ok) {
      const message = result?.error || 'Unknown E2E test failure.';
      console.error('[E2E] line-preview FAILED:', message);
      app.exit(1);
      return;
    }

    console.log('[E2E] line-preview PASSED:', result);
    app.exit(0);
  } catch (err) {
    console.error('[E2E] line-preview FAILED:', err?.message || err);
    app.exit(1);
  }
}

app.whenReady().then(() => {
  if (process.env.WALKER_E2E_LINE_PREVIEW === '1') {
    runLinePreviewE2ETest();
    return;
  }

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

ipcMain.handle('run-analysis', async (_event, payload) => {
  const { files, code, ruleGroups } = payload || {};
  const backend = getBackendCommand();

  if (!fs.existsSync(backend.command)) {
    return { ok: false, error: `Backend not found at ${backend.command}` };
  }

  let tempFile = null;
  const fileArgs = Array.isArray(files) ? files.filter(Boolean) : [];

  if (code && code.trim()) {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'walker-'));
    tempFile = path.join(tmpDir, 'pasted_input.cpp');
    fs.writeFileSync(tempFile, code, 'utf-8');
    fileArgs.push(tempFile);
  }

  if (!fileArgs.length) {
    return { ok: false, error: 'No files or code provided.' };
  }
  refreshAllowedSourcePaths(fileArgs, tempFile);

  return await new Promise((resolve) => {
    const spawnArgs = [...backend.args];
    if (Array.isArray(ruleGroups) && ruleGroups.length) {
      spawnArgs.push('--groups', ruleGroups.join(','));
    }
    spawnArgs.push(...fileArgs);

    const child = spawn(backend.command, spawnArgs, {
      cwd: backend.cwd,
      env: backend.env,
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    child.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    child.on('close', (code) => {
      if (tempFile) {
        try {
          fs.unlinkSync(tempFile);
        } catch (err) {
          // ignore cleanup errors
        }
      }

      const rawOut = stdout.trim();

      if (code !== 0) {
        const message = stderr.trim() || `Process exited with code ${code}`;
        resolve({ ok: false, error: message, stdout: rawOut });
        return;
      }

      if (!rawOut) {
        resolve({ ok: false, error: 'No output from backend.' });
        return;
      }

      try {
        const parsed = JSON.parse(rawOut);
        if (!parsed || parsed.ok === false) {
          resolve({
            ok: false,
            error: parsed?.error || 'Backend reported an error.',
            data: parsed || null,
          });
          return;
        }
        mergeAllowedSourcePathsFromResults(parsed);
        resolve({ ok: true, data: parsed });
      } catch (err) {
        resolve({
          ok: false,
          error: 'Failed to parse backend JSON.',
          stdout: rawOut,
        });
      }
    });
  });
});

ipcMain.handle('select-files', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openFile', 'multiSelections'],
    filters: [{ name: 'C++ Files', extensions: ['cpp', 'cc', 'cxx', 'h', 'hpp'] }],
  });

  if (result.canceled) {
    return { ok: true, files: [] };
  }

  return { ok: true, files: result.filePaths };
});

ipcMain.handle('read-source', async (_event, payload) => {
  const sourcePath = payload?.path;
  if (!sourcePath || typeof sourcePath !== 'string') {
    return { ok: false, error: 'No source path provided.' };
  }

  const resolved = normalizeExistingPath(sourcePath);
  if (!resolved) {
    return { ok: false, error: 'Source file does not exist.' };
  }
  if (!allowedSourcePaths.has(resolved)) {
    return { ok: false, error: 'Source path is not allowed. Analyze this file first.' };
  }

  try {
    const content = await fs.promises.readFile(resolved, 'utf-8');
    return { ok: true, path: resolved, content };
  } catch (_err) {
    return { ok: false, error: `Failed to read source file: ${resolved}` };
  }
});

ipcMain.handle('export-report', async (_event, payload) => {
  const format = payload?.format === 'json' ? 'json' : 'txt';
  const content = typeof payload?.content === 'string' ? payload.content : '';
  const defaultName = typeof payload?.defaultName === 'string' ? payload.defaultName : `walker-report.${format}`;

  if (!content) {
    return { ok: false, error: 'No report content to export.' };
  }

  const saveResult = await dialog.showSaveDialog({
    defaultPath: defaultName,
    filters: [
      { name: 'JSON Files', extensions: ['json'] },
      { name: 'Text Files', extensions: ['txt'] },
      { name: 'All Files', extensions: ['*'] },
    ],
  });

  if (saveResult.canceled || !saveResult.filePath) {
    return { ok: false, error: 'Export canceled.' };
  }

  try {
    await fs.promises.writeFile(saveResult.filePath, content, 'utf-8');
    return { ok: true, path: saveResult.filePath };
  } catch (_err) {
    return { ok: false, error: `Failed to write report: ${saveResult.filePath}` };
  }
});
