import type { LegalCatalog } from '@hermes/shared'
import { useStore } from '@nanostores/react'
import { useQuery } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { Codicon } from '@/components/ui/codicon'
import { SidebarMenuButton, SidebarMenuItem } from '@/components/ui/sidebar'
import { $gateway } from '@/store/gateway'
import {
  isLegalOwnerCurrent,
  type LegalPracticeSection,
  legalQueryKey,
  openLegalPractice
} from '@/store/legal-practice'
import { $activeGatewayProfile, $profileScope } from '@/store/profile'
import { createProject, enterProject, projectProfile } from '@/store/projects'

const sections: [LegalPracticeSection, string][] = [
  ['workspace', 'Structure du domaine'],
  ['matters', 'Clients et dossiers'],
  ['acts', 'Bibliothèque et rédaction'],
  ['tasks', 'Processus et échéances'],
  ['billing', 'Facturation']
]

export function LegalCabinetNavigation() {
  const gateway = useStore($gateway)
  const profile = useStore($activeGatewayProfile)
  const scope = useStore($profileScope)

  // Remount all transient state when the cabinet owner changes.
  return <LegalCabinetTree gateway={gateway} key={`${profile}:${scope}`} />
}

function LegalCabinetTree({ gateway }: { gateway: ReturnType<typeof $gateway.get> }) {
  const [expanded, setExpanded] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pending = useRef(false)
  const profile = projectProfile()
  const owner = gateway && profile ? { gateway, profile, projectId: '', name: '' } : null

  const catalog = useQuery({
    queryKey: owner ? [...legalQueryKey(owner), 'catalog'] : ['legal-cabinet-unavailable'],
    queryFn: () => gateway!.request<LegalCatalog>('legal.catalog', { profile }),
    enabled: Boolean(owner && expanded),
    refetchInterval: expanded ? 30_000 : false,
    retry: false
  })

  const data = catalog.data

  const open = (workspace: { id: string; name: string }, section: LegalPracticeSection) => {
    if (!owner || !isLegalOwnerCurrent(owner)) {
      return
    }

    enterProject(workspace.id)
    openLegalPractice(workspace, section)
  }

  const create = async (domain: LegalCatalog['domains'][number]) => {
    if (!owner || pending.current || !isLegalOwnerCurrent(owner)) {
      return
    }

    pending.current = true
    setBusy(true)
    setError('')

    try {
      const project = await createProject({ name: domain.label, use: false })

      if (!project || !isLegalOwnerCurrent(owner)) {
        return
      }

      // The project is retained on failure, visible under "Espaces à classer".
      // Never rewrite another workspace's domain to satisfy a navigation click.
      await gateway!.request('legal.workspace.set', {
        profile: owner.profile,
        project_id: project.id,
        domain: domain.id
      })

      if (isLegalOwnerCurrent(owner)) {
        await catalog.refetch()
        open(project, 'matters')
      }
    } catch (cause) {
      if (isLegalOwnerCurrent(owner)) {
        setError(cause instanceof Error ? cause.message : String(cause))
        void catalog.refetch()
      }
    } finally {
      pending.current = false
      setBusy(false)
    }
  }

  return (
    <SidebarMenuItem>
      <SidebarMenuButton aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
        <Codicon name="law" />
        Cabinet juridique
        <Codicon name={expanded ? 'chevron-down' : 'chevron-right'} />
      </SidebarMenuButton>
      {expanded && (
        <nav aria-label="Domaines du cabinet juridique" className="max-h-[45vh] space-y-1 overflow-y-auto pl-3 text-sm">
          {!owner && <p className="p-2">Sélectionnez un profil connecté pour ouvrir son cabinet.</p>}
          {owner && catalog.isPending && <p role="status">Chargement des domaines…</p>}
          {(error || catalog.isError) && (
            <div className="p-2 text-destructive" role="alert">
              {error || 'Impossible de charger le cabinet. Vérifiez la connexion et la version du backend.'}
              <button onClick={() => void catalog.refetch()} type="button">
                Réessayer
              </button>
            </div>
          )}
          {owner &&
            data?.domains.map(domain => (
              <details key={domain.id}>
                <summary className="cursor-pointer rounded px-2 py-1.5">{domain.label}</summary>
                <div className="space-y-1 border-l pl-3">
                  {data.workspaces
                    .filter(workspace => workspace.domain === domain.id)
                    .map(workspace => (
                      <details key={workspace.id} open>
                        <summary className="cursor-pointer px-2 py-1">
                          {workspace.name}
                          {Boolean(workspace.due_tasks) && (
                            <span role="status"> — {workspace.due_tasks} rappel(s)</span>
                          )}
                        </summary>
                        {sections.map(([section, label]) => (
                          <button
                            className="block w-full rounded px-3 py-1 text-left hover:bg-(--chrome-action-hover)"
                            key={section}
                            onClick={() => open(workspace, section)}
                            type="button"
                          >
                            {label}
                          </button>
                        ))}
                      </details>
                    ))}
                  <button
                    className="px-2 py-1 text-left"
                    disabled={busy}
                    onClick={() => void create(domain)}
                    type="button"
                  >
                    + Créer un espace {domain.label}
                  </button>
                </div>
              </details>
            ))}
          {owner && data?.workspaces.some(workspace => !workspace.domain) && (
            <details>
              <summary className="cursor-pointer px-2 py-1.5">Espaces à classer</summary>
              {data.workspaces
                .filter(workspace => !workspace.domain)
                .map(workspace => (
                  <button
                    className="block px-4 py-1 text-left"
                    key={workspace.id}
                    onClick={() => open(workspace, 'workspace')}
                    type="button"
                  >
                    {workspace.name}
                  </button>
                ))}
            </details>
          )}
        </nav>
      )}
    </SidebarMenuItem>
  )
}
