import type { LegalSnapshot } from '@hermes/shared'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { LegalWorkspaceSection } from './workspace'

afterEach(cleanup)

const data = {
  domain: 'societes',
  matter_types: ['Constitution'],
  domains: [
    { id: 'societes', label: 'Droit des sociétés', matter_types: ['Constitution'] },
    { id: 'social', label: 'Droit social', matter_types: ['Contrat de travail'] }
  ],
  matter_profile_schema: [{ id: 'company', label: 'Société', fields: [] }]
} as unknown as LegalSnapshot

it('applies a domain selection through the backend without an extra save click', async () => {
  const write = vi.fn().mockResolvedValue(true)
  render(<LegalWorkspaceSection data={data} submit={() => () => {}} write={write} />)
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'social' } })
  await waitFor(() =>
    expect(write).toHaveBeenCalledWith('legal.workspace.set', {
      domain: 'social',
      matter_types: ['Contrat de travail']
    })
  )
})

it('restores the persisted selection when the backend rejects the change', async () => {
  render(<LegalWorkspaceSection data={data} submit={() => () => {}} write={vi.fn().mockResolvedValue(false)} />)
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'social' } })
  await waitFor(() => expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('societes'))
})
