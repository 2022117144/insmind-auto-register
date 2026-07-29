/**
 * insmind2api 带日志的启动器
 * 把 stdout/stderr 写入日志文件，崩溃时可以看到原因
 * 并自动重启。detached 模式，shell 退出后进程独立存活。
 */
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const scriptPath = path.join(__dirname, 'dist', 'index.js');
const logDir = path.join(__dirname, 'logs');

// 确保日志目录存在
if (!fs.existsSync(logDir)) {
    fs.mkdirSync(logDir, { recursive: true });
}

const logFile = path.join(logDir, `server.log`);
const logStream = fs.createWriteStream(logFile, { flags: 'a' });

function start() {
    const child = spawn(process.execPath, [scriptPath], {
        cwd: __dirname,
        stdio: ['ignore', 'pipe', 'pipe'],
        detached: true,
        windowsHide: true,
    });

    child.stdout.pipe(logStream);
    child.stderr.pipe(logStream);
    child.unref();

    const ts = new Date().toISOString();
    logStream.write(`\n=== [${ts}] insmind2api started (PID ${child.pid}) ===\n`);
    console.log(`insmind2api started (PID ${child.pid}), logging to ${logFile}`);

    child.on('exit', (code, signal) => {
        const ts2 = new Date().toISOString();
        const msg = `[${ts2}] insmind2api exited: code=${code} signal=${signal}`;
        logStream.write(`${msg}\n`);
        console.error(msg);

        // 自动重启（非正常退出时）
        if (code !== 0 || signal) {
            console.log('Restarting in 3 seconds...');
            setTimeout(start, 3000);
        }
    });

    child.on('error', (err) => {
        const ts3 = new Date().toISOString();
        logStream.write(`[${ts3}] insmind2api error: ${err.message}\n`);
        console.error(`insmind2api error: ${err.message}`);
    });
}

start();