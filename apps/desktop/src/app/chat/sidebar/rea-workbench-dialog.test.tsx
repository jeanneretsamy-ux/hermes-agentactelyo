import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

const mock = vi.hoisted(() => ({ controller: {} as any, install: vi.fn(), insert: vi.fn() }))
vi.mock('react-router', () => ({ useNavigate: () => vi.fn() }))
vi.mock('@/app/capabilities/mcp/use-mcp-servers', () => ({ useMcpServers: () => mock.controller }))
vi.mock('@/app/capabilities/mcp/install-catalog-entry', () => ({ installBundledEntry: mock.install }))
vi.mock('@/app/chat/composer/focus', () => ({
  getActiveComposer: () => 'main',
  getVisibleComposerSurfaceId: () => 'surface',
  requestComposerInsert: mock.insert
}))
vi.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children }: any) => children,
  DialogContent: ({ children }: any) => <div>{children}</div>,
  DialogHeader: ({ children }: any) => <div>{children}</div>,
  DialogTitle: ({ children }: any) => <h2>{children}</h2>,
  DialogDescription: ({ children }: any) => <p>{children}</p>
}))
import { ReaWorkbenchDialog } from './rea-workbench-dialog'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

it('does not claim an installed connector is ready, and installs in the selected profile only on request', async () => {
  const entry = { name: 'rea' }
  mock.controller = {
    servers: {},
    statuses: {},
    toolCounts: {},
    availableCatalog: [entry],
    onCatalogInstalled: vi.fn()
  }
  render(<ReaWorkbenchDialog gateway={null} onClose={vi.fn()} profile="cabinet" />)
  expect(mock.install).not.toHaveBeenCalled()
  expect((screen.getByText('Préparer la demande à l’agent') as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(screen.getByText('Installer et connecter REA'))
  await waitFor(() => expect(mock.install).toHaveBeenCalledWith(entry, {}, 'cabinet'))
})

it('prepares the real analysis and coding request only after tool readiness and paths are supplied', () => {
  mock.controller = {
    servers: { rea: {} },
    statuses: { rea: 'ok' },
    toolCounts: { rea: { on: 4, total: 4 } },
    availableCatalog: []
  }
  render(<ReaWorkbenchDialog gateway={null} onClose={vi.fn()} profile="cabinet" />)
  fireEvent.change(screen.getByLabelText('Chemin de l’application à analyser'), {
    target: { value: 'C:/Example/app.asar' }
  })
  fireEvent.change(screen.getByLabelText('Fonctionnalité souhaitée'), { target: { value: 'Un sélecteur de modèles' } })
  fireEvent.change(screen.getByLabelText('Chemin du projet où coder'), { target: { value: 'C:/Projects/Actelyo' } })
  fireEvent.click(screen.getByText('Préparer la demande à l’agent'))
  expect(mock.insert.mock.calls[0][0]).toContain('C:/Example/app.asar')
  expect(mock.insert.mock.calls[0][0]).toContain('C:/Projects/Actelyo')
  expect(mock.insert.mock.calls[0][0]).toContain('binary_session')
})
