/**
 * Python FastAPI 子进程管理
 * - 启动时随机选取空闲端口
 * - 生成本地 token
 * - 监听 TOOLPACK_READY 信号完成健康检查
 * - 退出时优雅终止
 */

const { spawn } = require('child_process')
const path      = require('path')
const net       = require('net')
const crypto    = require('crypto')
const { app }   = require('electron')

let pyProcess   = null
let _port       = null
let _token      = null

/** 随机找一个可用 TCP 端口 */
function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer()
    srv.listen(0, '127.0.0.1', () => {
      const port = srv.address().port
      srv.close(() => resolve(port))
    })
    srv.on('error', reject)
  })
}

/** 等待后端就绪（最多 timeout ms） */
function waitForReady(port, token, timeout = 15000) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeout
    const http = require('http')

    function poll() {
      const req = http.get(
        { hostname: '127.0.0.1', port, path: '/api/system/info', timeout: 2000,
          headers: { 'X-Local-Token': token } },
        (res) => {
          if (res.statusCode === 200) {
            resolve()
          } else {
            retry()
          }
          res.resume()
        }
      )
      req.on('error', retry)
      req.on('timeout', () => { req.destroy(); retry() })
    }

    function retry() {
      if (Date.now() >= deadline) {
        reject(new Error('Python 后端启动超时'))
      } else {
        setTimeout(poll, 600)
      }
    }

    poll()
  })
}

/**
 * 启动 Python 后端
 * @returns {{ port: number, token: string }}
 */
async function startPythonBackend() {
  const port  = await findFreePort()
  const token = crypto.randomBytes(24).toString('hex')
  _port  = port
  _token = token

  // 生产环境：backend.exe 紧邻 Electron 可执行文件
  // 开发环境：直接用 python / uvicorn
  let pythonExe, args
  const isDev = !app.isPackaged

  if (isDev) {
    // 开发模式：项目根目录下的 backend/main.py
    const backendDir = path.join(__dirname, '..', 'backend')
    pythonExe = process.platform === 'win32' ? 'python' : 'python3'
    args = ['-m', 'uvicorn', 'main:app', '--port', String(port), '--host', '127.0.0.1']
    console.log(`[PythonBridge] Dev mode — cwd: ${backendDir}`)
    pyProcess = spawn(pythonExe, args, {
      cwd: backendDir,
      env: {
        ...process.env,
        TOOLPACK_PORT:  String(port),
        TOOLPACK_TOKEN: token,
        PYTHONUNBUFFERED: '1',
      },
    })
  } else {
    // 生产模式：resources/backend.exe
    const exePath = path.join(process.resourcesPath, 'backend.exe')
    pyProcess = spawn(exePath, [], {
      env: {
        ...process.env,
        TOOLPACK_PORT:  String(port),
        TOOLPACK_TOKEN: token,
      },
    })
  }

  pyProcess.stdout.on('data', (d) => process.stdout.write(`[Python] ${d}`))
  pyProcess.stderr.on('data', (d) => process.stderr.write(`[Python ERR] ${d}`))

  pyProcess.on('exit', (code, signal) => {
    console.log(`[PythonBridge] process exited code=${code} signal=${signal}`)
    pyProcess = null
  })

  await waitForReady(port, token)
  console.log(`[PythonBridge] Backend ready on port ${port}`)
  return { port, token }
}

/** 优雅停止 Python 进程 */
function stopPythonBackend() {
  if (!pyProcess) return
  const pid = pyProcess.pid
  console.log(`[PythonBridge] Stopping Python backend… pid=${pid}`)
  pyProcess = null

  if (process.platform === 'win32') {
    // Windows：SIGTERM/SIGKILL 对 .exe 无效，改用 taskkill /F /T 杀掉整个进程树
    const { execSync } = require('child_process')
    try {
      execSync(`taskkill /F /T /PID ${pid}`, { stdio: 'ignore' })
    } catch {
      // 进程可能已退出，忽略错误
    }
  } else {
    try { process.kill(-pid, 'SIGKILL') } catch { /* 已退出 */ }
  }
}

function getPort()  { return _port  }
function getToken() { return _token }

module.exports = { startPythonBackend, stopPythonBackend, getPort, getToken }
