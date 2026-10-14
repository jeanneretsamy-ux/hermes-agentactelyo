import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { downloadLegalText, legalDecimal, legalDocumentText, legalMoney } from '@/store/legal-practice'

import { Choice, type LegalSectionProps, TextField } from './fields'
const today = () => new Date().toISOString().slice(0, 10)

export function LegalBillingSection({ data, write, submit }: LegalSectionProps) {
  const [matterId, setMatterId] = useState('')
  const [description, setDescription] = useState('')
  const [feeKind, setFeeKind] = useState('fixed')
  const [amount, setAmount] = useState('')
  const [minutes, setMinutes] = useState('60')
  const [tax, setTax] = useState('0')
  const [dueOn, setDueOn] = useState(today)
  const [paidOn, setPaidOn] = useState(today)
  const [documentId, setDocumentId] = useState('')
  const [paymentAmount, setPaymentAmount] = useState('')
  const [paymentRef, setPaymentRef] = useState('')

  const matterChoices = data.matters.map(item => ({
    id: item.id,
    label: `${item.reference ? `${item.reference} — ` : ''}${item.title}`
  }))

  const fees = data.fees.filter(fee => fee.matter_id === matterId)
  const unbilled = fees.filter(fee => !fee.invoice_id)
  const invoices = data.documents.filter(doc => doc.kind === 'invoice')
  const total = invoices.reduce((sum, doc) => sum + doc.total_cents, 0)
  const paid = invoices.reduce((sum, doc) => sum + doc.paid_cents, 0)

  return (
    <>
      <p>Devis et factures de travail en EUR, à compléter avant émission. Les règlements sont saisis manuellement.</p>
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          ['Total des factures de travail', total],
          ['Règlements saisis', paid],
          ['Solde', total - paid]
        ].map(([label, value]) => (
          <div className="rounded-md border border-(--ui-stroke-secondary) p-3" key={label}>
            <p>{label}</p>
            <strong>{legalMoney(Number(value))}</strong>
          </div>
        ))}
      </div>
      <Choice items={matterChoices} label="Dossier à facturer" onChange={setMatterId} value={matterId} />
      <form
        className="space-y-3"
        onSubmit={submit(async () => {
          if (
            await write('legal.fee.add', {
              matter_id: matterId,
              description,
              kind: feeKind === 'time' ? 'time' : 'fixed',
              ...(feeKind === 'time'
                ? { minutes: Number(minutes), rate_cents: legalDecimal(amount) }
                : { amount_cents: legalDecimal(amount) }),
              tax_bps: legalDecimal(tax)
            })
          ) {
            setDescription('')
            setAmount('')
          }
        })}
      >
        <h3 className="font-semibold">Honoraires et temps</h3>
        <div className="grid gap-3 md:grid-cols-2">
          <Choice
            items={[
              { id: 'fixed', label: 'Forfait' },
              { id: 'time', label: 'Temps passé' }
            ]}
            label="Mode de facturation"
            onChange={setFeeKind}
            value={feeKind}
          />
          <TextField label="Prestation" onChange={setDescription} required value={description} />
          <TextField
            label={feeKind === 'time' ? 'Tarif horaire HT (€)' : 'Montant HT (€)'}
            onChange={setAmount}
            required
            value={amount}
          />
          {feeKind === 'time' && (
            <TextField label="Durée (minutes)" onChange={setMinutes} required type="number" value={minutes} />
          )}
          <TextField label="TVA (%) — à renseigner selon votre situation" onChange={setTax} required value={tax} />
        </div>
        <Button disabled={!matterId} type="submit">
          Ajouter les honoraires
        </Button>
      </form>
      <ul className="space-y-2">
        {fees.map(fee => (
          <li className="break-words" key={fee.id}>
            {fee.description} — {legalMoney(fee.net_cents)} HT{fee.kind === 'time' ? ` — ${fee.minutes} min` : ''} —{' '}
            {fee.invoice_id ? 'Inclus dans une facture' : 'À facturer'}
          </li>
        ))}
      </ul>
      <TextField label="Échéance du document" onChange={setDueOn} type="date" value={dueOn} />
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={!fees.length}
          onClick={() =>
            void write('legal.document.create', {
              matter_id: matterId,
              kind: 'quote',
              fee_ids: fees.map(fee => fee.id),
              due_on: dueOn
            })
          }
          type="button"
          variant="outline"
        >
          Créer le devis brouillon
        </Button>
        <Button
          disabled={!unbilled.length}
          onClick={() =>
            void write('legal.document.create', {
              matter_id: matterId,
              kind: 'invoice',
              fee_ids: unbilled.map(fee => fee.id),
              due_on: dueOn
            })
          }
          type="button"
        >
          Créer la facture brouillon
        </Button>
      </div>
      <h3 className="font-semibold">Documents</h3>
      <ul className="space-y-2">
        {data.documents.map(doc => (
          <li
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-(--ui-stroke-secondary) p-3"
            key={doc.id}
          >
            <span className="min-w-0 break-words">
              {doc.reference} — {doc.snapshot.client.name} — {legalMoney(doc.total_cents)} TTC
              {doc.kind === 'invoice' ? ` — solde ${legalMoney(doc.balance_cents)}` : ''}
            </span>
            <Button
              onClick={() => downloadLegalText(`${doc.reference}.md`, legalDocumentText(doc))}
              type="button"
              variant="outline"
            >
              Télécharger le brouillon
            </Button>
          </li>
        ))}
      </ul>
      <form
        className="space-y-3"
        onSubmit={submit(async () => {
          if (
            await write('legal.payment.add', {
              document_id: documentId,
              amount_cents: legalDecimal(paymentAmount),
              paid_on: paidOn,
              reference: paymentRef
            })
          ) {
            setPaymentAmount('')
            setPaymentRef('')
          }
        })}
      >
        <h3 className="font-semibold">Règlement reçu</h3>
        <Choice
          items={invoices
            .filter(doc => doc.balance_cents > 0)
            .map(doc => ({ id: doc.id, label: `${doc.reference} — ${doc.snapshot.client.name}` }))}
          label="Facture du règlement"
          onChange={setDocumentId}
          value={documentId}
        />
        <div className="grid gap-3 md:grid-cols-3">
          <TextField label="Montant reçu (€)" onChange={setPaymentAmount} required value={paymentAmount} />
          <TextField label="Date du règlement" onChange={setPaidOn} required type="date" value={paidOn} />
          <TextField label="Référence du règlement" onChange={setPaymentRef} required value={paymentRef} />
        </div>
        <Button disabled={!documentId} type="submit">
          Enregistrer le règlement
        </Button>
      </form>
      <ul className="space-y-1">
        {data.payments.map(payment => (
          <li className="break-words" key={payment.id}>
            {payment.paid_on} — {payment.reference} — {legalMoney(payment.amount_cents)} —{' '}
            {data.documents.find(doc => doc.id === payment.document_id)?.reference}
          </li>
        ))}
      </ul>
    </>
  )
}
