import type { LegalDocument, RpcMethods } from '@hermes/shared'
import { atom } from 'nanostores'

import type { HermesGateway } from '@/hermes'
import { activeGateway } from '@/store/gateway'
import { $activeGatewayProfile, normalizeProfileKey } from '@/store/profile'
import { projectProfile } from '@/store/projects'

export interface LegalPracticeOwner {
  gateway: HermesGateway
  profile: string
  projectId: string
  name: string
  section?: LegalPracticeSection
}

export type LegalPracticeSection = 'workspace' | 'matters' | 'acts' | 'billing' | 'tasks'

export const $legalPractice = atom<LegalPracticeOwner | null>(null)
const gatewayIds = new WeakMap<HermesGateway, number>()
let nextGatewayId = 0

export function legalQueryKey(owner: LegalPracticeOwner): (string | number)[] {
  let id = gatewayIds.get(owner.gateway)

  if (id === undefined) {
    id = ++nextGatewayId
    gatewayIds.set(owner.gateway, id)
  }

  return ['legal-practice', id, owner.profile, owner.projectId]
}

export function openLegalPractice(project: { id: string; name: string }, section: LegalPracticeSection = 'workspace'): void {
  const gateway = activeGateway()
  const profile = projectProfile()

  if (!gateway || !profile) {
    return
  }

  $legalPractice.set({ gateway, profile, projectId: project.id, name: project.name, section })
}

export function isLegalOwnerCurrent(owner: LegalPracticeOwner): boolean {
  return (
    activeGateway() === owner.gateway &&
    normalizeProfileKey($activeGatewayProfile.get()) === owner.profile &&
    projectProfile() === owner.profile
  )
}

export type LegalMethod = Extract<keyof RpcMethods, `legal.${string}`>
export type LegalWrite = Exclude<LegalMethod, 'legal.snapshot' | 'legal.catalog'>

export function legalRequest<M extends LegalMethod>(
  owner: LegalPracticeOwner,
  method: M,
  params: Omit<RpcMethods[M]['params'], 'profile' | 'project_id'>
): Promise<RpcMethods[M]['result']> {
  if (!isLegalOwnerCurrent(owner)) {
    return Promise.reject(new Error('Le profil ou la connexion a changé. Rouvrez le cabinet juridique.'))
  }

  return owner.gateway.request<RpcMethods[M]['result']>(method, {
    ...params,
    profile: owner.profile,
    project_id: owner.projectId
  })
}

export function legalMoney(cents: number): string {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(cents / 100)
}

// Parse decimal input without binary floating point. Also used for tax percent → basis points.
export function legalDecimal(value: string): number {
  const match = /^(\d+)(?:[.,](\d{1,2}))?$/.exec(value.trim())

  if (!match) {
    throw new Error('Saisissez un montant positif avec au plus deux décimales.')
  }

  const cents = Number(match[1]) * 100 + Number((match[2] ?? '').padEnd(2, '0'))

  if (!Number.isSafeInteger(cents) || cents > 1_000_000_000) {
    throw new Error('Montant trop élevé.')
  }

  return cents
}

export type LegalDocumentTemplate = NonNullable<LegalDocument['snapshot']['template_id']>

export const LEGAL_DOCUMENT_TEMPLATES: { id: LegalDocumentTemplate; label: string; description: string }[] = [
  { id: 'classique', label: 'Cabinet classique', description: 'Présentation formelle, équilibrée et lisible.' },
  { id: 'synthese', label: 'Synthèse', description: 'Informations essentielles en tête, document plus compact.' },
  { id: 'detaille', label: 'Détaillé', description: 'Prestations et conditions présentées avec davantage de repères.' }
]

