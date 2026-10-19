import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { openCatalogPluginInstall } from '@/store/plugin-catalog-install'

import { NativePluginCatalog } from './native-plugin-catalog'

vi.mock('@/store/plugin-catalog-install', () => ({ openCatalogPluginInstall: vi.fn() }))
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

it('opens the existing install confirmation with the selected profile and reviewed pin', async () => {
  const entry = { name: 'example-plugin', repo: 'owner/plugin', sha: 'a'.repeat(40) }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => [entry, null, {}] }))

  const { container } = render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <NativePluginCatalog profile="cabinet-a" />
    </QueryClientProvider>
  )

  fireEvent.click(await screen.findByRole('button', { name: 'Configurer l’installation' }))
  expect(openCatalogPluginInstall).toHaveBeenCalledWith(entry, 'cabinet-a')
  expect(container.querySelector('iframe')).toBeNull()
})
