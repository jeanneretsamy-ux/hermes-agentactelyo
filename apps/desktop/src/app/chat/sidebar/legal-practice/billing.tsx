import type { LegalDocument } from '@hermes/shared'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  downloadLegalText,
  LEGAL_DOCUMENT_TEMPLATES,
  legalDecimal,
  legalDocumentText,
  legalMoney
} from '@/store/legal-practice'

import { Choice, Field, type LegalSectionProps, TextField } from './fields'
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
  const [legalName, setLegalName] = useState(data.firm_settings.legal_name)
  const [firmAddress, setFirmAddress] = useState(data.firm_settings.address)
  const [siren, setSiren] = useState(data.firm_settings.siren)
  const [vatNumber, setVatNumber] = useState(data.firm_settings.vat_number)
  const [vatRegime, setVatRegime] = useState<'standard' | 'franchise'>(data.firm_settings.vat_regime)
  const [barName, setBarName] = useState(data.firm_settings.bar_name)
  const [paymentDelay, setPaymentDelay] = useState(String(data.firm_settings.payment_delay_days))
  const [latePenalty, setLatePenalty] = useState(data.firm_settings.late_penalty_rate)
  const [responsibleUser, setResponsibleUser] = useState('')
  const [templateId, setTemplateId] = useState<'classique' | 'synthese' | 'detaille'>('classique')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewDocId, setPreviewDocId] = useState('')
  const [previewKind, setPreviewKind] = useState<'quote' | 'invoice'>('quote')
  useEffect(() => {
    setLegalName(data.firm_settings.legal_name)
    setFirmAddress(data.firm_settings.address)
    setSiren(data.firm_settings.siren)
    setVatNumber(data.firm_settings.vat_number)
    setVatRegime(data.firm_settings.vat_regime)
    setBarName(data.firm_settings.bar_name)
    setPaymentDelay(String(data.firm_settings.payment_delay_days))
    setLatePenalty(data.firm_settings.late_penalty_rate)
  }, [data.firm_settings])

  const matterChoices = data.matters.map(item => ({
    id: item.id,
    label: `${item.reference ? `${item.reference} — ` : ''}${item.title}`
  }))

  const fees = data.fees.filter(fee => fee.matter_id === matterId)
  const unbilled = fees.filter(fee => !fee.invoice_id)
  const invoices = data.documents.filter(doc => doc.kind === 'invoice')

  return (
    <>
      <p>
        Gestion consolidée du cabinet, avec suivi par projet, dossier et utilisateur. Juridiction prise en charge :
        France.
      </p>
      <form
        className="space-y-3 rounded-md border border-(--ui-stroke-secondary) p-4"
        onSubmit={submit(async () => {
          await write('legal.firm.settings.set', {
            jurisdiction: 'FR',
            legal_name: legalName,
            address: firmAddress,
            siren,
            vat_number: vatNumber,
            vat_regime: vatRegime,
            bar_name: barName,
            payment_delay_days: Number(paymentDelay),
            late_penalty_rate: latePenalty
          })
        })}
      >
        <h3 className="font-semibold">Cabinet et juridiction</h3>
        <p>Complétez ces informations et vérifiez-les avant la création d’une facture.</p>
        <div className="grid gap-3 md:grid-cols-2">
          <TextField label="Nom juridique du cabinet" onChange={setLegalName} required value={legalName} />
          <TextField label="SIREN (9 chiffres)" onChange={setSiren} required value={siren} />
          <Field label="Adresse du cabinet">
            <textarea
              className="min-h-20 rounded-md border border-(--ui-stroke-secondary) bg-(--ui-chat-bubble-background) p-2"
              onChange={e => setFirmAddress(e.target.value)}
              required
              value={firmAddress}
            />
          </Field>
          <TextField label="N° TVA intracommunautaire (si applicable)" onChange={setVatNumber} value={vatNumber} />
          <Choice
            items={[
              { id: 'standard', label: 'Assujetti à la TVA' },
              { id: 'franchise', label: 'Franchise en base' }
            ]}
            label="Régime de TVA"
            onChange={value => setVatRegime(value as 'standard' | 'franchise')}
            value={vatRegime}
          />
          <TextField label="Barreau / ordre (facultatif)" onChange={setBarName} value={barName} />
          <TextField
            label="Délai de règlement (jours)"
            onChange={setPaymentDelay}
            required
            type="number"
            value={paymentDelay}
          />
          <TextField label="Pénalités de retard" onChange={setLatePenalty} required value={latePenalty} />
        </div>
        <Button type="submit">Enregistrer les paramètres du cabinet</Button>
      </form>
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          ['Honoraires du cabinet', data.firm_totals.fees_cents],
          ['Facturé', data.firm_totals.invoiced_cents],
          ['Solde du cabinet', data.firm_totals.balance_cents]
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
              tax_bps: legalDecimal(tax),
              responsible_user: responsibleUser
            })
          ) {
            setDescription('')
            setAmount('')
            setResponsibleUser('')
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
            label="Utilisateur responsable / collaborateur"
            onChange={setResponsibleUser}
            value={responsibleUser}
          />
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
      <div className="grid gap-4 md:grid-cols-2">
        <section>
          <h3 className="font-semibold">Répartition par utilisateur</h3>
          <ul>
            {data.firm_totals.by_user.map(row => (
              <li key={row.user}>
                {row.user} — {legalMoney(row.fees_cents)} HT ({row.fee_count})
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h3 className="font-semibold">Répartition par dossier</h3>
          <ul>
            {data.firm_totals.by_matter.map(row => (
              <li key={`${row.project_id}:${row.matter_id}`}>
                {row.project} · {row.title} — {legalMoney(row.fees_cents)} HT ({row.fee_count})
              </li>
            ))}
          </ul>
        </section>
      </div>
      <TextField label="Échéance du document" onChange={setDueOn} type="date" value={dueOn} />
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
        <Choice
          items={LEGAL_DOCUMENT_TEMPLATES.map(({ id, label }) => ({ id, label }))}
          label="Modèle de devis et facture"
          onChange={value => setTemplateId(value as typeof templateId)}
          value={templateId}
        />
        <Button
          onClick={() => {
            setPreviewDocId('')
            setPreviewKind('quote')
            setPreviewOpen(true)
          }}
          type="button"
          variant="outline"
        >
          Prévisualiser ce modèle
        </Button>
      </div>
      <p className="text-(--ui-text-tertiary)">
        Le modèle choisi est conservé sur le brouillon. Vous pourrez aussi comparer les présentations avant le
        téléchargement.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={!fees.length}
          onClick={() =>
            void write('legal.document.create', {
              matter_id: matterId,
              kind: 'quote',
              fee_ids: fees.map(fee => fee.id),
              due_on: dueOn,
              template_id: templateId
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
              due_on: dueOn,
              template_id: templateId
            })
          }
          type="button"
        >
          Créer la facture brouillon
        </Button>
      </div>
      <h3 className="font-semibold">Documents</h3>
      <Dialog onOpenChange={setPreviewOpen} open={previewOpen}>
        <DialogContent className="w-[min(58rem,calc(100vw-2rem))] max-w-none" bodyClassName="min-w-0">
          <DialogHeader>
            <DialogTitle>Prévisualisation du document</DialogTitle>
            <DialogDescription>
              Choisissez une présentation et relisez le brouillon avant de le télécharger ou de le transmettre.
            </DialogDescription>
          </DialogHeader>
          <Choice
            items={LEGAL_DOCUMENT_TEMPLATES.map(({ id, label }) => ({ id, label }))}
            label="Présentation"
            onChange={value => setTemplateId(value as typeof templateId)}
            value={templateId}
          />
          {!previewDocId && (
            <Choice
              items={[
                { id: 'quote', label: 'Devis' },
                { id: 'invoice', label: 'Facture' }
              ]}
              label="Type de document à prévisualiser"
              onChange={value => setPreviewKind(value as typeof previewKind)}
              value={previewKind}
            />
          )}
          <p className="text-(--ui-text-tertiary)">
            {LEGAL_DOCUMENT_TEMPLATES.find(template => template.id === templateId)?.description}
          </p>
          <LegalDocumentPreview
            document={data.documents.find(doc => doc.id === previewDocId)}
            templateId={templateId}
            kind={data.documents.find(doc => doc.id === previewDocId)?.kind ?? previewKind}
          />
          {data.documents.find(doc => doc.id === previewDocId) && (
            <Button
              onClick={() => {
                const doc = data.documents.find(item => item.id === previewDocId)
                if (doc) downloadLegalText(`${doc.reference}.md`, legalDocumentText(doc, templateId))
              }}
              type="button"
            >
              Télécharger cette présentation
            </Button>
          )}
        </DialogContent>
      </Dialog>
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
              onClick={() => {
                setPreviewDocId(doc.id)
                setPreviewKind(doc.kind)
                setTemplateId(doc.snapshot.template_id ?? 'classique')
                setPreviewOpen(true)
              }}
              type="button"
              variant="outline"
            >
              Prévisualiser
            </Button>
            <Button
              onClick={() =>
                downloadLegalText(
                  `${doc.reference}.md`,
                  legalDocumentText(doc, doc.snapshot.template_id ?? 'classique')
                )
              }
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

function LegalDocumentPreview({
  document,
  templateId,
  kind
}: {
  document?: LegalDocument
  templateId: 'classique' | 'synthese' | 'detaille'
  kind: 'quote' | 'invoice'
}) {
  const client = document?.snapshot.client
  const issuer = document?.snapshot.issuer
  const matter = document?.snapshot.matter
  const lines = document?.snapshot.lines ?? [
    { description: 'Prestation juridique — exemple', net_cents: 10000, tax_bps: 2000, tax_cents: 2000 }
  ]
  const title = kind === 'quote' ? 'Devis' : 'Facture'

  return (
    <article
      className={`mx-auto w-full max-w-3xl border border-(--ui-stroke-secondary) bg-background ${templateId === 'synthese' ? 'p-4 sm:p-6' : 'p-6 sm:p-10'}`}
      data-template={templateId}
    >
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-(--ui-stroke-secondary) pb-5">
        <div>
          <p className="text-xs uppercase tracking-widest text-(--ui-text-tertiary)">
            {issuer?.legal_name || 'Nom du cabinet'}
          </p>
          <h2 className="mt-2 text-2xl font-semibold">{title}</h2>
          <p className="mt-1 text-sm text-(--ui-text-secondary)">{document?.reference ?? 'Aperçu du modèle'}</p>
        </div>
        <div className="text-right text-sm">
          <p>{document?.created_on ?? new Date().toLocaleDateString('fr-FR')}</p>
          <p className="text-(--ui-text-secondary)">Échéance : {document?.due_on ?? 'à définir'}</p>
          <span className="mt-2 inline-block rounded-sm bg-(--ui-bg-quaternary) px-2 py-1 text-xs font-medium">
            BROUILLON
          </span>
          {templateId === 'synthese' && (
            <p className="mt-2 text-lg font-semibold">{legalMoney(document?.total_cents ?? 12000)} TTC</p>
          )}
        </div>
      </header>
      <div className="grid gap-5 py-5 sm:grid-cols-2">
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-(--ui-text-tertiary)">Cabinet</h3>
          <p className="mt-1 font-medium">{issuer?.legal_name || 'Nom du cabinet'}</p>
          <p className="whitespace-pre-wrap text-sm">{issuer?.address || 'Adresse du cabinet'}</p>
          {issuer?.siren && <p className="text-sm">SIREN {issuer.siren}</p>}
        </section>
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-(--ui-text-tertiary)">Client</h3>
          <p className="mt-1 font-medium">{client?.name || 'Nom du client'}</p>
          <p className="whitespace-pre-wrap text-sm">{client?.address || 'Adresse du client'}</p>
          {client?.email && <p className="text-sm">{client.email}</p>}
        </section>
      </div>
      <p className="mb-4 border-l-2 border-primary pl-3 text-sm">
        Dossier : {matter?.title ?? 'Intitulé du dossier'}
        {matter?.reference ? ` · ${matter.reference}` : ''}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] text-left text-sm">
          <thead className="border-b border-(--ui-stroke-secondary) text-(--ui-text-tertiary)">
            <tr>
              <th className="py-2 pr-3">Prestation</th>
              <th className="py-2 text-right">HT</th>
              {templateId === 'detaille' && <th className="py-2 text-right">Taux TVA</th>}
              <th className="py-2 text-right">TVA</th>
              <th className="py-2 text-right">TTC</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => (
              <tr className="border-b border-(--ui-stroke-secondary)" key={`${line.description}-${index}`}>
                <td className="py-3 pr-3">{line.description}</td>
                <td className="py-3 text-right">{legalMoney(line.net_cents)}</td>
                {templateId === 'detaille' && <td className="py-3 text-right">{line.tax_bps / 100} %</td>}
                <td className="py-3 text-right">{legalMoney(line.net_cents + line.tax_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="ml-auto mt-5 max-w-xs space-y-1 text-right text-sm">
        <p>Total HT : {legalMoney(document?.net_cents ?? 10000)}</p>
        <p>TVA : {legalMoney(document?.tax_cents ?? 2000)}</p>
        <p className="border-t border-(--ui-stroke-secondary) pt-2 text-lg font-semibold">
          Total TTC : {legalMoney(document?.total_cents ?? 12000)}
        </p>
      </div>
      <footer className="mt-8 border-t border-(--ui-stroke-secondary) pt-3 text-xs text-(--ui-text-tertiary)">
        {document?.snapshot.vat_notice || 'Document de travail interne, à relire et compléter avant émission.'}
      </footer>
    </article>
  )
}

