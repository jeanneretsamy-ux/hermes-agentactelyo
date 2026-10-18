import type { LegalSnapshot } from '@hermes/shared'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { LegalTasksSection } from './tasks'

vi.mock('@/components/ui/button', () => ({ Button: (props: React.ComponentProps<'button'>) => <button {...props} /> }))
afterEach(cleanup)
it('edits a dated step without losing its matter, reminder or notes', async () => {
  const write = vi.fn().mockResolvedValue(true)
  const task = {
    id: 'step',
    matter_id: 'matter',
    title: 'Dépôt',
    due_on: '2026-10-01',
    remind_on: '2026-09-30',
    notes: 'Date vérifiée',
    responsible_user: 'Responsable',
    status: 'pending',
    alert: 'overdue'
  }
  const data = { matters: [{ id: 'matter', title: 'Société' }], tasks: [task] } as LegalSnapshot
  render(
    <LegalTasksSection
      data={data}
      submit={action => event => {
        event.preventDefault()
        void action()
      }}
      write={write}
    />
  )
  expect(screen.getByText('Échéance dépassée')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Modifier' }))
  fireEvent.change(screen.getByLabelText('État de l’étape'), { target: { value: 'done' } })
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer l’étape' }))
  await waitFor(() =>
    expect(write).toHaveBeenCalledWith('legal.task.save', {
      id: 'step',
      matter_id: 'matter',
      title: 'Dépôt',
      due_on: task.due_on,
      remind_on: task.remind_on,
      notes: task.notes,
      responsible_user: task.responsible_user,
      task_status: 'done'
    })
  )
})