export function legalDocumentText(
  doc: LegalDocument,
  template: LegalDocumentTemplate = doc.snapshot.template_id ?? 'classique'
): string {
  const { client, matter, lines } = doc.snapshot
  const issuer = doc.snapshot.issuer
  const terms = doc.snapshot.payment_terms

  const title =
    doc.kind === 'quote'
      ? 'Devis'
      : doc.kind === 'credit_note'
        ? `Avoir d’annulation de ${doc.snapshot.credited_invoice_reference ?? 'facture'}`
        : doc.purpose === 'provision_fees'
          ? 'Facture de provision sur honoraires'
          : doc.purpose === 'provision_expenses_fees'
            ? 'Facture de provision sur frais et honoraires'
            : 'Facture'

  const header =
    template === 'synthese'
      ? [
          `# ${title} ${doc.reference} — BROUILLON`,
          `**Total TTC : ${legalMoney(doc.total_cents)}**`,
          `Émis le ${doc.created_on} · Échéance ${doc.due_on}`
        ]
      : [
          `# ${title} — BROUILLON`,
          `Référence : ${doc.reference}`,
          `Date : ${doc.created_on} | Échéance : ${doc.due_on}`
        ]

  const itemLines =
    template === 'synthese'
      ? lines.map(
          line =>
            `- **${line.description}** — ${legalMoney(line.net_cents)} HT, TVA ${line.tax_bps / 100} % (${legalMoney(line.tax_cents)}), soit ${legalMoney(line.net_cents + line.tax_cents)} TTC`
        )
      : template === 'detaille'
        ? lines.map(
            (line, index) =>
              `${index + 1}. **${line.description}**\n   Montant HT : ${legalMoney(line.net_cents)} · Taux TVA : ${line.tax_bps / 100} % · TVA : ${legalMoney(line.tax_cents)} · TTC : ${legalMoney(line.net_cents + line.tax_cents)}`
          )
        : lines.map(
            line =>
              `${line.description} — HT ${legalMoney(line.net_cents)} — TVA ${line.tax_bps / 100} % : ${legalMoney(line.tax_cents)}`
          )

  return [
    ...header,
    ...(issuer
      ? [
          `Émetteur : ${issuer.legal_name}\n${issuer.address}\nSIREN ${issuer.siren}${issuer.vat_number ? ` · TVA ${issuer.vat_number}` : ''}${issuer.bar_name ? ` · Barreau ${issuer.bar_name}` : ''}`
        ]
      : []),
    `Client : ${client.name}\n${client.address}\n${client.email}`,
    ...(client.customer_type === 'professional' && client.siren
      ? [`Client professionnel — SIREN ${client.siren}`]
      : []),
    `Dossier : ${matter.title} (${matter.reference})`,
    ...(() => {
      const company = matter.company_profile?.company_details

      if (!company) {
        return []
      }

      const fields = [
        ['registered_name', 'Dénomination sociale'],
        ['legal_form', 'Forme juridique'],
        ['registered_office', 'Siège social'],
        ['registration_number', 'RCS / registre'],
        ['siren', 'SIREN'],
        ['siret', 'SIRET'],
        ['vat_number', 'N° TVA']
      ] as const

      const lines = fields.filter(([key]) => company[key]).map(([key, label]) => `- ${label} : ${company[key]}`)

      return lines.length ? ['Société concernée par le dossier', ...lines] : []
    })(),
    ...(template === 'detaille' ? ['Détail des prestations'] : []),
    ...itemLines,
    `Total HT : ${legalMoney(doc.net_cents)}\nTVA : ${legalMoney(doc.tax_cents)}\nTotal TTC : ${legalMoney(doc.total_cents)}`,
    ...(doc.snapshot.vat_notice ? [doc.snapshot.vat_notice] : []),
    ...(terms
      ? [
          `Paiement : échéance au ${terms.due_on} (${terms.delay_days} jours)\nPénalités de retard : ${terms.late_penalty_rate}${client.customer_type === 'professional' ? '\nIndemnité forfaitaire pour frais de recouvrement : 40,00 €' : ''}`
        ]
      : []),
    `Règlements saisis : ${legalMoney(doc.paid_cents)}\nSolde : ${legalMoney(doc.balance_cents)}`,
    'Document de travail interne. À compléter et valider avant toute émission au client.'
  ].join('\n\n')
}

export function downloadLegalText(name: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
