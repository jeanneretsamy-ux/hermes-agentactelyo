import { beforeEach, expect, it, vi } from 'vitest'

const host = vi.hoisted(() => ({
  handlers: new Map<string, (...args: any[]) => any>(),
  sources: vi.fn(),
  confirm: vi.fn(),
  window: { isDestroyed: () => false }
}))

vi.mock('electron', () => ({
  BrowserWindow: { fromWebContents: () => host.window },
  desktopCapturer: { getSources: host.sources },
  dialog: { showMessageBox: host.confirm },
  ipcMain: { handle: (name: string, handler: (...args: any[]) => any) => host.handlers.set(name, handler) }
}))
import { installProcedureCapture } from './procedure-capture'

const frame = { url: 'file:///app/index.html' }
const event = (id = 1) => ({ sender: { id, mainFrame: frame, once: vi.fn() }, senderFrame: frame })

const call = (name: string, e: ReturnType<typeof event>, value?: unknown) =>
  host.handlers.get(`actelyo:procedure:${name}`)!(e, value)

beforeEach(() => {
  vi.useRealTimers()
  host.handlers.clear()
  host.sources
    .mockReset()
    .mockResolvedValue([
      { id: 'window:7', name: 'Exemple', thumbnail: { isEmpty: () => false, toPNG: () => new Uint8Array([1, 2]) } }
    ])
  host.confirm.mockReset().mockResolvedValue({ response: 1 })
  installProcedureCapture({ rendererUrl: frame.url })
})

it('requires native consent and never captures on source listing', async () => {
  await call('sources', event())
  expect(host.sources).toHaveBeenLastCalledWith({ types: ['window'], thumbnailSize: { width: 0, height: 0 } })
  host.confirm.mockResolvedValue({ response: 0 })
  expect(await call('start', event(), 'window:7')).toBeNull()
  await expect(call('capture', event(), 'invented')).rejects.toThrow('arrêtée')
})

it('binds grants to the owning window and revokes on stop', async () => {
  const { token } = await call('start', event(), 'window:7')
  await expect(call('capture', event(2), token)).rejects.toThrow()
  expect((await call('capture', event(), token)).png).toEqual(new Uint8Array([1, 2]))
  call('stop', event(), token)
  await expect(call('capture', event(), token)).rejects.toThrow()
})

it('enforces the frame bound and expiry independently of the renderer', async () => {
  const { token } = await call('start', event(), 'window:7')

  for (let index = 0; index < 12; index += 1) {
    await call('capture', event(), token)
  }

  await expect(call('capture', event(), token)).rejects.toThrow()
  vi.useFakeTimers()
  const next = await call('start', event(), 'window:7')
  vi.advanceTimersByTime(65_001)
  await expect(call('capture', event(), next.token)).rejects.toThrow()
  vi.useRealTimers()
})

it('refuses guest frames and drops a capture revoked while the OS was working', async () => {
  const guest = { ...event(), senderFrame: { url: 'https://untrusted.example/' } }
  await expect(call('sources', guest)).rejects.toThrow('Untrusted')
  const { token } = await call('start', event(), 'window:7')
  let complete!: (sources: unknown[]) => void
  host.sources.mockImplementationOnce(
    () =>
      new Promise(resolve => {
        complete = resolve
      })
  )
  const pending = call('capture', event(), token)
  call('stop', event(), token)
  complete([])
  await expect(pending).rejects.toThrow('arrêtée')
})
