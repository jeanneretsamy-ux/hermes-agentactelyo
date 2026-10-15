import type { LegalDocument } from '@hermes/shared'
import { describe, expect, it } from 'vitest'

import { legalDocumentText, legalMoney } from './legal-practice'

const document: LegalDocument = {
  id: 'doc-1',
  matter_id: 'matter-1',
  kind: 'quote',
  reference: 'DEV-BROUILLON-2026-00001',
  created_on: '2026-10-15',
  due_on: '2026-11-14',
  snapshot: {
    client: { name: 'Client Exemple', email: 'client@example.test', address: '1 rue Exemple' },
    matter: { title: 'Dossier social', reference: 'SOC-12' },
    lines: [{ description: 'Consultation', net_cents: 10000, tax_bps: 2000, tax_cents: 2000 }]
  },
  net_cents: 10000,
  tax_cents: 2000,
  total_cents: 12000,
  paid_cents: 0,
  balance_cents: 12000
}

describe('legalDocumentText template selection', () => {
  it('keeps all totals and switches the selected item presentation', () => {
    const classic = legalDocumentText(document, 'classique')
    const summary = legalDocumentText(document, 'synthese')
    const detailed = legalDocumentText(document, 'detaille')

    expect(classic).toContain(`Consultation — HT ${legalMoney(10000)} — TVA 20 % : ${legalMoney(2000)}`)
    expect(summary).toContain(
      `Consultation** — ${legalMoney(10000)} HT, TVA 20 % (${legalMoney(2000)}), soit ${legalMoney(12000)} TTC`
    )
    expect(detailed).toContain('Détail des prestations')

    for (const text of [classic, summary, detailed]) {
      expect(text).toContain(`Total TTC : ${legalMoney(12000)}`)
      expect(text).toContain('BROUILLON')
    }

    expect(new Set([classic, summary, detailed]).size).toBe(3)
  })
})

