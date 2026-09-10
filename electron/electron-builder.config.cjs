const { execFileSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const packageMetadata = require('./package.json')
const electronVersion = packageMetadata.devDependencies.electron
const electronArtifactName = `electron-v${electronVersion}-win32-x64.zip`
const electronArtifactSha256 =
  '26bf9a617d58d81772b3d68305d59ee48272969c15083c06db634a77358a8d9d'

const sourceSha = execFileSync('git', ['rev-parse', 'HEAD'], {
  cwd: path.resolve(__dirname, '..'),
  encoding: 'utf8',
}).trim()
if (!/^[0-9a-f]{40}$/.test(sourceSha)) {
  throw new Error('无法解析发行包源提交 SHA')
}
const sourceShortSha = sourceSha.slice(0, 12)

async function applyElectronFuses(context) {
  if (context.electronPlatformName !== 'win32') {
    throw new Error('Windows V1 Fuse hook 只能处理 win32 发行包')
  }

  const executablePath = path.join(
    context.appOutDir,
    'SiyuAIControlCenter.exe',
  )
  if (!fs.existsSync(executablePath)) {
    throw new Error(`未找到待配置 Fuse 的 Electron EXE：${executablePath}`)
  }

  const { flipFuses, FuseVersion, FuseV1Options } = await import(
    '@electron/fuses'
  )
  await flipFuses(executablePath, {
    version: FuseVersion.V1,
    strictlyRequireAllFuses: true,
    [FuseV1Options.RunAsNode]: false,
    [FuseV1Options.EnableCookieEncryption]: true,
    [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
    [FuseV1Options.EnableNodeCliInspectArguments]: false,
    [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
    [FuseV1Options.OnlyLoadAppFromAsar]: true,
    [FuseV1Options.LoadBrowserProcessSpecificV8Snapshot]: false,
    [FuseV1Options.GrantFileProtocolExtraPrivileges]: false,
    [FuseV1Options.WasmTrapHandlers]: true,
  })
}

module.exports = {
  appId: 'com.siyu.controlcenter',
  productName: '思余AI中控台',
  directories: {
    output: 'release',
  },
  asar: true,
  files: [
    'dist/config/**/*',
    'dist/ipc/**/*',
    'dist/main/**/*',
    'dist/preload/**/*',
    'dist/services/**/*',
    'dist/types/**/*',
    'package.json',
  ],
  npmRebuild: false,
  electronDownload: {
    checksums: {
      [electronArtifactName]: electronArtifactSha256,
    },
  },
  extraMetadata: {
    releaseSourceSha: sourceSha,
    releaseProductionUrl: 'https://119.29.188.118/',
    releaseElectronArtifactSha256: electronArtifactSha256,
  },
  afterPack: applyElectronFuses,
  win: {
    target: [
      {
        target: 'nsis',
        arch: ['x64'],
      },
    ],
    icon: path.resolve(
      __dirname,
      '../mobile/public/icons/icon-512.png',
    ),
    executableName: 'SiyuAIControlCenter',
    requestedExecutionLevel: 'asInvoker',
    artifactName: `Siyu-AI-Control-Center-${packageMetadata.version}-${sourceShortSha}-windows-\${arch}-setup.\${ext}`,
  },
  nsis: {
    oneClick: true,
    perMachine: false,
    createDesktopShortcut: 'always',
    createStartMenuShortcut: true,
    shortcutName: '思余AI中控台',
    uninstallDisplayName: '思余AI中控台',
    deleteAppDataOnUninstall: false,
    runAfterFinish: true,
  },
  publish: null,
}
