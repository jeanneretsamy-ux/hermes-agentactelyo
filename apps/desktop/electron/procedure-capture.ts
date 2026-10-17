import { randomUUID } from 'node:crypto'

import { BrowserWindow, desktopCapturer, dialog, ipcMain } from 'electron'
import type { IpcMainInvokeEvent } from 'electron'

/** Window-only, explicit native consent; no disk writes, input hooks or ambient capture. */
export function installProcedureCapture({ rendererUrl }: { rendererUrl: string }) {
  const expected = new URL(rendererUrl)
  const grants = new Map<number, { token: string; source: string; expires: number; remaining: number }>()
  const pending = new Set<number>()

  const trusted = (event: IpcMainInvokeEvent) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    const url = new URL(event.senderFrame?.url ?? 'about:blank')

    if (
      !win ||
      event.senderFrame !== event.sender.mainFrame ||
      url.protocol !== expected.protocol ||
      url.host !== expected.host ||
      url.pathname !== expected.pathname
    ) {
      throw new Error('Untrusted capture request')
    }

    return win
  }

  const sources = () => desktopCapturer.getSources({ types: ['window'], thumbnailSize: { width: 0, height: 0 } })
  ipcMain.handle('actelyo:procedure:sources', async event => {
    trusted(event)

    return (await sources()).map(({ id, name }) => ({ id, name }))
  })
  ipcMain.handle('actelyo:procedure:start', async (event, sourceId: unknown) => {
    const win = trusted(event)

    if (pending.has(event.sender.id)) {
      throw new Error('Une demande est déjà ouverte.')
    }

    pending.add(event.sender.id)

    try {
      grants.delete(event.sender.id)
      const source = (await sources()).find(item => item.id === sourceId)

      if (!source) {
        throw new Error('La fenêtre sélectionnée a été fermée.')
      }

      const answer = await dialog.showMessageBox(win, {
        type: 'question',
        title: 'Apprendre une procédure',
        message: `Autoriser les captures de « ${source.name} » pendant une minute ?`,
        detail:
          '12 images maximum, sans son ni saisie clavier. Fermez les données sensibles. Les images restent dans cette fenêtre Actelyo jusqu’à votre validation. Vous pourrez les supprimer avant de les joindre à la conversation et de les envoyer au modèle choisi.',
        buttons: ['Annuler', 'Démarrer les captures'],
        defaultId: 0,
        cancelId: 0
      })

      if (answer.response !== 1 || win.isDestroyed()) {
        return null
      }

      const token = randomUUID()
      grants.set(event.sender.id, { token, source: source.id, expires: Date.now() + 65_000, remaining: 12 })
      event.sender.once('destroyed', () => grants.delete(event.sender.id))

      return { token, name: source.name }
    } finally {
      pending.delete(event.sender.id)
    }
  })
  ipcMain.handle('actelyo:procedure:capture', async (event, token: unknown) => {
    trusted(event)
    const grant = grants.get(event.sender.id)

    if (!grant || token !== grant.token || Date.now() >= grant.expires || grant.remaining <= 0) {
      throw new Error('Capture arrêtée ou expirée.')
    }

    grant.remaining -= 1
    const windows = await desktopCapturer.getSources({ types: ['window'], thumbnailSize: { width: 1280, height: 800 } })

    if (grants.get(event.sender.id) !== grant || Date.now() >= grant.expires) {
      throw new Error('Capture arrêtée.')
    }

    const source = windows.find(item => item.id === grant.source)

    if (!source || source.thumbnail.isEmpty()) {
      grants.delete(event.sender.id)
      throw new Error('La fenêtre est fermée, minimisée ou ne peut pas être capturée.')
    }

    return { png: source.thumbnail.toPNG(), at: new Date().toISOString() }
  })
  ipcMain.handle('actelyo:procedure:stop', (event, token: unknown) => {
    trusted(event)

    if (grants.get(event.sender.id)?.token === token) {
      grants.delete(event.sender.id)
    }
  })
}
