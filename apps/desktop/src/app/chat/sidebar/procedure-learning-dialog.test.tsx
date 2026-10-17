import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

const bus = vi.hoisted(() => ({ attach: vi.fn(), insert: vi.fn() }))
vi.mock('@/app/chat/composer/focus', () => ({
  getActiveComposer: () => 'main',
  getVisibleComposerSurfaceId: () => 'surface',
  requestComposerAttachImages: bus.attach,
  requestComposerInsert: bus.insert
}))
vi.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children }: any) => children,
  DialogContent: ({ children }: any) => <div>{children}</div>,
  DialogHeader: ({ children }: any) => <div>{children}</div>,
  DialogTitle: ({ children }: any) => <h2>{children}</h2>,
  DialogDescription: ({ children }: any) => <p>{children}</p>
}))
import { ProcedureLearningDialog } from './procedure-learning-dialog'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.restoreAllMocks()
  bus.attach.mockReset()
  bus.insert.mockReset()
})

it('captures only after start, lets the user delete evidence, and joins only approved images', async () => {
  vi.useFakeTimers()

  const api = {
    sources: vi.fn().mockResolvedValue([{ id: 'w', name: 'Test' }]),
    start: vi.fn().mockResolvedValue({ token: 't', name: 'Test' }),
    capture: vi.fn().mockResolvedValue({ png: [1], at: '2026-10-18T10:00:00Z' }),
    stop: vi.fn().mockResolvedValue(undefined)
  }

  Object.defineProperty(window, 'hermesDesktop', { configurable: true, value: { procedureCapture: api } })
  URL.createObjectURL = vi.fn(() => 'blob:test')
  URL.revokeObjectURL = vi.fn()
  render(<ProcedureLearningDialog onClose={vi.fn()} />)
  expect(api.capture).not.toHaveBeenCalled()
  fireEvent.change(screen.getByPlaceholderText(/créer un dossier/), { target: { value: 'Faire une lettre' } })
  await act(async () => {
    fireEvent.click(screen.getByText('Choisir une fenêtre'))
  })
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'w' } })
  await act(async () => {
    fireEvent.click(screen.getByText('Démarrer'))
  })
  await act(async () => {
    await vi.advanceTimersByTimeAsync(8000)
  })
  expect(api.capture).toHaveBeenCalledTimes(2)
  fireEvent.click(screen.getByText('Arrêter les captures'))
  expect(api.stop).toHaveBeenCalledWith('t')
  fireEvent.click(screen.getAllByText('Supprimer cette capture')[0])
  fireEvent.change(screen.getByLabelText('Explication de l’étape 1'), { target: { value: 'Valider le formulaire' } })
  fireEvent.click(screen.getByText('Joindre les étapes et préparer la demande de skill'))
  expect(bus.attach.mock.calls[0][0]).toHaveLength(1)
  expect(bus.insert).not.toHaveBeenCalled()
  act(() => bus.attach.mock.calls[0][1].onComplete(true))
  expect(bus.insert.mock.calls[0][0]).toContain('Valider le formulaire')
  expect(bus.insert.mock.calls[0][0]).toContain('skill_manage')
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10_000)
  })
  expect(api.capture).toHaveBeenCalledTimes(2)
})

it('revokes a grant that arrives after the dialog was closed', async () => {
  let grant!: (value: unknown) => void

  const api = {
    sources: vi.fn().mockResolvedValue([{ id: 'w', name: 'Test' }]),
    start: vi.fn(
      () =>
        new Promise(resolve => {
          grant = resolve
        })
    ),
    capture: vi.fn(),
    stop: vi.fn().mockResolvedValue(undefined)
  }

  Object.defineProperty(window, 'hermesDesktop', { configurable: true, value: { procedureCapture: api } })
  const view = render(<ProcedureLearningDialog onClose={vi.fn()} />)
  fireEvent.change(screen.getByPlaceholderText(/créer un dossier/), { target: { value: 'Test' } })
  await act(async () => {
    fireEvent.click(screen.getByText('Choisir une fenêtre'))
  })
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'w' } })
  fireEvent.click(screen.getByText('Démarrer'))
  view.unmount()
  await act(async () => {
    grant({ token: 'late', name: 'Test' })
  })
  expect(api.stop).toHaveBeenCalledWith('late')
  expect(api.capture).not.toHaveBeenCalled()
})
