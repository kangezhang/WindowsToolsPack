import { spawnSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const mode = process.argv[2] === 'pack' ? 'pack' : 'dist'
const stamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 12)
const outputDir = join('dist-installer', `build-${stamp}`)
const bin = process.platform === 'win32'
  ? join('node_modules', '.bin', 'electron-builder.cmd')
  : join('node_modules', '.bin', 'electron-builder')

mkdirSync(outputDir, { recursive: true })

const args = [`--config.directories.output=${outputDir}`]
if (mode === 'pack') {
  args.push('--dir')
}

const result = spawnSync(bin, args, {
  stdio: 'inherit',
  shell: process.platform === 'win32',
  env: {
    ...process.env,
    CSC_IDENTITY_AUTO_DISCOVERY: 'false',
  },
})

if (result.error) {
  console.error(result.error)
}

process.exit(result.status ?? 1)
