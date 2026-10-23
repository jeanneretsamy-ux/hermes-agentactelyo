import type { LegalSnapshot } from '@hermes/shared'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { parsePrivateLibrary } from './library-import'
import { LegalLibraryImport } from './library-import-panel'

vi.mock('@/components/ui/button', () => ({ Button: (props: React.ComponentProps<'button'>) => <button {...props} /> }))
afterEach(cleanup)

const entry = {
  title: 'Statuts test',
  act_type: 'Statuts',
  domain: 'societes',
  body: 'ARTICLE 1 — [*Société]\nARTICLE 2 — [*Objet]',
  sources: [{ archive: 'exemple.zip', member: 'statuts.docm', sha256: 'a'.repeat(64) }]
}

const pack = (entries: unknown[]) => JSON.stringify({ format: 'actelyo-private-library-v1', entries })

it('preserves every marker and makes source facts explicitly non-transferable', () => {
  const result = parsePrivateLibrary(pack([entry]), ['societes'])[0]
  expect(result.body).toContain(entry.body)
  expect(result.body).toContain('NON ANONYMISÉE')
  expect(result.body).toContain('SHA-256 original : ' + 'a'.repeat(64))
  expect(() => parsePrivateLibrary(pack([{ ...entry, domain: 'unknown' }]), ['societes'])).toThrow()
  expect(() => parsePrivateLibrary(pack([{ ...entry, sources: [] }]), ['societes'])).toThrow()
})

it('previews privately, then imports only the selected domain after explicit click', async () => {
  const write = vi.fn().mockResolvedValue(true)
  const data = { domain: 'societes', domains: [{ id: 'societes' }, { id: 'social' }] } as LegalSnapshot
  render(<LegalLibraryImport data={data} write={write} />)
  const file = new File([''], 'bibliotheque-actelyo.json')
  Object.defineProperty(file, 'text', {
    value: async () => pack([entry, { ...entry, title: 'Contrat travail', domain: 'social' }])
  })
  fireEvent.change(screen.getByLabelText('Fichier de bibliothèque privée'), { target: { files: [file] } })
  await screen.findByText('Statuts test')
  expect(screen.queryByText('Contrat travail')).toBeNull()
  expect(write).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Importer les actes sélectionnés' }))
  await waitFor(() => expect(write).toHaveBeenCalledOnce())
  expect(write.mock.calls[0][0]).toBe('legal.library.import')
  expect(write.mock.calls[0][1]).toMatchObject({
    domain: 'societes',
    entries: [{ title: entry.title, act_type: entry.act_type }]
  })
  expect(write.mock.calls[0][1].entries).toHaveLength(1)
  await screen.findByText(/Import enregistré/)
})
