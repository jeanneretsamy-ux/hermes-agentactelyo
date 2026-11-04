import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { act } from 'react'
import { beforeEach, expect, it, vi } from 'vitest'

import type { HermesGateway } from '@/hermes'

import { AtelierDialog } from './atelier-dialog'

const mocks = vi.hoisted(() => ({
  insert: vi.fn(),
  request: vi.fn(),
  surface: true,
  pluginRoot: vi.fn()
}))

vi.mock('@/app/chat/composer/focus', () => ({
  getActiveComposer: () => 'main',
  getVisibleComposerSurfaceId: () => (mocks.surface ? 'surface' : null),
  requestComposerInsert: mocks.insert
}))
// Keep native control behavior while excluding layout/portal machinery from these interaction tests.
vi.mock('@/components/ui/button', () => ({
  Button: ({ variant: _variant, ...props }: any) => <button {...props} />
}))
vi.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children }: any) => <div>{children}</div>,
  DialogContent: ({ children }: any) => <div>{children}</div>,
  DialogHeader: ({ children }: any) => <header>{children}</header>,
  DialogTitle: ({ children }: any) => <h1>{children}</h1>,
  DialogDescription: ({ children }: any) => <p>{children}</p>
}))

const revision = 'a'.repeat(64)

const rows = [
  {
    id: 'chrono',
    name: 'Chronologie ALPHA',
    revision,
    created_at: '2026-11-03',
    active: false
  }
]

const panel = {
  id: 'chrono',
  name: 'Chronologie ALPHA',
  revision,
  kind: 'chronology',
  source_binding: 'verified',
  semantic_review: 'human_required',
  events: [
    {
      id: 'sign',
      date: '2026-10-15',
      title: 'Signature',
      evidence: [
        {
          passage_id: 'p_bound',
          name: 'bail.txt',
          page: null,
          quote: 'Signé le 15 octobre 2026. <script>danger()</script>',
          url: 'file:///bail.txt',
          start: 0,
          end: 57,
          source_sha256: 'b'.repeat(64)
        }
      ]
    }
  ]
}

const gateway = { request: mocks.request } as unknown as HermesGateway

beforeEach(() => {
  mocks.request.mockReset()
  mocks.insert.mockReset()
  mocks.surface = true
  mocks.pluginRoot.mockReset()
  mocks.pluginRoot.mockResolvedValue('C:/device/desktop-plugins')
  Object.defineProperty(window, 'hermesDesktop', {
    configurable: true,
    value: { desktopPluginsRoot: mocks.pluginRoot }
  })
  mocks.request.mockImplementation(async (method: string) =>
    method === 'atelier.preview' ? panel : { revisions: rows }
  )
})

it('previews a source, filters, activates and deactivates the exact version in the owner profile', async () => {
  render(<AtelierDialog gateway={gateway} onClose={vi.fn()} profile="legal-a" />)
  fireEvent.click(await screen.findByRole('button', { name: /Chronologie ALPHA/ }))
  await screen.findByRole('heading', { name: /Chronologie ALPHA/ })
  fireEvent.click(screen.getByText(/Source : bail.txt/))
  expect(screen.getByText(panel.events[0].evidence[0].quote)).toBeTruthy()
  expect(document.querySelector('script')).toBeNull()
  fireEvent.change(screen.getByLabelText('Filtrer les événements et les sources'), { target: { value: 'absent' } })
  expect(screen.getByText('0 événement(s)')).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Filtrer les événements et les sources'), { target: { value: 'Signature' } })
  expect(screen.getByText('1 événement(s)')).toBeTruthy()
  mocks.request.mockImplementation(async (method: string) => ({
    revisions: [{ ...rows[0], active: method !== 'atelier.deactivate' }]
  }))
  fireEvent.click(screen.getByRole('button', { name: 'Activer cette version après revue' }))
  await screen.findByRole('heading', { name: /Version active/ })
  expect(mocks.request).toHaveBeenCalledWith('atelier.activate', {
    profile: 'legal-a',
    revision
  })
  fireEvent.click(screen.getByRole('button', { name: 'Désactiver' }))
  await screen.findByText('Extension désactivée. Les versions sont conservées.')
  expect(mocks.request).toHaveBeenCalledWith('atelier.deactivate', {
    profile: 'legal-a',
    panel_id: 'chrono'
  })
})

it('prepares an unsent creator request for the actual composer', async () => {
  const close = vi.fn()
  render(<AtelierDialog gateway={gateway} onClose={close} profile="legal-a" />)
  await screen.findByRole('button', { name: /Chronologie ALPHA/ })
  fireEvent.click(screen.getByRole('button', { name: 'Préparer la création dans le chat' }))
  expect(mocks.insert).toHaveBeenCalledWith(expect.stringContaining('actelyo-atelier'), { target: 'main' })
  expect(close).toHaveBeenCalledOnce()
  expect(mocks.request.mock.calls.every(([method]) => method === 'atelier.list')).toBe(true)
})

