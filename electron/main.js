const { app, BrowserWindow, ipcMain, shell } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const fs = require('fs')
const http = require('http')

const BACKEND_PORT = 8005
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`
const NODE_PORT = 5105
const NODE_URL = `http://localhost:${NODE_PORT}`

let mainWindow = null
let setupWindow = null
let pythonProcess = null
let nodeProcess = null
let dataPath = ''
let proxyConfig = { host: '127.0.0.1', port: '7897' } // defaults

// ── File logger (don't rely on stdout — avoids EPIPE crashes) ─────

let log = null // initialized in app.whenReady() after dataPath is known

function initLogger() {
  const logDir = path.join(dataPath, 'logs')
  if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true })
  const logFile = path.join(logDir, 'electron-main.log')

  const logger = (level, ...args) => {
    const ts = new Date().toISOString()
    const msg = args.map(a => (typeof a === 'object' ? JSON.stringify(a) : String(a))).join(' ')
    const line = `[${ts}] [${level}] ${msg}\n`
    try {
      fs.appendFileSync(logFile, line, 'utf-8')
    } catch (_) {}
  }
  log = {
    info: (...args) => logger('INFO', ...args),
    error: (...args) => logger('ERROR', ...args),
    warn: (...args) => logger('WARN', ...args),
  }
}

// ── Uncaught exception guard (EPIPE → log silently) ──────────────

process.on('uncaughtException', (err) => {
  if (err.code === 'EPIPE' || err.message.includes('EPIPE')) {
    if (log) log.warn('Suppressed EPIPE (broken stdout):', err.message)
    return
  }
  // Let other uncaught exceptions show the dialog (still log them)
  if (log) log.error('Uncaught exception:', err.stack || err.message)
  console.error(err)
})

// ── Data path ────────────────────────────────────────────────────
// 安装版：数据放安装目录下（用户选哪数据就跟到哪）
// 开发版：数据放 backend/ 下

async function ensureDataPath() {
  if (app.isPackaged) {
    dataPath = path.dirname(app.getPath('exe'))
  } else {
    dataPath = path.join(__dirname, '..', 'backend')
  }
  const dirs = ['data', 'logs', 'data/screenshots', 'data/browser_states', 'downloads', 'images']
  dirs.forEach(d => {
    const p = path.join(dataPath, d)
    if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true })
  })
}

// ── Path resolution ──────────────────────────────────────────────

function backendDir() {
  if (app.isPackaged) return path.join(process.resourcesPath, 'backend')
  return path.join(__dirname, '..', 'backend')
}

function insmind2apiDir() {
  if (app.isPackaged) return path.join(process.resourcesPath, 'insmind2api')
  return path.join(__dirname, '..', 'insmind2api')
}

function findPythonPath() {
  // 打包模式：使用 PyInstaller 编译后的独立 exe
  if (app.isPackaged) {
    const backendExe = path.join(backendDir(), 'insmind-backend.exe')
    if (fs.existsSync(backendExe)) return backendExe
  }
  // 开发模式：使用 venv
  const venv = path.join(backendDir(), '.venv', 'Scripts', 'python.exe')
  if (fs.existsSync(venv)) return venv
  return 'python'
}

function findNodePath() {
  const candidates = [
    'C:\\Program Files\\nodejs\\node.exe',
    'C:\\Program Files (x86)\\nodejs\\node.exe',
    path.join(process.resourcesPath, '..', '..', '..', 'e', 'uni', 'node.exe'),
    'node',
  ]
  for (const c of candidates) {
    if (c === 'node') return 'node'
    try { if (fs.existsSync(c)) return c } catch (_) {}
  }
  return 'node'
}

// ── Proxy config ──────────────────────────────────────────────

function loadProxyConfig() {
  const configPath = path.join(dataPath, 'proxy-config.json')
  try {
    if (fs.existsSync(configPath)) {
      const raw = fs.readFileSync(configPath, 'utf-8')
      const cfg = JSON.parse(raw)
      if (cfg.host && cfg.host.trim()) {
        proxyConfig = { host: cfg.host.trim(), port: (cfg.port || '7897').trim() }
        log.info(`Loaded proxy config: ${proxyConfig.host}:${proxyConfig.port}`)
      }
    }
  } catch (e) {
    log.warn(`Failed to load proxy config: ${e.message}`)
  }
}

function proxyUrl() {
  if (!proxyConfig || !proxyConfig.host) return null
  return `http://${proxyConfig.host}:${proxyConfig.port}`
}

// ── Backend lifecycle ────────────────────────────────────────────

