import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

import { Choice, Field, type LegalSectionProps, TextField } from './fields'

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
                title: matterTitle,
                client_id: clientId,
                matter_type: matterType,
                reference
              })
            ) {
              setMatterTitle('')
              setReference('')
            }
          })}
        >
          <h3 className="font-semibold">Nouveau dossier</h3>
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
          <Button disabled={!clientId || !matterType} type="submit">
            Créer le dossier
          </Button>
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
