import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

import { Choice, Field, type LegalSectionProps } from './fields'

export function LegalWorkspaceSection({ data, write, submit }: LegalSectionProps) {
  const [domain, setDomain] = useState('')
  const [types, setTypes] = useState('')
  const savedTypes = data.matter_types.join('\n')
  useEffect(() => {
    setDomain(data.domain ?? '')
    setTypes(savedTypes)
  }, [data.domain, savedTypes])

  return (
    <form
      className="space-y-4"
      onSubmit={submit(async () => {
        await write('legal.workspace.set', {
          domain,
          matter_types: types
            .split('\n')
            .map(value => value.trim())
            .filter(Boolean)
        })
      })}
    >
      <Choice
        items={data.domains.map(item => ({ id: item.id, label: item.label }))}
        label="Domaine juridique"
        onChange={id => {
          setDomain(id)
          setTypes(data.domains.find(item => item.id === id)?.matter_types.join('\n') ?? '')
        }}
        value={domain}
      />
      <Field label="Types de dossiers — un par ligne, personnalisables">
        <Textarea onChange={e => setTypes(e.target.value)} rows={7} value={types} />
      </Field>
      <p>Chaque projet peut devenir un espace spécialisé. Créez des projets séparés pour les différents domaines.</p>
      <Button disabled={!domain} type="submit">
        Enregistrer l’espace juridique
      </Button>
    </form>
  )
}
