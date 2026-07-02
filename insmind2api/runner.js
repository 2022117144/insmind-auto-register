const { spawn } = require('child_process');
const path = require('path');

const child = spawn(process.execPath, [path.join(__dirname, 'dist/index.js')], {
    stdio: ['ignore', 'inherit', 'inherit'],
    cwd: __dirname,
});

child.on('exit', (code, signal) => {
    if (code !== 0 && code !== null) {
        console.error(`insmind2api exited with code ${code} signal ${signal}`);
    }
});
