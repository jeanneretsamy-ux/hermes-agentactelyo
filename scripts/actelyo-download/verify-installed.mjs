import { createRequire } from 'node:module'
import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'
const { _electron } = createRequire(path.join(process.env.GITHUB_WORKSPACE || process.cwd(), 'apps/desktop/package.json'))('playwright')

const [installed, proof] = process.argv.slice(2)
assert(installed && proof, 'Usage: verify-installed.mjs installed-directory proof-directory')
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

async function clearFirstRunOverlay(page) {
  const capabilities = page.getByText(/^(Capabilities|Capacités)$/).first()
  const overlay = page.locator('[data-glass-opaque]').last()
  const exitAction = /choose.*later|plus tard|skip|ignore|ignorer|continue|continuer|next|suivant|start|commencer|got it|compris/i

  for (let attempt = 0; attempt < 20; attempt++) {
    if (await capabilities.isVisible().catch(() => false) &&
        !(await overlay.isVisible().catch(() => false))) {
      return
    }

    if (await overlay.isVisible().catch(() => false)) {
      const buttons = await overlay.getByRole('button').all()
      let clicked = false

      for (const button of buttons) {
        const label = (await button.innerText().catch(() => '')).trim()
        if (exitAction.test(label) && await button.isEnabled().catch(() => false)) {
          await button.click({ timeout: 10000 })
          clicked = true
          break
        }
      }

      if (!clicked) {
        // The initial welcome screen can expose a single unlabeled close/continue
        // action. Escape is the same user-facing dismissal path as its close button.
        await page.keyboard.press('Escape')
      }

      await page.waitForTimeout(500)
      continue
    }

    // Wait for the first-run UI to mount before deciding it is absent. On Windows
    // it can appear after the sidebar and otherwise intercept every navigation click.
    await page.waitForTimeout(500)
  }

  const text = await overlay.innerText().catch(() => '')
  throw new Error(`First-run onboarding still blocks the app after dismissal attempts: ${text.slice(0, 500)}`)
}

try {
  const page = await app.firstWindow({ timeout: 180000 })
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
} finally {
  await app.close()
}