function startBackend() {
  killPort(BACKEND_PORT) // 清掉占坑的旧进程
  const pythonPath = findPythonPath()
  const cwd = backendDir()
  log.info(`Data path: ${dataPath}`)
  const isBackendExe = pythonPath.endsWith('insmind-backend.exe')
  log.info(`Starting Python backend: ${pythonPath} ${isBackendExe ? '' : 'run.py'}`)

  pythonProcess = spawn(pythonPath, isBackendExe ? ['--port', String(BACKEND_PORT)] : ['run.py'], {
      cwd, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env, PYTHONUNBUFFERED: '1',
        DATABASE_URL: `sqlite+aiosqlite:///${path.join(dataPath, 'data', 'dreamina.db').replace(/\\/g, '/')}`,
        data_dir: path.join(dataPath, 'data').replace(/\\/g, '/'),
        logs_dir: path.join(dataPath, 'logs').replace(/\\/g, '/'),
        ext_proxy_file_path: path.join(dataPath, 'proxies.txt').replace(/\\/g, '/'),
        HTTP_PROXY: proxyUrl() || process.env.HTTP_PROXY || '',
        HTTPS_PROXY: proxyUrl() || process.env.HTTPS_PROXY || '',
      },
    })

  pythonProcess.stdout.on('data', (d) => log.info(`[backend] ${d}`))
  pythonProcess.stderr.on('data', (d) => log.warn(`[backend] ${d}`))
  pythonProcess.on('exit', (code) => { pythonProcess = null; log.info(`Python backend exited (code=${code})`) })
}

function waitForBackend(retries = 30) {
  return new Promise((resolve, reject) => {
    let attempt = 0
    const check = () => {
      attempt++
      http.get(`${BACKEND_URL}/`, (res) => { res.resume(); resolve() })
        .on('error', () => {
          if (attempt >= retries) reject(new Error(`Backend didn't start after ${retries}s`))
          else setTimeout(check, 1000)
        })
    }
    check()
  })
}

function killPort(port) {
  try {
    const { execSync } = require('child_process')
    // netstat 找 PID → taskkill，比 PowerShell 快得多，不会超时残留
    const out = execSync(`netstat -ano | findstr "LISTENING" | findstr ":${port} "`, { timeout: 2000, windowsHide: true, encoding: 'utf-8' })
    const lines = out.trim().split('\n')
    for (const line of lines) {
      const parts = line.trim().split(/\s+/)
      const pid = parts[parts.length - 1]
      if (pid && pid !== '0') {
        execSync(`taskkill /f /pid ${pid}`, { timeout: 2000, windowsHide: true })
        if (log) log.info(`Killed stale process ${pid} on port ${port}`)
      }
    }
  } catch (_) {}
}

function startNodeService() {
  killPort(NODE_PORT)
    const nodePath = findNodePath()
    const cwd = insmind2apiDir()
    log.info(`Starting Node insmind2api: ${nodePath} dist/index.js`)

    // 传代理给 Node 子进程（insmind2api 的 sseFetch 通过 fetch() 走代理）
    const proxyEnv = {}
        const pUrl = proxyUrl()
        if (pUrl) {
          proxyEnv.HTTP_PROXY = pUrl
          proxyEnv.HTTPS_PROXY = pUrl
        }

    nodeProcess = spawn(nodePath, ['dist/index.js'], {
      cwd, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, ...proxyEnv },
    })
  nodeProcess.stdout.on('data', (d) => log.info(`[insmind2api] ${d}`))
  nodeProcess.stderr.on('data', (d) => log.warn(`[insmind2api] ${d}`))
  nodeProcess.on('exit', (code) => { nodeProcess = null; log.info(`Node insmind2api exited (code=${code})`) })
}

function waitForNodeService(retries = 20) {
  return new Promise((resolve) => {
    let attempt = 0
    const check = () => {
      attempt++
      http.get(`${NODE_URL}/api/accounts`, (res) => { res.resume(); resolve() })
        .on('error', () => {
          if (attempt >= retries) { resolve() }
          else setTimeout(check, 1000)
        })
    }
    check()
  })
}

// ── Window ───────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400, height: 900, minWidth: 1000, minHeight: 700,
    title: 'insMind Desktop',
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false },
    show: false,
  })

  mainWindow.webContents.session.on('will-download', (event, item) => {
    const downloadPath = path.join(dataPath, 'downloads')
    if (!fs.existsSync(downloadPath)) fs.mkdirSync(downloadPath, { recursive: true })
    item.setSavePath(path.join(downloadPath, item.getFilename()))
  })

  mainWindow.loadURL(BACKEND_URL)
    mainWindow.once('ready-to-show', () => mainWindow.show())
    mainWindow.on('closed', () => { mainWindow = null })
    // 点 X 关窗口时彻底退出 app（杀掉子进程）
    mainWindow.on('close', () => app.quit())
  }

// ── IPC handlers ─────────────────────────────────────────────────

ipcMain.handle('get-data-path', () => dataPath)
ipcMain.handle('open-data-path', () => shell.openPath(dataPath))

// ── App lifecycle ────────────────────────────────────────────────

app.whenReady().then(async () => {
  await ensureDataPath()
  initLogger()
  loadProxyConfig() // 读取 NSIS 安装器写入的代理配置
  startBackend()
  try {
    await waitForBackend()
    startNodeService()
    await waitForNodeService()
    createWindow()
  } catch (e) {
    log.error(e.message)
    app.quit()
  }
})

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
app.on('will-quit', () => {
  if (pythonProcess) { pythonProcess.kill(); pythonProcess = null }
  if (nodeProcess) { nodeProcess.kill(); nodeProcess = null }
})
app.on('activate', () => { if (!mainWindow) createWindow() })