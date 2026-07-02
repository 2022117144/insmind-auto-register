const { spawn } = require('child_process');
const path = require('path');

const nodeExe = process.execPath;
const scriptPath = path.join(__dirname, 'dist', 'index.js');
const logFile = path.join(__dirname, 'logs', 'server.log');

const fs = require('fs');
const logStream = fs.createWriteStream(logFile, { flags: 'a' });

const child = spawn(nodeExe, [scriptPath], {
    cwd: __dirname,
    stdio: ['ignore', logStream, logStream],
    detached: true,
});

child.unref();

console.log(`insmind2api started (PID ${child.pid}), logging to ${logFile}`);
process.exit(0);
