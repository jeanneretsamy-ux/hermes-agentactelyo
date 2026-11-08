import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { atom } from 'nanostores'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ request: vi.fn(), open: vi.fn(), create: vi.fn(), enter: vi.fn(), current: true }))
vi.mock('@/store/gateway', () => ({ $gateway: atom({ request: mocks.request }) }))
vi.mock('@/store/profile', () => ({ $activeGatewayProfile: atom('default'), $profileScope: atom('default') }))
vi.mock('@/store/projects', () => ({
  projectProfile: () => 'default',
  createProject: mocks.create,
  enterProject: mocks.enter
}))
vi.mock('@/store/legal-practice', () => ({
  legalQueryKey: () => ['cabinet-test'],
  isLegalOwnerCurrent: () => mocks.current,
  openLegalPractice: mocks.open
}))
vi.mock('@/components/ui/codicon', () => ({ Codicon: () => null }))
vi.mock('@/components/ui/sidebar', () => ({
  SidebarMenuItem: ({ children }: { children: React.ReactNode }) => <li>{children}</li>,
  SidebarMenuButton: (props: React.ComponentProps<'button'>) => <button {...props} />
}))

import { LegalCabinetNavigation } from '../legal-cabinet-navigation'

const catalog = {
  domains: [
    { id: 'social', label: 'Droit social' },
    { id: 'societes', label: 'Droit des sociétés' }
  ],
  workspaces: [{ id: 'soc', name: 'Mon cabinet social', domain: 'social' }]
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.current = true
  mocks.request.mockResolvedValue(catalog)
})
afterEach(cleanup)

function show() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <LegalCabinetNavigation />
    </QueryClientProvider>
  )
}

it('opens the selected workspace library without rewriting its domain', async () => {
  show()
  fireEvent.click(await screen.findByText('Droit social'))
  fireEvent.click(screen.getByRole('button', { name: 'Bibliothèque et rédaction' }))
  expect(mocks.enter).toHaveBeenCalledWith('soc')
  expect(mocks.open).toHaveBeenCalledWith(catalog.workspaces[0], 'acts')
  expect(mocks.request.mock.calls.every(([method]) => method === 'legal.catalog')).toBe(true)
})

it('creates a separate domain workspace and applies its real backend configuration', async () => {
  mocks.create.mockResolvedValue({ id: 'new', name: 'Droit des sociétés' })
  show()
  fireEvent.click(await screen.findByText('Droit des sociétés'))
  fireEvent.click(screen.getByRole('button', { name: '+ Créer un espace Droit des sociétés' }))
  await waitFor(() =>
    expect(mocks.request).toHaveBeenCalledWith('legal.workspace.set', {
      profile: 'default',
      project_id: 'new',
      domain: 'societes'
    })
  )
  await waitFor(() => expect(mocks.open).toHaveBeenCalledWith({ id: 'new', name: 'Droit des sociétés' }, 'matters'))
})

it('does not apply or open a late creation after the owner changed', async () => {
  let resolve!: (value: unknown) => void
  mocks.create.mockReturnValue(
    new Promise(done => {
      resolve = done
    })
  )
  show()
  fireEvent.click(await screen.findByText('Droit des sociétés'))
  fireEvent.click(screen.getByRole('button', { name: '+ Créer un espace Droit des sociétés' }))
  mocks.current = false
  resolve({ id: 'old-owner', name: 'Droit des sociétés' })
  await waitFor(() =>
    expect(screen.getByRole('button', { name: '+ Créer un espace Droit des sociétés' }).hasAttribute('disabled')).toBe(
      false
    )
  )
  expect(mocks.open).not.toHaveBeenCalled()
  expect(mocks.request.mock.calls.every(([method]) => method === 'legal.catalog')).toBe(true)
})
