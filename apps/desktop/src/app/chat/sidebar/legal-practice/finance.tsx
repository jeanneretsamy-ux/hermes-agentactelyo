import { useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { isLegalOwnerCurrent, type LegalPracticeOwner } from '@/store/legal-practice'
import FinanceCabinet from './finance-cabinet'

export function LegalFinanceSection({ owner }: { owner: LegalPracticeOwner }) {
  const pending = useRef<{ id: string; value: any; created: number } | null>(null)
  async function call(operation: string, input: Record<string, unknown> = {}) {
    if (!isLegalOwnerCurrent(owner)) throw Error('Le profil ou la connexion a changé. Rouvrez le cabinet.')
    if (input.project_id && input.project_id !== owner.projectId)
      throw Error('Espace financier différent du cabinet ouvert.')
    const params = { project_id: owner.projectId, profile: owner.profile }
    if (operation === 'snapshot' || operation === 'export')
      return owner.gateway.request('legal.finance.' + operation, params)
    if (operation === 'prepare') {
      const value: any = await owner.gateway.request('legal.finance.prepare', {
        ...params,
        action: input.action,
        payload: input.payload,
        request_id: crypto.randomUUID()
      })
      if (!isLegalOwnerCurrent(owner)) throw Error('La préparation appartient à une autre connexion.')
      const id = crypto.randomUUID()
      pending.current = { id, value, created: Date.now() }
      return { ...value, proposal_id: id }
    }
    const transfers = {file_start:'legal.finance.file.start',file_chunk:'legal.finance.file.chunk',file_finish:'legal.finance.file.finish',file_cancel:'legal.finance.file.cancel',file_read:'legal.finance.file.read',file_text:'legal.finance.file.text'} as const
    if(operation in transfers){
      const value = await owner.gateway.request(transfers[operation as keyof typeof transfers],{
        ...input,...params,...(operation==='file_start'?{request_id:crypto.randomUUID()}:{})
      } as any)
      if(!isLegalOwnerCurrent(owner))throw Error('Le document appartient à une autre connexion.')
      return value
    }
    const proposal = pending.current
    if (
      operation !== 'apply' ||
      input.approved !== true ||
      !proposal ||
      proposal.id !== input.proposal_id ||
      Date.now() - proposal.created > 600000
    )
      throw Error('Préparation absente ou expirée.')
    await owner.gateway.request('legal.' + proposal.value.action, { ...proposal.value.params, ...params })
    const readback = await owner.gateway.request('legal.finance.snapshot', params)
    return { applied: true, native_request_id: proposal.value.params.request_id, readback }
  }
  return <FinanceCabinet Button={Button} Input={Input} call={call} projectId={owner.projectId} />
}
