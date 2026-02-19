const { platform } = require('os');
const { spawnSync } = require('child_process');

if (platform() !== 'darwin') {
  console.log('Skipping xattr cleanup (non-macOS).');
  process.exit(0);
}

const result = spawnSync('xattr', ['-cr', '.'], { stdio: 'inherit' });
if (result.error) {
  console.error(`xattr cleanup failed: ${result.error.message}`);
  process.exit(1);
}

process.exit(result.status ?? 1);
