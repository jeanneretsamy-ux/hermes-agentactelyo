import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

import { Choice, Field, type LegalSectionProps, TextField } from './fields'

const COMPANY_SECTIONS = [
  {
    id: 'matter_organization',
    label: 'Résumé, cote et documents du dossier',
    fields: [
      ['summary', 'Résumé'],
      ['cote', 'Cote'],
      ['secondary_sections', 'Rubriques secondaires'],
      ['formulas', 'Formules'],
      ['documents', 'Documents liés'],
      ['models', 'Modèles'],
      ['headers', 'En-têtes']
    ]
  },
  {
    id: 'company_details',
    label: 'Détail société',
    fields: [
      ['registered_name', 'Dénomination sociale'],
      ['legal_form', 'Forme juridique'],
      ['trade_name', 'Nom commercial'],
      ['registration_number', 'RCS / registre et ville'],
      ['siren', 'SIREN'],
      ['siret', 'SIRET'],
      ['vat_number', 'N° TVA intracommunautaire'],
      ['registered_office', 'Siège social'],
      ['activity', 'Activité / objet social'],
      ['financial_year', 'Exercice social'],
      ['duration', 'Durée de la société']
    ]
  },
  {
    id: 'capital_rights',
    label: 'Capital et droits sociaux',
    fields: [
      ['capital', 'Capital social'],
      ['shares', 'Parts / actions et valeur nominale'],
      ['voting_rights', 'Droits de vote'],
      ['special_rights', 'Droits particuliers'],
      ['capital_changes', 'Variations de capital']
    ]
  },
  { id: 'history', label: 'Historique', fields: [['events', 'Événements et modifications']] },
  { id: 'dividends', label: 'Dividendes', fields: [['decisions', 'Décisions et distributions']] },
  {
    id: 'current_accounts',
    label: 'Intérêts de compte courant',
    fields: [['accounts', 'Associé, solde, taux et périodes']]
  },
  {
    id: 'share_transfers',
    label: 'Cessions de parts',
    fields: [['transfers', 'Cédant, cessionnaire, titres, prix et dates']]
  },
  {
    id: 'remuneration',
    label: 'Rémunérations',
    fields: [['remuneration', 'Bénéficiaire, fonction, montants et décisions']]
  },
  {
    id: 'associates',
    label: 'Associés',
    fields: [['members', 'Identité, coordonnées, titres et droits de chaque associé']]
  },
  {
    id: 'management',
    label: 'Administration',
    fields: [
      ['president', 'Président'],
      ['vice_president', 'Vice-président'],
      ['general_managers', 'Directeurs généraux'],
      ['deputy_general_managers', 'Directeurs généraux délégués'],
      ['manager_details', 'Infos générales DG / DGD']
    ]
  },
  {
    id: 'agreements',
    label: 'Conventions',
    fields: [['agreements', 'Conventions réglementées et autres conventions']]
  },
  {
    id: 'delegations',
    label: 'Délégation de pouvoirs',
    fields: [['delegations', 'Délégant, délégataire, pouvoirs et durée']]
  },
  {
    id: 'meetings',
    label: 'Assemblées du dossier',
    fields: [['meetings', 'Date, type, convocations, décisions et procès-verbaux']]
  },
  {
    id: 'control_bodies',
    label: 'Organes de contrôle',
    fields: [
      ['statutory_auditors', 'Commissaires aux comptes titulaires'],
      ['alternate_auditors', 'Commissaires aux comptes suppléants'],
      ['contribution_auditors', 'Commissaires aux apports'],
      ['accountants', 'Experts-comptables'],
      ['supervisory_board_president', 'Président du conseil de surveillance'],
      ['supervisory_board_vice_president', 'Vice-président du conseil de surveillance'],
      ['supervisory_board_members', 'Membres du conseil de surveillance'],
      ['supervisory_board_details', 'Informations sur le conseil de surveillance']
    ]
  },
  {
    id: 'assets',
    label: 'Patrimoine',
    fields: [
      ['goods', 'Biens'],
      ['establishments', 'Établissements secondaires'],
      ['subsidiaries', 'Filiales'],
      ['contracts', 'Contrats en cours'],
      ['leases', 'Baux'],
      ['patents', 'Brevets'],
      ['trademarks', 'Marques'],
      ['designs', 'Dessins et modèles'],
      ['works_council', 'Membres du CSE']
    ]
  },
  {
    id: 'billable_clients',
    label: 'Clients facturés / Tiers',
    fields: [['third_parties', 'Clients facturés et tiers']]
  },
  {
    id: 'tax',
    label: 'Fiscal',
    fields: [
      ['tax_regime', 'Régime fiscal'],
      ['tax_ids', 'Identifiants fiscaux'],
      ['tax_calendar', 'Échéances et obligations fiscales'],
      ['tax_notes', 'Autres informations fiscales']
    ]
  }
] as const

type CompanyProfile = Record<string, Record<string, string>>