it('shows RPC failures and refreshes without pretending the extension was activated', async () => {
  mocks.request.mockRejectedValueOnce(new Error('Backend indisponible'))
  render(<AtelierDialog gateway={gateway} onClose={vi.fn()} profile="legal-a" />)
  await screen.findByRole('alert')
  expect(screen.queryByRole('button', { name: 'Activer cette version après revue' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser' }))
  await screen.findByRole('button', { name: /Chronologie ALPHA/ })
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
})

it('prepares a JavaScript plugin request using the local app root and opens its manager', async () => {
  const open = vi.fn()
  render(<AtelierDialog gateway={gateway} local onClose={vi.fn()} onOpenPlugins={open} profile="legal-a" />)
  await screen.findByRole('button', { name: /Chronologie ALPHA/ })
  fireEvent.click(screen.getByRole('button', { name: 'Plugin d’interface' }))
  fireEvent.click(screen.getByRole('button', { name: 'Préparer la création dans le chat' }))
  await waitFor(() =>
    expect(mocks.insert).toHaveBeenCalledWith(expect.stringContaining('actelyo-plugin-creator'), { target: 'main' })
  )
  expect(mocks.insert.mock.calls[0][0]).toContain('C:/device/desktop-plugins')
  expect(mocks.insert.mock.calls[0][0]).toContain('defaultEnabled: false')
  fireEvent.click(screen.getByRole('button', { name: 'Ouvrir les plugins' }))
  expect(open).toHaveBeenCalledOnce()
})

it('refuses to confuse a remote backend with the local desktop plugin root', async () => {
  render(<AtelierDialog gateway={gateway} onClose={vi.fn()} profile="remote-profile" />)
  await screen.findByRole('button', { name: /Chronologie ALPHA/ })
  fireEvent.click(screen.getByRole('button', { name: 'Plugin d’interface' }))
  fireEvent.click(screen.getByRole('button', { name: 'Préparer la création dans le chat' }))
  expect((await screen.findByRole('alert')).textContent).toContain('connexion locale')
  expect(mocks.pluginRoot).not.toHaveBeenCalled()
  expect(mocks.insert).not.toHaveBeenCalled()
})

it('prepares a bounded mission for the selected profile without creating work before send', async () => {
  render(<AtelierDialog gateway={gateway} onClose={vi.fn()} profile="legal-b" />)
  await screen.findByRole('button', { name: /Chronologie ALPHA/ })
  fireEvent.click(screen.getByRole('button', { name: 'Mission suivie' }))
  fireEvent.change(screen.getByLabelText('Demande à l’agent'), {
    target: { value: 'Comparer les deux projets du dossier.' }
  })
  fireEvent.click(screen.getByRole('button', { name: 'Préparer la création dans le chat' }))
  const [prompt, destination] = mocks.insert.mock.calls[0]
  expect(prompt).toContain('Comparer les deux projets du dossier.')
  expect(prompt).toContain('"legal-b"')
  expect(prompt).toContain('--goal-max-turns 20')
  expect(prompt).toContain('--max-retries 2')
  expect(prompt).toContain('--completion-contract local-only')
  expect(destination).toEqual({ target: 'main' })
  expect(mocks.request.mock.calls.every(([method]) => method === 'atelier.list')).toBe(true)
  expect(mocks.pluginRoot).not.toHaveBeenCalled()
})

it('ignores a late preview from the previous profile across A to B to A', async () => {
  let resolvePreview!: (value: typeof panel) => void
  mocks.request.mockImplementation(async (method: string) =>
    method === 'atelier.preview'
      ? new Promise<typeof panel>(resolve => {
          resolvePreview = resolve
        })
      : { revisions: rows }
  )
  const view = render(<AtelierDialog gateway={gateway} onClose={vi.fn()} profile="legal-a" />)
  fireEvent.click(await screen.findByRole('button', { name: /Chronologie ALPHA/ }))
  view.rerender(<AtelierDialog gateway={gateway} onClose={vi.fn()} profile="legal-b" />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Actualiser' }).hasAttribute('disabled')).toBe(false))
  await act(async () => resolvePreview(panel))
  expect(screen.queryByRole('region', { name: 'Chronologie sourcée' })).toBeNull()
  view.rerender(<AtelierDialog gateway={gateway} onClose={vi.fn()} profile="legal-a" />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Actualiser' }).hasAttribute('disabled')).toBe(false))
  expect(screen.queryByRole('region', { name: 'Chronologie sourcée' })).toBeNull()
})

it('ignores a late failure without unlocking the new profile request', async () => {
  let rejectPreview!: (error: Error) => void
  let resolveList!: (value: { revisions: typeof rows }) => void
  mocks.request.mockImplementation(async (method: string, params: { profile: string }) => {
    if (method === 'atelier.preview') {
      return new Promise((_, reject) => {
        rejectPreview = reject
      })
    }

    if (params.profile === 'legal-b') {
      return new Promise(resolve => {
        resolveList = resolve
      })
    }

    return { revisions: rows }
  })
  const view = render(<AtelierDialog gateway={gateway} onClose={vi.fn()} profile="legal-a" />)
  fireEvent.click(await screen.findByRole('button', { name: /Chronologie ALPHA/ }))
  view.rerender(<AtelierDialog gateway={gateway} onClose={vi.fn()} profile="legal-b" />)
  await act(async () => rejectPreview(new Error('Erreur du profil A')))
  expect(screen.queryByRole('alert')).toBeNull()
  expect(screen.getByRole('button', { name: 'Actualiser' }).hasAttribute('disabled')).toBe(true)
  await act(async () => resolveList({ revisions: rows }))
  expect(screen.getByRole('button', { name: 'Actualiser' }).hasAttribute('disabled')).toBe(false)
})
