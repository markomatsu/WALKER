const { spawn } = require('child_process');
const path = require('path');
const electronBinary = require('electron');

const appRoot = path.resolve(__dirname, '..');

const child = spawn(electronBinary, ['.'], {
  cwd: appRoot,
  env: {
    ...process.env,
    WALKER_E2E_LINE_PREVIEW: '1',
  },
  stdio: 'inherit',
});

child.on('exit', (code) => {
  if (code !== 0) {
    console.error(`[E2E] line-preview exited with code ${code}`);
  }
  process.exit(code ?? 1);
});

child.on('error', (err) => {
  console.error('[E2E] Failed to start Electron:', err.message || err);
  process.exit(1);
});