export function LegalMattersSection({ data, write, submit }: LegalSectionProps) {
  const [clientName, setClientName] = useState('')
  const [email, setEmail] = useState('')
  const [address, setAddress] = useState('')
  const [customerType, setCustomerType] = useState('individual')
  const [siren, setSiren] = useState('')
  const [clientId, setClientId] = useState('')
  const [matterTitle, setMatterTitle] = useState('')
  const [matterType, setMatterType] = useState('')
  const [reference, setReference] = useState('')
  const [editingMatterId, setEditingMatterId] = useState('')
  const [companyProfile, setCompanyProfile] = useState<CompanyProfile>({})

  const editMatter = (matter: (typeof data.matters)[number]) => {
    setEditingMatterId(matter.id)
    setMatterTitle(matter.title)
    setClientId(matter.client_id)
    setMatterType(matter.matter_type)
    setReference(matter.reference)
    setCompanyProfile(matter.company_profile ?? {})
  }

  const updateCompanyField = (section: string, key: string, value: string) => {
    setCompanyProfile(current => ({ ...current, [section]: { ...current[section], [key]: value } }))
  }

  return (
    <>
      <div className="grid gap-6 md:grid-cols-2">
        <form
          className="space-y-3"
          onSubmit={submit(async () => {
            if (
              await write('legal.client.save', {
                name: clientName,
                email,
                address,
                customer_type: customerType as 'individual' | 'professional',
                siren
              })
            ) {
              setClientName('')
              setEmail('')
              setAddress('')
              setSiren('')
            }
          })}
        >
          <h3 className="font-semibold">Nouveau client</h3>
          <TextField label="Nom du client" onChange={setClientName} required value={clientName} />
          <TextField label="Email" onChange={setEmail} type="email" value={email} />
          <Choice
            items={[
              { id: 'individual', label: 'Particulier' },
              { id: 'professional', label: 'Professionnel' }
            ]}
            label="Type de client"
            onChange={setCustomerType}
            value={customerType}
          />
          {customerType === 'professional' && (
            <TextField label="SIREN du client professionnel" onChange={setSiren} value={siren} />
          )}
          <Field label="Adresse">
            <Textarea onChange={e => setAddress(e.target.value)} value={address} />
          </Field>
          <Button type="submit">Ajouter le client</Button>
        </form>
        <form
          className="space-y-3"
          onSubmit={submit(async () => {
            if (
              await write('legal.matter.save', {
                ...(editingMatterId ? { id: editingMatterId } : {}),
                title: matterTitle,
                client_id: clientId,
                matter_type: matterType,
                reference,
                ...(editingMatterId
                  ? { status: data.matters.find(item => item.id === editingMatterId)?.status ?? 'open' }
                  : {}),
                ...(data.domain === 'societes' ? { company_profile: companyProfile } : {})
              })
            ) {
              setEditingMatterId('')
              setMatterTitle('')
              setClientId('')
              setMatterType('')
              setReference('')
              setCompanyProfile({})
            }
          })}
        >
          <h3 className="font-semibold">{editingMatterId ? 'Modifier le dossier' : 'Nouveau dossier'}</h3>
          {!data.domain && <p>Configurez d’abord l’espace juridique.</p>}
          <Choice
            items={data.clients.map(item => ({ id: item.id, label: item.name }))}
            label="Client du dossier"
            onChange={setClientId}
            value={clientId}
          />
          <TextField label="Intitulé du dossier" onChange={setMatterTitle} required value={matterTitle} />
          <TextField label="Référence du dossier" onChange={setReference} value={reference} />
          <Choice
            items={data.matter_types.map(item => ({ id: item, label: item }))}
            label="Type de dossier"
            onChange={setMatterType}
            value={matterType}
          />
          {data.domain === 'societes' && (
            <section className="space-y-2 rounded-md border border-(--ui-stroke-secondary) p-3">
              <h4 className="font-medium">Fiche société</h4>
              <p className="text-sm text-(--ui-text-secondary)">
                Renseignez les informations connues. L’agent pourra les reprendre dans les brouillons du dossier et
                signalera les champs manquants.
              </p>
              {COMPANY_SECTIONS.map(section => (
                <details className="rounded border border-(--ui-stroke-secondary) p-2" key={section.id}>
                  <summary className="cursor-pointer font-medium">{section.label}</summary>
                  <div className="mt-3 space-y-3">
                    {section.fields.map(([key, label]) => (
                      <Field key={key} label={label}>
                        <Textarea
                          onChange={event => updateCompanyField(section.id, key, event.target.value)}
                          value={companyProfile[section.id]?.[key] ?? ''}
                        />
                      </Field>
                    ))}
                  </div>
                </details>
              ))}
            </section>
          )}
          <Button disabled={!clientId || !matterType} type="submit">
            {editingMatterId ? 'Enregistrer le dossier' : 'Créer le dossier'}
          </Button>
          {editingMatterId && (
            <Button
              onClick={() => {
                setEditingMatterId('')
                setMatterTitle('')
                setClientId('')
                setMatterType('')
                setReference('')
                setCompanyProfile({})
              }}
              type="button"
              variant="outline"
            >
              Annuler la modification
            </Button>
          )}
        </form>
      </div>
      <h3 className="font-semibold">Clients ({data.clients.length})</h3>
      <ul className="space-y-2">
        {data.clients.map(item => (
          <li className="break-words" key={item.id}>
            {item.name} — {item.email || 'Sans email'}
            <p className="whitespace-pre-wrap text-(--ui-text-secondary)">{item.address}</p>
          </li>
        ))}
      </ul>
      <h3 className="font-semibold">Dossiers ({data.matters.length})</h3>
      <ul className="space-y-2">
        {data.matters.map(item => (
          <li
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-(--ui-stroke-secondary) p-3"
            key={item.id}
          >
            <span className="min-w-0 break-words">
              {item.reference} {item.title} — {item.matter_type} —{' '}
              {data.clients.find(c => c.id === item.client_id)?.name} ({item.status === 'open' ? 'Ouvert' : 'Clos'})
            </span>
            <Button onClick={() => editMatter(item)} type="button" variant="outline">
              Modifier
            </Button>
            <Button
              onClick={() =>
                void write('legal.matter.save', { ...item, status: item.status === 'open' ? 'closed' : 'open' })
              }
              type="button"
              variant="outline"
            >
              {item.status === 'open' ? 'Clore' : 'Rouvrir'}
            </Button>
          </li>
        ))}
      </ul>
    </>
  )
}
