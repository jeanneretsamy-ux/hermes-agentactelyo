import test from 'node:test'
import assert from 'node:assert/strict'
import { clearFirstRunOverlay } from './verify-installed.mjs'

function startup({ readyAfter = Infinity, transparent = false } = {}) {
  let polls = 0
  let trialClicks = 0
  const overlay = {
    evaluate: async () => !transparent,
    innerText: async () => 'CONNECTING',
    getByRole() { throw new Error('Startup must not be dismissed as onboarding') }
  }
  const capabilities = {
    isVisible: async () => true,
    async click(options) {
      assert.equal(options.trial, true)
      trialClicks++
      if (!transparent && polls < readyAfter) throw new Error('Overlay intercepts pointer')
    }
  }
  return {
    page: {
      getByText: () => ({ first: () => capabilities }),
      locator: () => ({ all: async () => [overlay] }),
      async waitForTimeout() { polls++; await new Promise(resolve => setTimeout(resolve, 1)) }
    },
    get trialClicks() { return trialClicks }
  }
}

test('waits through startup beyond the former 20-attempt onboarding limit', async () => {
  const fixture = startup({ readyAfter: 25 })
  await clearFirstRunOverlay(fixture.page, { timeout: 2000, pollInterval: 1 })
  assert.equal(fixture.trialClicks, 26)
})

test('an exited transparent overlay does not block an actionable sidebar', async () => {
  const fixture = startup({ transparent: true })
  await clearFirstRunOverlay(fixture.page, { timeout: 100, pollInterval: 1 })
  assert.equal(fixture.trialClicks, 1)
})

test('a backend that never becomes ready still fails verification', async () => {
  const fixture = startup()
  await assert.rejects(clearFirstRunOverlay(fixture.page, { timeout: 30, pollInterval: 1 }), /did not become interactive.*CONNECTING/)
})

for (const label of ["I'll choose a provider later", 'Je choisirai un fournisseur plus tard']) {
  test(`defers setup without selecting a provider: ${label}`, async () => {
    let dismissed = false
    const clicked = []
    const buttons = ['Get started with a provider', 'Continue', label].map(text => ({
      innerText: async () => text,
      isEnabled: async () => true,
      async click() { clicked.push(text); dismissed = text === label }
    }))
    const overlay = {
      evaluate: async () => !dismissed,
      innerText: async () => 'Connect a model provider to start chatting',
      getByRole: () => ({ all: async () => buttons })
    }
    const page = {
      getByText: () => ({ first: () => ({
        isVisible: async () => true,
        async click() { if (!dismissed) throw new Error('Setup blocks navigation') }
      }) }),
      locator: () => ({ all: async () => [overlay] }),
      waitForTimeout: async () => {}
    }
    await clearFirstRunOverlay(page, { timeout: 100 })
    assert.deepEqual(clicked, [label])
  })
}

