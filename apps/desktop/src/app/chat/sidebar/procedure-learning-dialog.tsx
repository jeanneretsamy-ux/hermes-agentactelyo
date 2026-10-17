import { useEffect, useRef, useState } from 'react'

import {
  getActiveComposer,
  getVisibleComposerSurfaceId,
  requestComposerAttachImages,
  requestComposerInsert
} from '@/app/chat/composer/focus'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'

import type { ProcedureSource } from '../../../../electron/procedure-capture-types'

import { procedureLearningRequest } from './procedure-learning'

interface Step {
  id: string
  at: string
  note: string
  blob: Blob
  url: string
}

export function ProcedureLearningDialog({ onClose }: { onClose: () => void }) {
  const api = window.hermesDesktop?.procedureCapture
  const [sources, setSources] = useState<ProcedureSource[]>([])
  const [source, setSource] = useState('')
  const [goal, setGoal] = useState('')
  const [steps, setSteps] = useState<Step[]>([])
  const [recording, setRecording] = useState(false)
  const [starting, setStarting] = useState(false)
  const [joining, setJoining] = useState(false)
  const [error, setError] = useState('')
  const token = useRef<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mounted = useRef(true)
  const urls = useRef(new Set<string>())
  const destination = useRef({ target: getActiveComposer(), surface: getVisibleComposerSurfaceId(getActiveComposer()) })

  // eslint-disable-next-line no-restricted-syntax -- Mount lifecycle guard; no reactive value is mirrored.
  useEffect(() => {
    mounted.current = true
    const ownedUrls = urls.current

    return () => {
      mounted.current = false

      if (timer.current) {
        clearTimeout(timer.current)
      }

      if (token.current) {
        void api?.stop(token.current)
      }

      token.current = null

      for (const url of ownedUrls) {
        URL.revokeObjectURL(url)
      }

      ownedUrls.clear()
    }
  }, [api])

  const stop = () => {
    if (timer.current) {
      clearTimeout(timer.current)
    }

    if (token.current) {
      void api?.stop(token.current)
    }

    token.current = null
    setRecording(false)
  }

  async function loadSources() {
    setError('')

    try {
      const found = await api!.sources()

      if (mounted.current) {
        setSources(found)
        setSource('')
      }
    } catch (cause) {
      if (mounted.current) {
        setError(String(cause))
      }
    }
  }

  async function start() {
    setStarting(true)
    setError('')

    try {
      const grant = await api!.start(source)

      if (!grant) {
        return
      }

      if (!mounted.current) {
        await api!.stop(grant.token)

        return
      }

      for (const url of urls.current) {
        URL.revokeObjectURL(url)
      }

      urls.current.clear()
      setSteps([])
      token.current = grant.token
      setRecording(true)
      let count = 0

      const capture = async () => {
        try {
          const image = await api!.capture(grant.token)

          if (!mounted.current || token.current !== grant.token) {
            return
          }

          const blob = new Blob([new Uint8Array(image.png)], { type: 'image/png' })
          const url = URL.createObjectURL(blob)
          urls.current.add(url)
          setSteps(previous => [...previous, { id: crypto.randomUUID(), at: image.at, note: '', blob, url }])
          count += 1

          if (count >= 12) {
            stop()
          } else {
            timer.current = setTimeout(() => void capture(), 5000)
          }
        } catch (cause) {
          if (mounted.current && token.current === grant.token) {
            stop()
            setError(String(cause))
          }
        }
      }

      timer.current = setTimeout(() => void capture(), 3000)
    } catch (cause) {
      if (mounted.current) {
        setError(String(cause))
      }
    } finally {
      if (mounted.current) {
        setStarting(false)
      }
    }
  }

  function prepare() {
    const { target, surface } = destination.current

    if (!surface || getVisibleComposerSurfaceId(target) !== surface || target === 'edit') {
      setError('Ouvrez une conversation, puis relancez l’apprentissage depuis cette conversation.')

      return
    }

    try {
      const text = procedureLearningRequest(goal, steps)
      setJoining(true)
      let timedOut = false

      const timeout = setTimeout(() => {
        timedOut = true

        if (mounted.current) {
          setJoining(false)
          setError('Pièces jointes non confirmées. Vérifiez la conversation avant de réessayer.')
        }
      }, 60_000)

      const isCurrent = () => !timedOut && mounted.current && getVisibleComposerSurfaceId(target) === surface
      requestComposerAttachImages(
        steps.map(step => step.blob),
        {
          target,
          surfaceId: surface,
          isCurrent,
          onComplete: ok => {
            clearTimeout(timeout)

            if (!isCurrent()) {
              return
            }

            setJoining(false)

            if (!ok) {
              setError('Certaines images n’ont pas pu être jointes. Vérifiez les pièces jointes de la conversation.')

              return
            }

            requestComposerInsert(text, { target })
            onClose()
          }
        }
      )
    } catch (cause) {
      setError(String(cause))
    }
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
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Apprendre une procédure</DialogTitle>
          <DialogDescription>
            Montrez une procédure, relisez les captures, puis demandez à l’agent d’en créer un skill.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <p>
            Une fenêtre, une minute, une image toutes les 5 secondes. Aucun enregistrement du clavier ni du son. Les
            gestes rapides peuvent manquer : ajoutez vos explications. Fermer cette fenêtre arrête et efface les
            captures non jointes.
          </p>
          <label className="block">
            Objectif de la procédure
            <input
              className="w-full rounded border p-2"
              onChange={e => setGoal(e.target.value)}
              placeholder="Ex. créer un dossier et préparer une lettre"
              value={goal}
            />
          </label>
          {!api && <p role="alert">Cette fonction nécessite la nouvelle version de l’application Desktop.</p>}
          <div className="flex flex-wrap gap-2">
            <Button disabled={!api || recording || starting || joining} onClick={() => void loadSources()}>
              Choisir une fenêtre
            </Button>
            <select
              aria-label="Fenêtre à observer"
              disabled={recording || starting}
              onChange={e => setSource(e.target.value)}
              value={source}
            >
              <option value="">Sélectionner…</option>
              {sources.map(item => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            <Button
              disabled={!api || !source || !goal.trim() || recording || starting || joining}
              onClick={() => void start()}
            >
              Démarrer
            </Button>
            {recording && <Button onClick={stop}>Arrêter les captures</Button>}
          </div>
          {recording && (
            <p role="status">
              Capture en cours — {steps.length}/12. Passez dans la fenêtre choisie et montrez votre procédure.
            </p>
          )}
          {error && <p role="alert">{error}</p>}
          {!recording &&
            steps.map((step, index) => (
              <div className="space-y-2" key={step.id}>
                <p>
                  Étape {index + 1} — {new Date(step.at).toLocaleTimeString()}
                </p>
                <img alt={`Capture de l’étape ${index + 1}`} className="max-h-64 max-w-full" src={step.url} />
                <input
                  aria-label={`Explication de l’étape ${index + 1}`}
                  className="w-full rounded border p-2"
                  onChange={e =>
                    setSteps(previous =>
                      previous.map(item => (item.id === step.id ? { ...item, note: e.target.value } : item))
                    )
                  }
                  placeholder="Décrivez votre action et le résultat attendu"
                  value={step.note}
                />
                <Button
                  onClick={() => {
                    URL.revokeObjectURL(step.url)
                    urls.current.delete(step.url)
                    setSteps(previous => previous.filter(item => item.id !== step.id))
                  }}
                  variant="outline"
                >
                  Supprimer cette capture
                </Button>
              </div>
            ))}
          <p>
            Après validation, les captures choisies seront jointes au brouillon de la conversation. Relisez-le avant
            d’envoyer : le modèle sélectionné recevra ces images. La création du skill et son essai seront visibles dans
            la conversation.
          </p>
          <Button disabled={recording || starting || joining || !steps.length || !goal.trim()} onClick={prepare}>
            Joindre les étapes et préparer la demande de skill
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
