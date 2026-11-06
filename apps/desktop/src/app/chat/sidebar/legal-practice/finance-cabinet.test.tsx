import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import FinanceCabinet from './finance-cabinet'

afterEach(cleanup)

const metrics = {
  minutes: 0,
  billable_minutes: 0,
  unbilled_cents: 0,
  pending_cents: 0,
  cost_cents: 0,
  billed_net_cents: 0,
  cash_received_cents: 0,
  outstanding_cents: 0,
  missing_costs: 0,
  margin_cents: 0
}

const snapshot = (project_id = 'one') => ({
  project_id,
  as_of: '2026-11-04',
  totals: metrics,
  matters: [
    {
      ...metrics,
      id: 'matter',
      title: 'Dossier témoin',
      reference: 'DOS-1',
      client: 'Cliente',
      budget: null,
      time_over_budget: false,
      cost_over_budget: false
    }
  ],
  ageing: { not_due: 0 },
  receivables: [],
  pending_fees: [],
  ready_fees: [],
  scope: 'Registre de test'
})

const controlSnapshot = () => ({...snapshot(),operations:{parties:[],contracts:[],purchases:[],supplier_payments:[],timers:[],supplier_balance_cents:0,scope:'Interne',controls:{imports:[],objectives:[],forecasts:[],mileage:[],reminders:[]}}})

it('prepares a forecast in cents without recording it before confirmation',async()=>{
  const call=vi.fn(async(op:string,input?:Record<string,unknown>)=>op==='snapshot'?controlSnapshot():{proposal_id:'forecast',action:input!.action,params:input!.payload,description:'Prévision à confirmer'})
  render(<FinanceCabinet call={call} projectId="one"/>);
  fireEvent.click(screen.getByRole('button',{name:'Actualiser le registre réel'}));await screen.findByText('Registre de test');
  fireEvent.change(screen.getByLabelText('Entrées prévues (€)'),{target:{value:'199,99'}});
  fireEvent.change(screen.getByLabelText('Sorties prévues (€)'),{target:{value:'10,50'}});
  fireEvent.submit(screen.getByRole('button',{name:'Préparer la prévision'}).closest('form')!);
  await screen.findByRole('button',{name:'Confirmer l’enregistrement'});
  expect(call).toHaveBeenCalledWith('prepare',expect.objectContaining({action:'finance.forecast.save',payload:expect.objectContaining({incoming_cents:19999,outgoing_cents:1050})}));
  expect(call.mock.calls.some(([op])=>op==='apply')).toBe(false);
})

it('reports an invalid forecast amount without an unhandled error or financial request',async()=>{
  const call=vi.fn(async()=>controlSnapshot());render(<FinanceCabinet call={call} projectId="one"/>);
  fireEvent.click(screen.getByRole('button',{name:'Actualiser le registre réel'}));await screen.findByText('Registre de test');
  fireEvent.change(screen.getByLabelText('Entrées prévues (€)'),{target:{value:'999999999999999999'}});
  fireEvent.submit(screen.getByRole('button',{name:'Préparer la prévision'}).closest('form')!);
  expect((await screen.findByRole('alert')).textContent).toContain('Montant trop élevé');
  expect(call).toHaveBeenCalledTimes(1);
})

it('prepares a budget and writes only after the separate confirmation', async () => {
  const call = vi.fn(async (op: string, input?: Record<string, unknown>) => {
    if (op === 'snapshot') {return snapshot()}

    if (op === 'prepare')
      {return { proposal_id: 'proposal', action: input!.action, params: input!.payload, description: 'Préparation' }}

    return { applied: true, native_request_id: 'native-once', readback: snapshot() }
  })

  render(<FinanceCabinet call={call} projectId="one" />)
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser le registre réel' }))
  await screen.findByText('Registre de test')
  fireEvent.change(screen.getByLabelText('Dossier'), { target: { value: 'matter' } })
  fireEvent.click(screen.getByText('Budget et rentabilité de ce dossier'))
  fireEvent.change(screen.getByLabelText('Budget de temps (minutes)'), { target: { value: '120' } })
  fireEvent.change(screen.getByLabelText('Objectif de facturation HT (€)'), { target: { value: '199,99' } })
  fireEvent.click(screen.getByRole('button', { name: 'Préparer le budget' }))
  await screen.findByRole('button', { name: 'Confirmer l’enregistrement' })
  expect(call.mock.calls.some(([op]) => op === 'apply')).toBe(false)
  expect(call).toHaveBeenCalledWith(
    'prepare',
    expect.objectContaining({
      project_id: 'one',
      action: 'finance.budget.save',
      payload: expect.objectContaining({ budget_minutes: 120, revenue_cents: 19999, expected_version: 0 })
    })
  )
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer l’enregistrement' }))
  await screen.findByText(/Écriture enregistrée et registre relu/)
  expect(call).toHaveBeenCalledWith('apply', { proposal_id: 'proposal', approved: true })
})

it('ignores a late snapshot from a previous project and permits refreshing the new project', async () => {
  let resolveFirst!: (value: unknown) => void

  const first = new Promise(resolve => {
    resolveFirst = resolve
  })

  const call = vi.fn((op: string, input?: Record<string, unknown>) =>
    input?.project_id === 'one' ? first : Promise.resolve(snapshot('two'))
  )

  const view = render(<FinanceCabinet call={call} projectId="one" />)
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser le registre réel' }))
  view.rerender(<FinanceCabinet call={call} projectId="two" />)
  await waitFor(() =>
    expect((screen.getByRole('button', { name: 'Actualiser le registre réel' }) as HTMLButtonElement).disabled).toBe(false)
  )
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser le registre réel' }))
  await screen.findByText('Registre de test')
  resolveFirst({ ...snapshot(), scope: 'Ancien espace à ignorer' })
  await waitFor(() => expect(call).toHaveBeenCalledWith('snapshot', { project_id: 'two' }))
  expect(screen.queryByText('Ancien espace à ignorer')).toBeNull()
})
