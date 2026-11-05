import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { testLocalModelInference } from '@/hermes'
import { isCurrentLocalModelsOwner, localModelsRequestScope, watchLocalRuntimeJobs } from '@/store/local-runtime-jobs'
import type { LocalRuntimeJob } from '@/types/hermes'

import { useScopedLocalModelsOwner } from './local-models-owner'

export function LocalModelsInference({ modelId, jobs }: { modelId: string | null; jobs: readonly LocalRuntimeJob[] }) {
  const owner = useScopedLocalModelsOwner()
  const client = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const test = jobs.find(job => job.kind === 'model-inference-test' && job.model_id === modelId)

  return (
    <section className="my-4 space-y-2 rounded border p-3">
      <h3 className="font-semibold">Diagnostic d’inférence</h3>
      <p>
        Teste la génération de texte du modèle actif. Le premier test charge ses poids en mémoire. Les outils, la vision
        et la qualité juridique nécessitent des essais distincts.
      </p>
      <Button
        disabled={!modelId || busy || Boolean(test && !['done', 'error'].includes(test.status))}
        onClick={async () => {
          if (!modelId || !isCurrentLocalModelsOwner(owner)) {
            return
          }

          setBusy(true)
          setError('')

          try {
            await testLocalModelInference(modelId, localModelsRequestScope(owner))

            if (isCurrentLocalModelsOwner(owner)) {
              watchLocalRuntimeJobs(owner, client)
            }
          } catch (cause) {
            if (isCurrentLocalModelsOwner(owner)) {
              setError(String(cause))
            }
          } finally {
            setBusy(false)
          }
        }}
      >
        Tester le modèle actif
      </Button>
      {test && <p role="status">{test.error || test.detail || test.status}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  )
}
