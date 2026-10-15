import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

import { Choice, Field, type LegalSectionProps, TextField } from './fields'

type MatterProfile = Record<string, Record<string, string>>

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
  const [matterProfile, setMatterProfile] = useState<MatterProfile>({})

  const editMatter = (matter: (typeof data.matters)[number]) => {
    setEditingMatterId(matter.id)
    setMatterTitle(matter.title)
    setClientId(matter.client_id)
    setMatterType(matter.matter_type)
    setReference(matter.reference)
    setMatterProfile(matter.matter_profile ?? matter.company_profile ?? {})
  }

  const updateMatterField = (section: string, key: string, value: string) => {
    setMatterProfile(current => ({ ...current, [section]: { ...current[section], [key]: value } }))
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
                matter_profile: matterProfile
              })
            ) {
              setEditingMatterId('')
              setMatterTitle('')
              setClientId('')
              setMatterType('')
              setReference('')
              setMatterProfile({})
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
          {data.domain && (
            <section className="space-y-2 rounded-md border border-(--ui-stroke-secondary) p-3">
              <h4 className="font-medium">
                Fiche de dossier — {data.domains.find(domain => domain.id === data.domain)?.label}
              </h4>
              <p className="text-sm text-(--ui-text-secondary)">
                Saisissez les informations connues pour ce type de dossier. L’agent pourra les reprendre dans les
                brouillons et signalera les éléments manquants.
              </p>
              {data.matter_profile_schema.map(section => (
                <details className="rounded border border-(--ui-stroke-secondary) p-2" key={section.id}>
                  <summary className="cursor-pointer font-medium">{section.label}</summary>
                  <div className="mt-3 space-y-3">
                    {section.fields.map(({ id: key, label }) => (
                      <Field key={key} label={label}>
                        <Textarea
                          onChange={event => updateMatterField(section.id, key, event.target.value)}
                          value={matterProfile[section.id]?.[key] ?? ''}
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
                setMatterProfile({})
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
