import { createRequire } from 'node:module'
import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'
import { pathToFileURL } from 'node:url'
async function main() {
const { _electron } = createRequire(path.join(process.env.GITHUB_WORKSPACE || process.cwd(), 'apps/desktop/package.json'))('playwright')

const [installedArg, proofArg] = process.argv.slice(2)
assert(installedArg && proofArg, 'Usage: verify-installed.mjs installed-directory proof-directory')
const installed = path.resolve(installedArg)
const proof = path.resolve(proofArg)
fs.mkdirSync(proof, { recursive: true })
const exe = path.join(installed, 'Actelyo Law Harness.exe')
assert(fs.existsSync(exe), 'Installed Actelyo executable missing')
assert(fs.existsSync(path.join(installed, 'resources', 'agent-payload')), 'Bundled local agent missing')
const cleanEnv = { ...process.env }
for (const key of ['HERMES_PYTHON', 'HERMES_RUNTIME_DIR', 'VIRTUAL_ENV', 'PYTHONPATH', 'PYTHONHOME']) delete cleanEnv[key]
const app = await _electron.launch({
  executablePath: exe,
  env: {
    ...cleanEnv,
    HERMES_HOME: path.join(proof, 'clean-home'),
    HERMES_DESKTOP_USER_DATA_DIR: path.join(proof, 'clean-desktop'),
    HERMES_DESKTOP_DISABLE_GPU: '1'
  },
  timeout: 180000
})


let page
const runtimeLogs = []
for (const stream of [app.process().stdout, app.process().stderr]) {
  stream?.on('data', chunk => {
    runtimeLogs.push(chunk.toString())
    if (runtimeLogs.length > 200) runtimeLogs.shift()
  })
}
try {
  page = await app.firstWindow({ timeout: 180000 })
  await page.getByText(/^(Capabilities|Capacités)$/).first().waitFor({ timeout: 300000 })
  await clearFirstRunOverlay(page)
  await page.screenshot({ path: path.join(proof, 'installed-window.png') })
  const identity = await app.evaluate(({ app }) => ({ name: app.getName(), version: app.getVersion() }))
  assert.match(identity.name, /Actelyo/i)
  await page.getByText(/^(Capabilities|Capacités)$/).first().click()
  const catalog = page.getByRole('region', { name: 'Actelyo · Skills Hub' })
  await catalog.waitFor({ timeout: 90000 })
  assert.equal(await catalog.locator('iframe').count(), 0)
  const logos = await page.locator('img').evaluateAll(nodes => nodes.map(n => ({ src: n.src, alt: n.alt, loaded: n.complete && n.naturalWidth > 0 })))
  assert(logos.some(n => n.loaded && /actelyo/i.test(n.src + n.alt)), 'Loaded Actelyo logo missing')
  await page.screenshot({ path: path.join(proof, 'installed-skills.png') })
  fs.writeFileSync(path.join(proof, 'verification.json'), JSON.stringify({
    identity, sourceCommit: process.env.ACTELYO_SOURCE_SHA || process.env.GITHUB_SHA, executable: path.basename(exe),
    localPayloadPresent: true, nativeCatalogVerified: true, logos,
    modelIncluded: false, codeSigned: false
  }, null, 2))
} catch (error) {
  const body = page ? await page.locator('body').innerText().catch(() => '') : ''
  if (page) await page.screenshot({ path: path.join(proof, 'installed-failure.png') }).catch(() => {})
  fs.writeFileSync(path.join(proof, 'failure.json'), JSON.stringify({
    error: String(error.stack || error), body, runtimeLogs
  }, null, 2))
  console.error('Installed application verification failed:', body.slice(0, 2000))
  throw error
} finally {
  await app.close()
}
}

export async function clearFirstRunOverlay(page, { timeout = 300000, pollInterval = 500 } = {}) {
  const capabilities = page.getByText(/^(Capabilities|Capacités)$/).first()
  const overlays = page.locator('[data-glass-opaque]')
  // Only defer provider configuration. Generic words such as "start" can
  // match a provider's marketing copy and open its credentials form instead.
  const exitAction = /^(?:I'll choose a provider later|Je choisirai un fournisseur plus tard)$/i
  const deadline = Date.now() + timeout
  let lastText = ''

  while (Date.now() < deadline) {
    // Actionability checks the actual hit target, including transparent exit
    // animations. isVisible alone also matches opacity:0 CONNECTING overlays.
    if (await capabilities.isVisible().catch(() => false)) {
      try {
        await capabilities.click({ trial: true, timeout: Math.min(1000, Math.max(1, deadline - Date.now())) })
        return
      } catch {
        // First-run or boot overlays still intercept navigation.
      }
    }

    for (const overlay of await overlays.all()) {
      const blocking = await overlay.evaluate(node => {
        const style = getComputedStyle(node)
        return style.display !== 'none' && style.visibility !== 'hidden' &&
          style.pointerEvents !== 'none' && Number(style.opacity) > 0
      }).catch(() => false)
      if (!blocking) continue
      lastText = await overlay.innerText().catch(() => '')
      // Startup is not onboarding: wait for the local backend, do not send Escape.
      if (/^CONNECTING$/i.test(lastText.trim())) continue
      if (/installation failed|failed to start|startup failed/i.test(lastText)) {
        throw new Error('Installed application startup failed: ' + lastText.slice(0, 1000))
      }
      for (const button of await overlay.getByRole('button').all()) {
        const label = (await button.innerText().catch(() => '')).trim()
        if (exitAction.test(label) && await button.isEnabled().catch(() => false)) {
          await button.click({ timeout: Math.min(10000, Math.max(1, deadline - Date.now())) })
          break
        }
      }
    }
    await page.waitForTimeout(pollInterval)
  }
  throw new Error('Installed application did not become interactive within ' + timeout +
    ' ms. Last blocking overlay: ' + lastText.slice(0, 1000))
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  await main()
}

