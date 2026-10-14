import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { downloadLegalText } from '@/store/legal-practice'

import { Field, type LegalSectionProps, TextField } from './fields'

export function LegalActsSection({ data, write, submit }: LegalSectionProps) {
  const [actId, setActId] = useState<string | undefined>()
  const [actTitle, setActTitle] = useState('')
  const [actType, setActType] = useState('')
  const [body, setBody] = useState('')
  const [search, setSearch] = useState('')
  const domainInfo = data.domains.find(item => item.id === data.domain)

  return (
    <>
      <p>
        Ajoutez vos modèles, modifiez leur texte et téléchargez-les. Les catégories suggérées sont des intitulés ; elles
        ne contiennent pas d’actes prévalidés.
      </p>
      <div className="flex flex-wrap gap-2">
        {domainInfo?.act_types.map(type => (
          <Button
            key={type}
            onClick={() => {
              setActId(undefined)
              setActType(type)
              setActTitle(type)
              setBody('')
            }}
            type="button"
            variant="outline"
          >
            {type}
          </Button>
        ))}
      </div>
      <form
        className="space-y-3"
        onSubmit={submit(async () => {
          if (await write('legal.act.save', { id: actId, title: actTitle, act_type: actType, body })) {
            setActId(undefined)
            setActTitle('')
            setActType('')
            setBody('')
          }
        })}
      >
        <div className="grid gap-3 md:grid-cols-2">
          <TextField label="Titre du modèle" onChange={setActTitle} required value={actTitle} />
          <TextField label="Catégorie d’acte" onChange={setActType} required value={actType} />
        </div>
        <Field label="Texte du modèle — variables possibles : {{client}}, {{dossier}}">
          <Textarea onChange={e => setBody(e.target.value)} rows={10} value={body} />
        </Field>
        <div className="flex flex-wrap gap-2">
          <Button type="submit">{actId ? 'Enregistrer le modèle' : 'Ajouter à la bibliothèque'}</Button>
          {actId && (
            <Button
              onClick={() => {
                setActId(undefined)
                setActTitle('')
                setActType('')
                setBody('')
              }}
              type="button"
              variant="outline"
            >
              Nouveau modèle
            </Button>
          )}
        </div>
      </form>
      <TextField label="Rechercher un acte" onChange={setSearch} value={search} />
      <ul className="space-y-2">
        {data.acts
          .filter(act => `${act.title} ${act.act_type}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
          .map(act => (
            <li
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-(--ui-stroke-secondary) p-3"
              key={act.id}
            >
              <span className="min-w-0 break-words">
                {act.title} — {act.act_type}
              </span>
              <div className="flex flex-wrap gap-2">
                <Button
                  onClick={() => {
                    setActId(act.id)
                    setActTitle(act.title)
                    setActType(act.act_type)
                    setBody(act.body)
                  }}
                  type="button"
                  variant="outline"
                >
                  Modifier
                </Button>
                <Button
                  onClick={() => downloadLegalText(`acte-${act.id}.md`, `# ${act.title}\n\n${act.body}`)}
                  type="button"
                  variant="outline"
                >
                  Télécharger
                </Button>
              </div>
            </li>
          ))}
      </ul>
    </>
  )
}
