import type { LegalSnapshot, RpcMethods } from '@hermes/shared'
import { useStore } from '@nanostores/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { appendComposerDraft } from '@/store/composer'
import { $gateway } from '@/store/gateway'
import {
  $legalPractice,
  isLegalOwnerCurrent,
  type LegalPracticeOwner,
  legalQueryKey,
  legalRequest,
  type LegalWrite
} from '@/store/legal-practice'
import { $activeGatewayProfile } from '@/store/profile'

import { LegalActsSection } from './legal-practice/acts'
import { LegalBillingSection } from './legal-practice/billing'
import { legalDraftRequest } from './legal-practice/drafting'
import { LegalMattersSection } from './legal-practice/matters'
import { LegalWorkspaceSection } from './legal-practice/workspace'

export function LegalPracticeDialog() {
  const owner = useStore($legalPractice)
  const gateway = useStore($gateway)
  const profile = useStore($activeGatewayProfile)

  useEffect(() => {
    if (owner && !isLegalOwnerCurrent(owner)) {
      $legalPractice.set(null)
    }
  }, [owner, gateway, profile])

  return (
    <Dialog
      onOpenChange={open => {
        if (!open) {
          $legalPractice.set(null)
        }
      }}
      open={Boolean(owner)}
    >
      {owner && (
        <DialogContent bodyClassName="min-w-0 overflow-x-hidden" className="w-[min(72rem,calc(100vw-2rem))] max-w-none">
          <DialogHeader>
            <DialogTitle>Cabinet juridique — {owner.name}</DialogTitle>
            <DialogDescription>Espaces, dossiers, bibliothèque d’actes et facturation du projet.</DialogDescription>
          </DialogHeader>
          <LegalPracticeContent key={`${owner.profile}:${owner.projectId}:${owner.section ?? 'workspace'}`} owner={owner} />
        </DialogContent>
      )}
    </Dialog>
  )
}

export function LegalPracticeContent({ owner }: { owner: LegalPracticeOwner }) {
  const client = useQueryClient()
  // Object identity pins the connection; profile and project pin the business data.
  const queryKey = legalQueryKey(owner)
  const state = useQuery({ queryKey, queryFn: () => legalRequest(owner, 'legal.snapshot', {}), retry: false })
  const [tab, setTab] = useState<string>(owner.section ?? 'workspace')
  const [localError, setLocalError] = useState('')
  const pendingIds = useRef(new Map<string, string>())

  const mutation = useMutation({
    mutationFn: (input: { method: LegalWrite; params: Record<string, unknown> }) =>
      owner.gateway.request<LegalSnapshot>(input.method, {
        ...input.params,
        profile: owner.profile,
        project_id: owner.projectId
      }),
    onSuccess: snapshot => {
      if (isLegalOwnerCurrent(owner)) {
        client.setQueryData(queryKey, snapshot)
        void client.invalidateQueries({ queryKey: [...legalQueryKey({ ...owner, projectId: '' }), 'catalog'] })
      }
    },
    retry: false
  })

  async function write<M extends LegalWrite>(
    method: M,
    params: Omit<RpcMethods[M]['params'], 'profile' | 'project_id' | 'request_id'>
  ): Promise<boolean> {
    setLocalError('')

    try {
      if (!isLegalOwnerCurrent(owner)) {
        throw new Error('Le profil ou la connexion a changé.')
      }

      const key = JSON.stringify({ method, params })
      const moneyOperation = ['legal.fee.add', 'legal.document.create', 'legal.payment.add'].includes(method)
      const requestId = moneyOperation ? (pendingIds.current.get(key) ?? crypto.randomUUID()) : undefined

      if (requestId) {
        pendingIds.current.set(key, requestId)
      }

      await mutation.mutateAsync({ method, params: { ...params, ...(requestId ? { request_id: requestId } : {}) } })
      pendingIds.current.delete(key)

      return true
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : String(error))

      return false
    }
  }

  const submit = (action: () => Promise<void>) => (event: FormEvent) => {
    event.preventDefault()

    if (mutation.isPending) {
      return
    }

    void action().catch(error => setLocalError(error instanceof Error ? error.message : String(error)))
  }

  if (state.isPending) {
    return <p role="status">Chargement du cabinet…</p>
  }

  if (state.isError) {
    return (
      <div role="alert">
        <p>{state.error.message}</p>
        <Button onClick={() => void state.refetch()} type="button">
          Réessayer
        </Button>
      </div>
    )
  }

  const data = state.data

  return (
    <div className="flex min-w-0 flex-col gap-5 text-sm">
      <nav aria-label="Rubriques du cabinet" className="flex flex-wrap gap-2">
        {[
          ['workspace', 'Espace juridique'],
          ['matters', 'Clients et dossiers'],
          ['acts', 'Bibliothèque d’actes'],
          ['billing', 'Facturation']
        ].map(([id, label]) => (
          <Button
            aria-pressed={tab === id}
            key={id}
            onClick={() => setTab(id)}
            type="button"
            variant={tab === id ? 'default' : 'outline'}
          >
            {label}
          </Button>
        ))}
      </nav>
      {localError && (
        <p className="text-destructive" role="alert">
          {localError}
        </p>
      )}
      <fieldset className="min-w-0 space-y-5" disabled={mutation.isPending}>
        <section hidden={tab !== 'workspace'}>
          <LegalWorkspaceSection data={data} submit={submit} write={write} />
        </section>
        <section hidden={tab !== 'matters'}>
          <LegalMattersSection data={data} submit={submit} write={write} />
        </section>
        <section hidden={tab !== 'acts'}>
          <LegalActsSection
            data={data}
            prepareDraft={(matterId, documentType) => {
              if (!isLegalOwnerCurrent(owner)) {
                return
              }

              appendComposerDraft(legalDraftRequest(data, matterId, documentType))
              $legalPractice.set(null)
            }}
            submit={submit}
            write={write}
          />
        </section>
        <section hidden={tab !== 'billing'}>
          <LegalBillingSection data={data} submit={submit} write={write} />
        </section>
      </fieldset>
    </div>
  )
}
