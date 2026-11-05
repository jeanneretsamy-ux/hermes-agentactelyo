import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import yaml from 'js-yaml'

import { MOCK_REPLY } from '../../../tests-js/scripts/mock-server'

import { type MockBackendFixture, setupMockBackend, waitForAppReady } from './fixtures'
import { expect, test } from './test'
import { captureRpc } from './capture-rpc'

// A bot created from the New Bot dialog WITHOUT a clone source (the "inherited
// from launch profile" path) must land on disk with a usable `model:` block in
// its own config.yaml and its introduction turn must actually run — a profile
// whose config.yaml lacks the block is dead on arrival ("No LLM provider
// configured" on the first message). Verified against storage truth (the
// created profile's config.yaml under HERMES_HOME), not the toast.

let fixture: MockBackendFixture | null = null
const wire: unknown[] = []

type Page = MockBackendFixture['page']

async function openBots(page: Page): Promise<void> {
  const tab = page
    .getByRole('button', { name: 'Bots', exact: true })
    .or(page.getByRole('tab', { name: 'Bots', exact: true }))
    .first()

  await tab.click()
  await expect(page.getByRole('button', { name: 'New bot or group chat' })).toBeVisible()
}

test.beforeAll(async () => {
  fixture = await setupMockBackend()
  captureRpc(fixture.page, wire)
  await waitForAppReady(fixture, 120_000)
})

// eslint-disable-next-line no-empty-pattern
test.afterEach(async ({}, info) => {
  if (!fixture) {
    return
  }

  await info.attach('native-window', { body: await fixture.page.screenshot(), contentType: 'image/png' })
  writeFileSync(info.outputPath('bot-rpc.json'), JSON.stringify({ wire, prompts: fixture.mock.receivedPrompts.length }))
  const cfg = join(fixture.sandbox.hermesHome, 'profiles', 'fresh-scout', 'config.yaml')
  await info.attach('created-config', {
    body: existsSync(cfg) ? readFileSync(cfg) : Buffer.from('<missing>'),
    contentType: 'text/plain'
  })
})

test.afterAll(async () => {
  await fixture?.cleanup()
  fixture = null
})

test('a fresh (non-clone) bot gets a runnable model block on disk', async () => {
  test.setTimeout(300_000)
  const page = fixture!.page

  await openBots(page)
  await page.getByRole('button', { name: 'New bot or group chat' }).click()
  await page.getByRole('menuitem', { name: 'New Bot' }).click()

  const dialog = page.getByRole('dialog', { name: 'New Bot' })
  await dialog.getByPlaceholder('inbox-triage').fill('fresh-scout')
  await dialog.getByPlaceholder('Inbox Triage').fill('Fresh Scout')
  await dialog.getByRole('button', { name: 'Advanced' }).click()

  // "Fresh profile" = no clone source; the model must be inherited, not cloned.
  await dialog.getByRole('combobox').filter({ hasText: /default|Fresh profile/ }).first().click()
  await page.getByRole('option', { name: 'Fresh profile (bundled skills)' }).click()
  await dialog.getByRole('button', { name: 'Create Bot' }).click()
  await expect(dialog).toBeHidden({ timeout: 60_000 })

  // Storage truth: the created profile's own config.yaml carries the model block.
  const cfgPath = join(fixture!.sandbox.hermesHome, 'profiles', 'fresh-scout', 'config.yaml')
  await expect.poll(() => existsSync(cfgPath), { timeout: 30_000 }).toBe(true)
  const cfg = readFileSync(cfgPath, 'utf8')
  const created = yaml.load(cfg) as { model: Record<string, unknown> }
  const parent = yaml.load(readFileSync(join(fixture!.sandbox.hermesHome, 'config.yaml'), 'utf8')) as { model: Record<string, unknown> }
  // The fixture now uses the supported custom provider with its endpoint in
  // model.base_url, rather than a legacy named providers.mock gateway.
  expect(parent.model.base_url).toBe(`${fixture!.mockUrl}/v1`)
  expect(created.model).toMatchObject({
    provider: parent.model.provider,
    default: parent.model.default,
    base_url: parent.model.base_url,
  })
  // A stored block alone is not a runnable bot: its automatic introduction
  // must complete through the real gateway and the mock inference server.
  await expect(page.locator('[data-slot="aui_thread-viewport"]')).toContainText(MOCK_REPLY, { timeout: 60_000 })
  expect(fixture!.mock.receivedPrompts.length).toBeGreaterThan(0)
})
