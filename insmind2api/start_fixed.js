/**
 * insmind2api wrapper - isolates stdin to prevent "stdin is not a tty" crash
 * when running in background / non-interactive sessions.
 * 
 * Usage: node start_fixed.js
 */
const { spawn } = require('child_process');
const path = require('path');

const child = spawn(process.execPath, [path.join(__dirname, 'dist', 'index.js')], {
    cwd: __dirname,
    stdio: ['ignore', 'inherit', 'inherit'],
    windowsHide: true,
});

child.on('exit', (code, signal) => {
    if (code !== 0) {
        console.error(`insmind2api exited with code ${code} signal ${signal}`);
    }
    process.exit(code ?? 0);
});

process.on('SIGTERM', () => child.kill('SIGTERM'));
process.on('SIGINT', () => child.kill('SIGINT'));
