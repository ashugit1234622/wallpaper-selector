import { resolve, basename } from 'node:path'
import { readFileSync, existsSync, mkdirSync } from 'node:fs'
import { randomUUID } from 'node:crypto'
import { AdbClient } from '../src/main/adb/client'
import { loadKeys } from '../src/main/adb/keys'

const PKG = 'com.gathin.tvhome'
const DIR = `/sdcard/Android/data/${PKG}/files`

interface CliArgs {
  image?: string
  host?: string
  port: number
  test: boolean
}

function parseArgs(): CliArgs {
  const args = process.argv.slice(2)
  const result: CliArgs = { port: 5555, test: false }

  for (let i = 0; i < args.length; i++) {
    const arg = args[i]
    if (arg === '--image' && i + 1 < args.length) {
      result.image = args[++i]
    } else if (arg === '--host' && i + 1 < args.length) {
      result.host = args[++i]
    } else if (arg === '--port' && i + 1 < args.length) {
      result.port = Number(args[++i]) || 5555
    } else if (arg === '--test') {
      result.test = true
    }
  }

  // Fallback to settings.json if host not provided
  if (!result.host) {
    try {
      const appData = process.env.APPDATA || ''
      const settingsPath = resolve(appData, 'cleanmytv', 'settings.json')
      if (existsSync(settingsPath)) {
        const settings = JSON.parse(readFileSync(settingsPath, 'utf8'))
        if (settings.lastHost) result.host = settings.lastHost
      }
    } catch {
      // ignore
    }
  }

  if (!result.host) result.host = '192.168.1.37'
  return result
}

function logJson(data: Record<string, unknown>): void {
  console.log(JSON.stringify(data))
}

async function main(): Promise<void> {
  const opts = parseArgs()

  // 1. Resolve ADB keys
  const appData = process.env.APPDATA || ''
  const primaryKey = resolve(appData, 'cleanmytv', 'adbkey')
  const localKey = resolve('.cytv-data', 'adbkey')
  const keyPath = existsSync(primaryKey) ? primaryKey : localKey

  mkdirSync(resolve('.cytv-data'), { recursive: true })
  const keys = loadKeys(keyPath)

  logJson({
    status: 'connecting',
    message: `Connecting to Android TV at ${opts.host}:${opts.port}...`,
    host: opts.host,
    port: opts.port
  })

  let client: AdbClient
  try {
    client = await AdbClient.connect({
      host: opts.host!,
      port: opts.port,
      keys,
      authTimeoutMs: 15000
    })
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err)
    logJson({
      status: 'error',
      code: 'connection_failed',
      message: `Failed to connect to TV at ${opts.host}:${opts.port}: ${errorMsg}`
    })
    process.exit(1)
  }

  try {
    // If test mode, verify shell access & product model
    if (opts.test) {
      const model = (await client.shell('getprop ro.product.model')).trim()
      const device = (await client.shell('getprop ro.product.device')).trim()
      logJson({
        status: 'ok',
        mode: 'test',
        message: `Successfully connected to TV: ${model || 'Android TV'} (${device || 'device'})`,
        model,
        device
      })
      client.close()
      process.exit(0)
    }

    if (!opts.image) {
      logJson({
        status: 'error',
        code: 'missing_argument',
        message: 'No --image path specified.'
      })
      client.close()
      process.exit(1)
    }

    const resolvedImage = resolve(opts.image)
    if (!existsSync(resolvedImage)) {
      logJson({
        status: 'error',
        code: 'file_not_found',
        message: `Image file does not exist: ${resolvedImage}`
      })
      client.close()
      process.exit(1)
    }

    const imgBuf = readFileSync(resolvedImage)
    if (imgBuf.length === 0) {
      logJson({
        status: 'error',
        code: 'empty_file',
        message: 'Image file is empty.'
      })
      client.close()
      process.exit(1)
    }

    logJson({
      status: 'pushing',
      message: 'Ensuring wallpaper directories on TV...',
      progress: 0.15
    })
    await client.shell(`mkdir -p ${DIR}/wallpapers`)

    // Sanitize file name for rotation pool
    const origName = basename(resolvedImage).replace(/[^a-zA-Z0-9._-]/g, '_')
    const poolFilename = origName.toLowerCase().endsWith('.jpg') || origName.toLowerCase().endsWith('.jpeg')
      ? origName
      : `${origName}.jpg`

    const targetRemote = `${DIR}/wallpaper.jpg`
    const poolRemote = `${DIR}/wallpapers/${poolFilename}`

    const chunkSize = 24 * 1024
    const tmp = targetRemote + '.b64'
    await client.shell(`rm -f ${targetRemote} ${tmp}`)

    const numChunks = Math.ceil(imgBuf.length / chunkSize)
    for (let i = 0; i < numChunks; i++) {
      const chunkB64 = imgBuf.subarray(i * chunkSize, (i + 1) * chunkSize).toString('base64')
      await client.shell(`echo '${chunkB64}' >> ${tmp}`)
      const progress = 0.2 + 0.6 * ((i + 1) / numChunks)
      logJson({
        status: 'pushing',
        message: `Uploading wallpaper chunk ${i + 1}/${numChunks}...`,
        progress: Number(progress.toFixed(2))
      })
    }

    // Decode on device and copy to rotation pool
    logJson({
      status: 'pushing',
      message: 'Decoding image and updating rotation pool...',
      progress: 0.85
    })
    await client.shell(`base64 -d ${tmp} > ${targetRemote} && rm -f ${tmp}`)
    await client.shell(`cp ${targetRemote} ${poolRemote}`)

    // Update revision to trigger launcher refresh
    logJson({
      status: 'pushing',
      message: 'Reloading TV launcher theme...',
      progress: 0.95
    })
    const rev = randomUUID().replace(/-/g, '')
    await client.shell(`printf '%s' '${rev}' > ${DIR}/theme_revision`)

    // Restart launcher preserving accessibility services
    const restartCmd = `a=$(settings get secure enabled_accessibility_services); am force-stop ${PKG}; am start -n ${PKG}/.MainActivity >/dev/null; case "$a" in *${PKG}*) sleep 1; settings put secure enabled_accessibility_services ''; settings put secure enabled_accessibility_services "$a"; settings put secure accessibility_enabled 1 ;; esac`
    await client.shell(restartCmd)

    logJson({
      status: 'ok',
      message: '✓ TV Wallpaper updated and added to rotation pool successfully!',
      progress: 1.0,
      targetRemote,
      poolRemote
    })
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err)
    logJson({
      status: 'error',
      code: 'transfer_failed',
      message: `Failed to push wallpaper to TV: ${errorMsg}`
    })
    process.exit(1)
  } finally {
    client.close()
  }
}

main().catch(err => {
  logJson({
    status: 'error',
    code: 'fatal_error',
    message: String(err)
  })
  process.exit(1)
})
