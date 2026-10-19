import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

import { Choice, Field, type LegalSectionProps } from './fields'

export function LegalWorkspaceSection({ data, write, submit }: LegalSectionProps) {
  const [domain, setDomain] = useState('')
  const [types, setTypes] = useState('')
  const [saved, setSaved] = useState(false)
  const savedTypes = data.matter_types.join('\n')
  useEffect(() => {
    setDomain(data.domain ?? '')
    setTypes(savedTypes)
  }, [data.domain, savedTypes])

  return (
    <form
      className="space-y-4"
      onSubmit={submit(async () => {
        const ok = await write('legal.workspace.set', {
          domain,
          matter_types: types
            .split('\n')
            .map(value => value.trim())
            .filter(Boolean)
        })

        setSaved(ok)
      })}
    >
      <Choice
        items={data.domains.map(item => ({ id: item.id, label: item.label }))}
        label="Domaine juridique"
        onChange={async id => {
          setSaved(false)

          if (!id) {
            return
          }
          const nextTypes = data.domains.find(item => item.id === id)?.matter_types ?? []
          setDomain(id)
          setTypes(nextTypes.join('\n'))
          const ok = await write('legal.workspace.set', { domain: id, matter_types: nextTypes })
          setSaved(ok)

          if (!ok) {
            setDomain(data.domain ?? '')
            setTypes(savedTypes)
          }
        }}
        value={domain}
      />
      <Field label="Types de dossiers — un par ligne, personnalisables">
        <Textarea onChange={e => setTypes(e.target.value)} rows={7} value={types} />
      </Field>
      <p>Chaque projet peut devenir un espace spécialisé. Créez des projets séparés pour les différents domaines.</p>
      {domain !== data.domain && domain && <p role="status">Application des rubriques et catégories du domaine…</p>}
      {saved && (
        <p role="status">
          Domaine appliqué : les rubriques sont disponibles dans Clients et dossiers, et les catégories dans
          Bibliothèque d’actes.
        </p>
      )}
      {data.domain && (
        <section aria-label="Rubriques du domaine actif" className="space-y-2">
          <h3 className="font-semibold">{data.domains.find(item => item.id === data.domain)?.label}</h3>
          <ul className="grid gap-1 md:grid-cols-2">
            {data.matter_profile_schema.map(section => (
              <li key={section.id}>{section.label}</li>
            ))}
          </ul>
        </section>
      )}
      <Button disabled={!domain} type="submit">
        Enregistrer l’espace juridique
      </Button>
    </form>
  )
}
