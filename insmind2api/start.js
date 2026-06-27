// insmind2api wrapper - suppress stdin is not a tty
const cp = require('child_process');
const p = cp.spawn(process.execPath, [require('path').join(__dirname, 'dist/index.js')], {
    stdio: ['pipe', 'inherit', 'inherit'],
    cwd: __dirname,
});
p.on('exit', (code) => process.exit(code));
p.stdin.end();
