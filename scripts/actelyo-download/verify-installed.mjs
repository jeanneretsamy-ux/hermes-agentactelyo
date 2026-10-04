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
try {
  const page = await app.firstWindow({ timeout: 180000 })
  // Exercise the visible first-run choice; never force clicks through onboarding.
  const chooseLater = page.getByRole('button', { name: /choose a provider later|choisirai.*fournisseur.*plus tard/i })
  await chooseLater.waitFor({ timeout: 300000 })
  assert(!/\bHermes\b/i.test(await page.locator('body').innerText()), 'Legacy product name on fresh-install screen')
  await page.screenshot({ path: path.join(proof, 'installed-onboarding.png') })
  await chooseLater.click()
  await chooseLater.waitFor({ state: 'hidden', timeout: 30000 })
  await page.getByText(/^(Capabilities|Capacités)$/).first().waitFor({ timeout: 300000 })
  await page.screenshot({ path: path.join(proof, 'installed-window.png') })
  const identity = await app.evaluate(({ app }) => ({ name: app.getName(), version: app.getVersion() }))
  assert.match(identity.name, /Actelyo/i)
  await page.getByText(/^(Capabilities|Capacités)$/).first().click()
  const catalog = page.getByRole('region', { name: 'Actelyo · Skills Hub' })
  await catalog.waitFor({ timeout: 90000 })
  await catalog.getByRole('button', { name: /Install/i }).first().waitFor({ timeout: 180000 })
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
  for (const [index, page] of app.windows().entries()) {
    await page.screenshot({ path: path.join(proof, `failure-window-${index}.png`) }).catch(() => {})
    console.error('Installed window:', await page.locator('body').innerText().catch(() => 'unavailable'))
  }
  throw error
} finally {
  await app.close()
}
