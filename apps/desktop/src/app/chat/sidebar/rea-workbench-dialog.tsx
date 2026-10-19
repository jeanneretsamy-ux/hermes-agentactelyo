import { useRef, useState } from 'react'
import { useNavigate } from 'react-router'

import { installBundledEntry } from '@/app/capabilities/mcp/install-catalog-entry'
import { useMcpServers } from '@/app/capabilities/mcp/use-mcp-servers'
import { getActiveComposer, getVisibleComposerSurfaceId, requestComposerInsert } from '@/app/chat/composer/focus'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import type { HermesGateway } from '@/hermes'

export function ReaWorkbenchDialog({
  gateway,
  profile,
  onClose
}: {
  gateway: HermesGateway | null
  profile: string
  onClose: () => void
}) {
  const mcp = useMcpServers({ gateway, profile })
  const navigate = useNavigate()
  const [application, setApplication] = useState('')
  const [feature, setFeature] = useState('')
  const [workspace, setWorkspace] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const destination = useRef({ target: getActiveComposer(), surface: getVisibleComposerSurfaceId(getActiveComposer()) })
  const entry = mcp.availableCatalog.find(item => item.name === 'rea')
  const installed = Boolean(mcp.servers.rea)
  const status = mcp.statuses.rea
  const count = mcp.toolCounts.rea
  const ready = status === 'ok' && (count?.on ?? 0) > 0

  async function connect() {
    setBusy(true)
    setError('')

    try {
      if (!installed && entry) {
        await installBundledEntry(entry, {}, profile)
        await mcp.onCatalogInstalled()
      } else if (installed) {
        await mcp.setServerEnabled('rea', true)
        await mcp.runProbe('rea')
      }
    } catch (cause) {
      setError(String(cause))
    } finally {
      setBusy(false)
    }
  }

  function prepare() {
    const { target, surface } = destination.current

    if (!surface || getVisibleComposerSurfaceId(target) !== surface) {
      setError('Ouvrez une conversation puis ouvrez REA pour préparer sa demande.')

      return
    }

    requestComposerInsert(
      [
        `Avec le connecteur REA, analyse cette application autorisée : ${application.trim()}.`,
        `Fonctionnalité à comprendre et à créer : ${feature.trim()}.`,
        `Projet de destination : ${workspace.trim()}.`,
        'Vérifie les outils réellement disponibles du serveur REA et leurs schémas. Commence par binary_session puis utilise analyze_javascript_application et les vues de preuve adaptées. Si REA est absent de cette session, demande une nouvelle conversation après activation ; ne prétends pas l’avoir appelé.',
        'Rapporte les observations et les limites de l’analyse. Lis les instructions et le code du projet de destination, puis crée une implémentation Actelyo originale avec les outils de fichiers et de terminal disponibles. Ne copie pas de sources, secrets ou éléments propriétaires de l’application de référence.',
        'Exécute les vérifications pertinentes et relis les modifications. Signale ce qui est seulement codé, testé ou réellement exécuté. Ne publie pas et n’installe pas de logiciels ou modèles sans demande explicite.'
      ].join('\n\n'),
      { target }
    )
    onClose()
  }

  return (
    <Dialog
      onOpenChange={open => {
        if (!open) {
          onClose()
        }
      }}
      open
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>REA — créer des fonctionnalités</DialogTitle>
          <DialogDescription>
            Analyser une application autorisée puis coder dans votre projet avec l’agent.
          </DialogDescription>
        </DialogHeader>
        <p>
          Profil : {profile}. REA s’exécute sur la machine de la connexion active. Les chemins doivent être accessibles
          sur cette machine.
        </p>
        <p role="status">
          {ready
            ? `Connecté — ${count?.on} outils actifs`
            : status === 'probing'
              ? 'Vérification en cours…'
              : installed
                ? 'Connecteur configuré ; connexion à vérifier'
                : 'Connecteur non installé'}
        </p>
        <p>
          La première connexion télécharge REA depuis npm. Après activation, ouvrez une nouvelle conversation pour que
          l’agent dispose des outils.
        </p>
        <div className="flex gap-2">
          <Button
            disabled={busy || mcp.configLoading || mcp.profilePending || (!installed && !entry)}
            onClick={() => void connect()}
          >
            {installed ? 'Activer et vérifier REA' : 'Installer et connecter REA'}
          </Button>
          <Button
            onClick={() => {
              onClose()
              navigate('/capabilities?tab=connectors&connector=local%3Area')
            }}
            variant="outline"
          >
            Voir les outils
          </Button>
        </div>
        {error && <p role="alert">{error}</p>}
        <label>
          Chemin de l’application à analyser
          <input
            className="w-full rounded border p-2"
            onChange={e => setApplication(e.target.value)}
            value={application}
          />
        </label>
        <label>
          Fonctionnalité souhaitée
          <textarea className="w-full rounded border p-2" onChange={e => setFeature(e.target.value)} value={feature} />
        </label>
        <label>
          Chemin du projet où coder
          <input className="w-full rounded border p-2" onChange={e => setWorkspace(e.target.value)} value={workspace} />
        </label>
        <Button disabled={!ready || !application.trim() || !feature.trim() || !workspace.trim()} onClick={prepare}>
          Préparer la demande à l’agent
        </Button>
      </DialogContent>
    </Dialog>
  )
}
