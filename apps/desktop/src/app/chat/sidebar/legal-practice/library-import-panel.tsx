import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'

import type { LegalSectionProps } from './fields'
import { parsePrivateLibrary, type PrivateLibraryEntry } from './library-import'

export function LegalLibraryImport({ data, write }: Pick<LegalSectionProps, 'data' | 'write'>) {
  const [entries, setEntries] = useState<PrivateLibraryEntry[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const alive = useRef(true)
  const reading = useRef(0)
  // eslint-disable-next-line no-restricted-syntax -- Mount lifecycle guard; no reactive value is mirrored.
  useEffect(() => {
    alive.current = true

    return () => {
      alive.current = false
    }
  }, [])
  const matching = entries.map((entry, index) => ({ entry, index })).filter(({ entry }) => entry.domain === data.domain)

  async function load(file?: File) {
    const generation = ++reading.current
    setEntries([])
    setSelected(new Set())
    setMessage('')

    if (!file) { return }

    try {
      if (file.size > 8_000_000) { throw new Error('Fichier trop volumineux (8 Mo maximum).') }
      const parsed = parsePrivateLibrary(await file.text(), data.domains.map(domain => domain.id))

      if (!alive.current || generation !== reading.current) { return }
      setEntries(parsed)
      setSelected(new Set(parsed.map((_, index) => index)))
    } catch (error) {
      if (alive.current && generation === reading.current) {
        setMessage(error instanceof Error ? error.message : String(error))
      }
    }
  }

  async function save() {
    if (busy || !data.domain) { return }

    const chosen = matching.filter(({ index }) => selected.has(index))
      .map(({ entry: { title, act_type, body } }) => ({ title, act_type, body }))

    if (!chosen.length) { return }
    setBusy(true)

    try {
      const ok = await write('legal.library.import', { domain: data.domain, entries: chosen })

      if (alive.current) {
        setMessage(ok ? 'Import enregistré. Les entrées déjà importées sont conservées sans doublon ni écrasement.' : 'Import non confirmé. Vous pouvez réessayer sans dupliquer les mêmes entrées.')

        if (ok) { setEntries([]) }
      }
    } finally {
      if (alive.current) { setBusy(false) }
    }
  }

  return <section className="space-y-3 rounded border p-3">
    <h3 className="font-semibold">Importer une bibliothèque privée</h3>
    <p>Choisissez le fichier bibliotheque-actelyo.json. Seuls les actes du domaine de cet espace seront enregistrés dans le profil connecté.</p>
    <input accept=".json,application/json" aria-label="Fichier de bibliothèque privée" disabled={busy || !data.domain}
      onChange={event => void load(event.target.files?.[0])} type="file" />
    {entries.length > 0 && <>
      <p>{matching.length} actes proposés pour ce domaine sur {entries.length}. Vérifiez le classement et la sélection.</p>
      <p>Les textes peuvent contenir des identités et faits préremplis. Les balises sont conservées ; la fusion Word et les macros ne sont pas exécutées.</p>
      <div className="max-h-60 overflow-auto">
        {matching.map(({ entry, index }) => <label className="flex gap-2 py-1" key={index}>
          <input checked={selected.has(index)} disabled={busy} onChange={event => setSelected(previous => {
            const next = new Set(previous)

            if (event.target.checked) { next.add(index) } else { next.delete(index) }

            return next
          })} type="checkbox" />
          {entry.title}
        </label>)}
      </div>
      <Button disabled={busy || !matching.some(({ index }) => selected.has(index))} onClick={() => void save()} type="button">
        Importer les actes sélectionnés
      </Button>
    </>}
    {message && <p role="status">{message}</p>}
  </section>
}
