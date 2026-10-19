import type { LegalSnapshot } from '@hermes/shared'
import { describe, expect, it } from 'vitest'

import { legalDraftRequest } from './drafting'

describe('legal drafting request', () => {
  const data = {
    project_id: 'project-a',
    domain: 'societes',
    domains: [{ id: 'societes', label: 'Droit des sociétés' }],
    clients: [{ id: 'client-a', name: 'Entreprise exemple' }],
    matters: [
      {
        id: 'matter-a',
        client_id: 'client-a',
        title: 'Création SAS',
        matter_type: 'Constitution',
        matter_profile: { company: { capital: '5000 EUR' } }
      }
    ]
  } as unknown as LegalSnapshot

  it('carries the selected project, matter and known facts into a complete-document request', () => {
    const request = legalDraftRequest(data, 'matter-a', 'Statuts SAS')
    expect(request).toContain('project="project-a"')
    expect(request).toContain('Statuts SAS')
    expect(request).toContain('5000 EUR')
    expect(request).toContain('Entreprise exemple')
    expect(request).toContain('tous les articles')
  })

  it('rejects a dossier outside the snapshot rather than drafting for another client', () => {
    expect(() => legalDraftRequest(data, 'other-matter', 'Statuts')).toThrow('dossier enregistré')
  })
})
