// Exercise model-authored files through the real Desktop loader in Chromium.
const fs = require('node:fs')
const path = require('node:path')
const http = require('node:http')
const assert = require('node:assert/strict')
const crypto = require('node:crypto')
const { chromium } = require('@playwright/test')
const base = path.resolve(__dirname, '../../..')
const args = process.argv.slice(2)
function option(name, fallback) {
  const i = args.indexOf(name)
  return i < 0 ? fallback : args[i + 1]
}
const out = path.resolve(option('--artifacts', path.join(base, '.atelier-browser-proof')))
const dist = path.resolve(option('--dist', path.join(base, '.atelier-smoke-dist')))
const calendar = path.join(base, 'apps/desktop/src/test/plugin-workshop/fixtures/calendar-days/plugin.js')
const counter = path.join(base, 'apps/desktop/src/test/plugin-workshop/fixtures/piece-counter/plugin.js')
const chrome = option('--browser', undefined)
const checks = []
function checked(name) {
  checks.push(name)
  console.log('PASS', name)
}
const server = http.createServer((req, res) => {
  const file = path.resolve(dist, '.' + decodeURIComponent(new URL(req.url, 'http://localhost').pathname))
  if (file !== dist && !file.startsWith(dist + path.sep)) {
    res.writeHead(403)
    res.end()
    return
  }
  const target = file === dist ? path.join(dist, 'index.html') : file
  const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json' }
  try {
    const bytes = fs.readFileSync(target)
    res.writeHead(200, { 'Content-Type': mime[path.extname(target)] || 'application/octet-stream' })
    res.end(bytes)
  } catch {
    res.writeHead(404)
    res.end('Not found')
  }
})
async function main() {
  fs.mkdirSync(out, { recursive: true })
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(17838, '127.0.0.1', resolve)
  })
  const browser = await chromium.launch({ executablePath: chrome, headless: true })
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 }, timezoneId: 'Europe/Paris' })
  const errors = []
  page.on('pageerror', error => errors.push(String(error)))
  page.on('console', message => {
    if (message.type() === 'error') console.log('BROWSER', message.text().slice(0, 350))
  })
  const count = async value => {
    await page.waitForFunction(
      v => document.querySelector('[data-testid="pane-count"]')?.textContent === `${v} panneau(x)`,
      value
    )
  }
  try {
    await page.goto('http://127.0.0.1:17838', { waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: 'Atelier — chargeur réel' }).waitFor()
    await page.getByLabel('Fichier du plugin').setInputFiles(calendar)
    await page.getByRole('status').filter({ hasText: 'Chargé : actelyo-calendar-days' }).waitFor()
    await count(0)
    checked('Generated calendar loads through the real loader and stays disabled')
    await page.getByRole('button', { name: 'Activer', exact: true }).click()
    await count(1)
    const date = page.getByLabel('Date de départ', { exact: true })
    const days = page.getByLabel('Nombre de jours calendaires', { exact: true })
    const output = page.getByLabel('Date obtenue', { exact: true })
    await date.fill('2028-02-28')
    await days.fill('1')
    await page.getByRole('button', { name: 'Calculer', exact: true }).click()
    assert.equal(await output.textContent(), 'Date obtenue : 29/02/2028')
    checked('Calendar button computes leap day')
    await date.fill('2027-12-31')
    await days.fill('2')
    await page.getByRole('button', { name: 'Calculer', exact: true }).click()
    assert.equal(await output.textContent(), 'Date obtenue : 02/01/2028')
    checked('Calendar button crosses year boundary')
    await days.fill('-1')
    await page.getByRole('button', { name: 'Calculer', exact: true }).click()
    assert.ok(await page.getByRole('alert').textContent())
    checked('Invalid input produces a visible error')
    await page.getByRole('button', { name: 'Effacer', exact: true }).click()
    assert.equal(await date.inputValue(), '')
    assert.equal(await days.inputValue(), '')
    assert.equal(await output.textContent(), '')
    assert.equal(await page.getByRole('alert').count(), 0)
    checked('Clear button removes fields, result and error')
    await page.getByRole('button', { name: 'Désactiver', exact: true }).click()
    await count(0)
    await page.getByRole('button', { name: 'Activer', exact: true }).click()
    await count(1)
    assert.equal(await date.inputValue(), '')
    checked('Disable cleans contributions and re-enable remounts clean state')
    await page.getByLabel('Fichier du plugin').setInputFiles(calendar)
    await count(1)
    checked('Reloading the same plugin leaves one panel')
    await page.getByLabel('Fichier du plugin').setInputFiles(counter)
    await page.getByRole('status').filter({ hasText: 'Chargé : actelyo-compteur-pieces' }).waitFor()
    await count(1)
    await page.getByRole('button', { name: 'Activer', exact: true }).click()
    await count(2)
    const value = page.getByLabel('Nombre de pièces', { exact: true })
    assert.equal(await value.textContent(), '0')
    assert.ok(await page.getByRole('button', { name: 'Retirer', exact: true }).isDisabled())
    await page.getByRole('button', { name: 'Ajouter', exact: true }).click()
    await page.getByRole('button', { name: 'Ajouter', exact: true }).click()
    assert.equal(await value.textContent(), '2')
    checked('Second generated plugin loads alongside the first and increments')
    await page.getByRole('button', { name: 'Retirer', exact: true }).click()
    assert.equal(await value.textContent(), '1')
    await page.getByRole('button', { name: 'Retirer', exact: true }).click()
    assert.equal(await value.textContent(), '0')
    assert.ok(await page.getByRole('button', { name: 'Retirer', exact: true }).isDisabled())
    checked('Counter cannot become negative')
    await page.getByRole('button', { name: 'Ajouter', exact: true }).click()
    await page.getByRole('button', { name: 'Remettre à zéro', exact: true }).click()
    assert.equal(await value.textContent(), '0')
    checked('Counter reset button works')
    await date.fill('2028-02-28')
    await days.fill('1')
    await page.getByRole('button', { name: 'Calculer', exact: true }).click()
    await page.getByRole('button', { name: 'Ajouter', exact: true }).click()
    await page.screenshot({ path: path.join(out, 'two-generated-plugins.png'), fullPage: true })
    await page.getByRole('button', { name: 'Désactiver', exact: true }).click()
    await count(1)
    assert.equal(await page.getByLabel('Nombre de pièces', { exact: true }).count(), 0)
    assert.equal(await output.textContent(), 'Date obtenue : 29/02/2028')
    checked('Disabling one plugin leaves the other functional')
    await page.getByRole('button', { name: 'Activer', exact: true }).click()
    await count(2)
    assert.equal(await value.textContent(), '0')
    await page.getByRole('button', { name: 'Décharger', exact: true }).click()
    await count(1)
    await page.getByRole('combobox').selectOption('actelyo-calendar-days')
    await page.getByRole('button', { name: 'Décharger', exact: true }).click()
    await count(0)
    checked('Both plugin lifecycles unload without residual panels')
    assert.deepEqual(errors, [])
    checked('No browser runtime exceptions')
    fs.writeFileSync(
      path.join(out, 'results.json'),
      JSON.stringify(
        {
          passed: checks.length,
          checks,
          errors,
          method:
            'Unmodified model-authored files; actual Desktop runtime-loader, plugin context, SDK, registry and activation store in Chromium. Electron shell and installed EXE not tested.',
          files: [calendar, counter].map(file => ({
            file,
            sha256: crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
          }))
        },
        null,
        2
      )
    )
  } catch (error) {
    await page.screenshot({ path: path.join(out, 'failure.png'), fullPage: true })
    fs.writeFileSync(
      path.join(out, 'failure.json'),
      JSON.stringify({ error: String(error), errors, checks, body: await page.locator('body').innerText() }, null, 2)
    )
    throw error
  } finally {
    await browser.close()
    await new Promise(resolve => server.close(resolve))
  }
}
main().catch(error => {
  console.error(error)
  process.exitCode = 1
  server.close()
})
