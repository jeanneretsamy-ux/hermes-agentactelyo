import { useRef, useState } from 'react'

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
  const [dropMessage, setDropMessage] = useState('')
  const [draggingExample, setDraggingExample] = useState(false)
  const bodyRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const domainInfo = data.domains.find(item => item.id === data.domain)

  async function insertExample(file: File, selectionStart?: number, selectionEnd?: number) {
    const extension = file.name.split('.').pop()?.toLowerCase()

    if (!['txt', 'md'].includes(extension ?? '') || file.size > 1_000_000) {
      setDropMessage(
        'Importez un exemple texte .txt ou .md de moins de 1 Mo. Les PDF/Word restent à joindre au chat ou à lire depuis le dossier du projet.'
      )

      return
    }

    const text = await file.text()

    if (!text.trim()) {
      setDropMessage('Ce fichier ne contient pas de texte exploitable.')

      return
    }

    const start = selectionStart ?? body.length
    const end = selectionEnd ?? start
    setBody(current => `${current.slice(0, start)}${text}${current.slice(end)}`)
    setDropMessage(
      `Exemple « ${file.name} » inséré dans le modèle. Enregistrez-le pour que l’agent puisse s’y référer.`
    )
    requestAnimationFrame(() => {
      bodyRef.current?.focus()
      bodyRef.current?.setSelectionRange(start + text.length, start + text.length)
    })
  }

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
          <Textarea
            className={draggingExample ? 'border-primary bg-primary/5' : undefined}
            onChange={e => setBody(e.target.value)}
            onDragEnter={event => {
              event.preventDefault()
              setDraggingExample(true)
            }}
            onDragLeave={() => setDraggingExample(false)}
            onDragOver={event => event.preventDefault()}
            onDrop={event => {
              event.preventDefault()
              setDraggingExample(false)
              const file = event.dataTransfer.files[0]

              if (file) {void insertExample(file, event.currentTarget.selectionStart, event.currentTarget.selectionEnd)}
            }}
            ref={bodyRef}
            rows={10}
            value={body}
          />
        </Field>
        <div className="flex flex-wrap items-center gap-2">
          <input
            accept=".txt,.md,text/plain,text/markdown"
            className="sr-only"
            onChange={event => {
              const file = event.currentTarget.files?.[0]

              if (file) {void insertExample(file)}
              event.currentTarget.value = ''
            }}
            ref={fileRef}
            type="file"
          />
          <Button onClick={() => fileRef.current?.click()} type="button" variant="outline">
            Importer un exemple texte
          </Button>
          <span className="text-(--ui-text-tertiary)">
            ou déposez un fichier .txt/.md dans le texte pour l’insérer au curseur.
          </span>
        </div>
        {dropMessage && <p role="status">{dropMessage}</p>}
        <details className="space-y-2">
          <summary className="cursor-pointer">Prévisualiser le modèle</summary>
          <article className="max-h-80 overflow-auto rounded-md bg-(--ui-bg-quaternary) p-4">
            <h3 className="mb-3 text-center text-base font-semibold">{actTitle || 'Titre de l’acte'}</h3>
            <pre className="whitespace-pre-wrap break-words font-sans text-sm">
              {body || 'Le texte de votre modèle apparaîtra ici.'}
            </pre>
          </article>
        </details>
        <p className="text-(--ui-text-tertiary)">
          Dans le chat, vous pouvez demander : « Reprends le modèle {actTitle || 'X'}, densifie uniquement la partie Y à
          partir des faits du dossier et de l’exemple enregistré. » L’agent doit signaler les éléments manquants et vous
          laisser relire l’acte.
        </p>
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

