import type { AtelierPanel, AtelierSnapshot } from '@hermes/shared'
import { useEffect, useRef, useState } from 'react'

import { getActiveComposer, getVisibleComposerSurfaceId, requestComposerInsert } from '@/app/chat/composer/focus'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import type { HermesGateway } from '@/hermes'

import { atelierPluginPrompt, atelierPrompt } from './atelier-prompts'

export function AtelierDialog({
  gateway,
  profile,
  onClose,
  local = false,
  onOpenPlugins
}: {
  gateway: HermesGateway | null
  profile: string
  onClose: () => void
  local?: boolean
  onOpenPlugins?: () => void
}) {
  const [snapshot, setSnapshot] = useState<AtelierSnapshot>({ revisions: [] })
  const [panel, setPanel] = useState<AtelierPanel | null>(null)
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState<'chronology' | 'desktop-plugin'>('chronology')

  const [request, setRequest] = useState(
    'Crée la chronologie du dossier avec une source précise pour chaque événement.'
  )

  const [pluginRequest, setPluginRequest] = useState(
    'Crée un panneau pour calculer une date après un nombre de jours calendaires, avec un bouton Effacer.'
  )

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const pending = useRef(false)
  const generation = useRef(0)

  const destination = useRef({
    target: getActiveComposer(),
    surface: getVisibleComposerSurfaceId(getActiveComposer())
  })

  async function run(action: (current: () => boolean) => Promise<void>) {
    if (pending.current || !gateway) {
      return
    }
    pending.current = true
    const ticket = generation.current
    const current = () => generation.current === ticket
    setBusy(true)
    setError('')
    setNotice('')

    try {
      await action(current)
    } catch (cause) {
      if (current()) {
        setError(cause instanceof Error ? cause.message : String(cause))
        setPanel(null)
      }
    } finally {
      if (current()) {
        pending.current = false
        setBusy(false)
      }
    }
  }

  // Request generations fence late responses after a profile change or unmount; no atom is mirrored.
  // eslint-disable-next-line no-restricted-syntax
  useEffect(() => {
    const ticket = ++generation.current
    setSnapshot({ revisions: [] })
    setPanel(null)
    setError('')
    setNotice('')
    setQuery('')
    setBusy(Boolean(gateway))
    pending.current = Boolean(gateway)

    if (!gateway) {
      return
    }
    gateway
      .request<AtelierSnapshot>('atelier.list', { profile })
      .then(value => {
        if (generation.current === ticket) {
          setSnapshot(value)
        }
      })
      .catch(cause => {
        if (generation.current === ticket) {
          setError(String(cause))
        }
      })
      .finally(() => {
        if (generation.current === ticket) {
          setBusy(false)
          pending.current = false
        }
      })

    return () => {
      generation.current++
    }
  }, [gateway, profile])

  function prepare() {
    const { target, surface } = destination.current

    if (!surface || getVisibleComposerSurfaceId(target) !== surface) {
      setError('Ouvrez une conversation puis rouvrez l’Atelier pour préparer sa demande.')

      return
    }

    if (kind === 'desktop-plugin') {
      if (!local) {
        setError('Choisissez une connexion locale pour créer un plugin sur cet ordinateur.')

        return
      }

      const ticket = generation.current
      void run(async () => {
        const root = await window.hermesDesktop?.desktopPluginsRoot?.()

        if (ticket !== generation.current || getVisibleComposerSurfaceId(target) !== surface) {
          return
        }

        if (!root) {
          throw new Error('Cette version Desktop ne fournit pas de dossier de plugins.')
        }
        requestComposerInsert(atelierPluginPrompt(pluginRequest, root), { target })
        onClose()
      })
    } else {
      requestComposerInsert(atelierPrompt(request), { target })
      onClose()
    }
  }

  const active = snapshot.revisions.some(row => row.revision === panel?.revision && row.active)

  const events =
    panel?.events.filter(event =>
      `${event.date} ${event.title} ${event.evidence.map(e => `${e.name} ${e.quote}`).join(' ')}`
        .toLocaleLowerCase()
        .includes(query.toLocaleLowerCase())
    ) ?? []

  return (
    <Dialog
      onOpenChange={open => {
        if (!open) {
          onClose()
        }
      }}
      open
    >
      <DialogContent className="w-[min(64rem,calc(100vw-2rem))] max-w-none">
        <DialogHeader>
          <DialogTitle>Atelier Actelyo</DialogTitle>
          <DialogDescription>Créez une chronologie sourcée ou un plugin d’interface avec l’agent.</DialogDescription>
        </DialogHeader>
        <p>
          Profil de l’agent : {profile}. Les chronologies appartiennent à ce profil ; les plugins d’interface
          appartiennent à l’application locale.
        </p>
        <div aria-label="Type d’extension" className="flex gap-2">
          <Button aria-pressed={kind === 'chronology'} onClick={() => setKind('chronology')} variant="outline">
            Chronologie sourcée
          </Button>
          <Button aria-pressed={kind === 'desktop-plugin'} onClick={() => setKind('desktop-plugin')} variant="outline">
            Plugin d’interface
          </Button>
        </div>
        {kind === 'desktop-plugin' && (
          <p>
            Les plugins d’interface appartiennent à cette application sur cet ordinateur, avec ses droits. Examinez leur
            code et leurs tests avant de les activer dans Plugins.
          </p>
        )}
        {kind === 'desktop-plugin' && (
          <p>Utilisez un modèle capable de programmer et d’exécuter les outils de la conversation.</p>
        )}
        <label className="grid gap-2">
          Demande à l’agent
          <textarea
            className="rounded border p-2"
            onChange={e => (kind === 'chronology' ? setRequest(e.target.value) : setPluginRequest(e.target.value))}
            value={kind === 'chronology' ? request : pluginRequest}
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={!gateway || busy || !(kind === 'chronology' ? request : pluginRequest).trim()}
            onClick={prepare}
          >
            Préparer la création dans le chat
          </Button>
          {kind === 'desktop-plugin' && (
            <Button
              disabled={!onOpenPlugins}
              onClick={() => {
                onClose()
                onOpenPlugins?.()
              }}
              variant="outline"
            >
              Ouvrir les plugins
            </Button>
          )}
          <Button
            disabled={!gateway || busy}
            onClick={() =>
              void run(async current => {
                const value = await gateway!.request<AtelierSnapshot>('atelier.list', {
                  profile
                })

                if (!current()) {
                  return
                }
                setSnapshot(value)
                setPanel(null)
                setNotice('Versions actualisées.')
              })
            }
            variant="outline"
          >
            Actualiser
          </Button>
        </div>
        {!gateway && <p role="alert">Connectez ce profil pour accéder à l’Atelier.</p>}
        {busy && <p role="status">Chargement…</p>}
        {error && <p role="alert">{error} Vérifiez la connexion et la version du backend, puis actualisez.</p>}
        {notice && <p role="status">{notice}</p>}
        <div className="max-h-[55vh] space-y-4 overflow-y-auto" hidden={kind !== 'chronology'}>
          {!busy && !error && snapshot.revisions.length === 0 && (
            <p>Aucune extension enregistrée. Préparez la demande puis envoyez-la à l’agent.</p>
          )}
          <nav aria-label="Versions des extensions" className="flex flex-wrap gap-2">
            {snapshot.revisions.map(row => (
              <Button
                aria-pressed={panel?.revision === row.revision}
                disabled={busy}
                key={row.revision}
                onClick={() =>
                  void run(async current => {
                    const value = await gateway!.request<AtelierPanel>('atelier.preview', {
                      profile,
                      revision: row.revision
                    })

                    if (!current()) {
                      return
                    }
                    setPanel(value)
                    setQuery('')
                  })
                }
                variant="outline"
              >
                {row.name} · {row.revision.slice(0, 8)} {row.active ? '· Active' : '· Aperçu'}
              </Button>
            ))}
          </nav>
          {panel && (
            <section aria-label="Chronologie sourcée" className="space-y-4">
              <h2>
                {panel.name} — {active ? 'Version active' : 'Aperçu'}
              </h2>
              <p>
                Extraits et dates liés au texte fourni. Vérifiez le sens des événements et l’authenticité des pièces
                avant activation.
              </p>
              <div className="flex gap-2">
                <Button
                  disabled={busy || active}
                  onClick={() =>
                    void run(async current => {
                      const value = await gateway!.request<AtelierSnapshot>('atelier.activate', {
                        profile,
                        revision: panel.revision
                      })

                      if (!current()) {
                        return
                      }
                      setSnapshot(value)
                      setNotice('Version activée. Les versions précédentes restent disponibles.')
                    })
                  }
                >
                  Activer cette version après revue
                </Button>
                <Button
                  disabled={busy || !active}
                  onClick={() =>
                    void run(async current => {
                      const value = await gateway!.request<AtelierSnapshot>('atelier.deactivate', {
                        profile,
                        panel_id: panel.id
                      })

                      if (!current()) {
                        return
                      }
                      setSnapshot(value)
                      setNotice('Extension désactivée. Les versions sont conservées.')
                    })
                  }
                  variant="outline"
                >
                  Désactiver
                </Button>
              </div>
              <label className="grid gap-2">
                Filtrer les événements et les sources
                <input className="rounded border p-2" onChange={e => setQuery(e.target.value)} value={query} />
              </label>
              <p>{events.length} événement(s)</p>
              <ol className="space-y-4">
                {events.map(event => (
                  <li key={event.id}>
                    <p>
                      <time dateTime={event.date}>{event.date}</time> — {event.title}
                    </p>
                    {event.evidence.map(e => (
                      <details key={e.passage_id}>
                        <summary>
                          Source : {e.name} · {e.page === null ? 'page non renseignée' : `page ${e.page}`}
                        </summary>
                        <blockquote className="whitespace-pre-wrap">{e.quote}</blockquote>
                        <p className="break-all">{e.url}</p>
                        <p>
                          Caractères {e.start}–{e.end} du texte extrait · {e.passage_id}
                        </p>
                        <p className="break-all">SHA-256 : {e.source_sha256}</p>
                        {Boolean(e.table) && (
                          <p>Les données de ligne et de colonne sont conservées dans cette référence.</p>
                        )}
                      </details>
                    ))}
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
