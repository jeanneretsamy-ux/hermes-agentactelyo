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
  const [allocations, setAllocations] = useState<Record<string, string>>({})
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
  const [selectedFeeIds, setSelectedFeeIds] = useState<string[]>([])
  const [createKind, setCreateKind] = useState<'quote' | 'invoice'>('invoice')

  const [createPurpose, setCreatePurpose] = useState<'standard' | 'provision_fees' | 'provision_expenses_fees'>(
    'standard'
  )

  const [createStep, setCreateStep] = useState<'general' | 'items' | 'payment'>('general')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewDocId, setPreviewDocId] = useState('')
  const [creditOpen, setCreditOpen] = useState(false)
  const [creditTargetId, setCreditTargetId] = useState('')
  const [creditReason, setCreditReason] = useState('')
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
  const availableFees = fees.filter(fee => createKind === 'quote' || !fee.invoice_id)
  const selectedFees = availableFees.filter(fee => selectedFeeIds.includes(fee.id))
  const selectedTotal = selectedFees.reduce((sum, fee) => sum + fee.net_cents + fee.tax_cents, 0)

  const openDocumentWizard = (kind: 'quote' | 'invoice', purpose: typeof createPurpose = 'standard') => {
    setCreateKind(kind)
    setCreatePurpose(purpose)
    setCreateStep('general')
    setSelectedFeeIds(kind === 'quote' ? fees.map(fee => fee.id) : unbilled.map(fee => fee.id))
    setPreviewOpen(true)
  }

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
              kind: feeKind === 'time' ? 'time' : feeKind === 'expense' ? 'expense' : 'fixed',
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
              { id: 'time', label: 'Temps passé' },
              { id: 'expense', label: 'Frais de dossier' }
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
            label={
              feeKind === 'time'
                ? 'Tarif horaire HT (€)'
                : feeKind === 'expense'
                  ? 'Montant du frais (€)'
                  : 'Montant HT (€)'
            }
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
      <section className="space-y-3 rounded-lg border border-(--ui-stroke-secondary) p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold">Factures et devis</h3>
            <p className="text-sm text-(--ui-text-secondary)">Créer, prévisualiser et suivre les pièces du cabinet.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={!matterId || !fees.length}
              onClick={() => openDocumentWizard('quote')}
              type="button"
              variant="outline"
            >
              Nouveau devis
            </Button>
            <Button
              disabled={!matterId || !unbilled.length}
              onClick={() => openDocumentWizard('invoice')}
              type="button"
            >
              Nouvelle facture
            </Button>
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          {[
            ['Encaissé', invoices.reduce((sum, doc) => sum + doc.paid_cents, 0)],
            ['À encaisser', invoices.reduce((sum, doc) => sum + doc.balance_cents, 0)],
            [
              'En retard',
              invoices
                .filter(doc => doc.balance_cents > 0 && doc.due_on < today())
                .reduce((sum, doc) => sum + doc.balance_cents, 0)
            ]
          ].map(([label, cents]) => (
            <div className="rounded-md border border-(--ui-stroke-secondary) p-3" key={label}>
              <p className="text-sm text-(--ui-text-secondary)">{label}</p>
              <strong>{legalMoney(Number(cents))}</strong>
            </div>
          ))}
        </div>
      </section>
      <h3 className="font-semibold">Documents</h3>
      <Dialog onOpenChange={setPreviewOpen} open={previewOpen}>
        <DialogContent
          bodyClassName="min-w-0 overflow-auto"
          className="h-[min(54rem,calc(100vh-2rem))] w-[min(78rem,calc(100vw-2rem))] max-w-none overflow-hidden"
        >
          <DialogHeader>
            <DialogTitle>
              Création d’un{' '}
              {createKind === 'quote'
                ? 'devis'
                : createPurpose === 'provision_fees'
                  ? 'provision sur honoraires'
                  : createPurpose === 'provision_expenses_fees'
                    ? 'provision sur frais et honoraires'
                    : 'facture'}
            </DialogTitle>
            <DialogDescription>
              Le document reste un brouillon à vérifier. Choisissez le modèle puis contrôlez l’aperçu à droite.
            </DialogDescription>
          </DialogHeader>
          <div className="grid min-h-0 gap-4 lg:grid-cols-[minmax(19rem,0.85fr)_minmax(0,1.15fr)]">
            <section className="min-h-0 space-y-4 overflow-y-auto pr-1">
              <nav aria-label="Étapes de création" className="flex gap-2 border-b border-(--ui-stroke-secondary) pb-3">
                {(['general', 'items', 'payment'] as const).map((step, index) => (
                  <Button
                    key={step}
                    onClick={() => setCreateStep(step)}
                    type="button"
                    variant={createStep === step ? 'default' : 'outline'}
                  >
                    {index + 1}. {step === 'general' ? 'Général' : step === 'items' ? 'Prestations' : 'Paiement'}
                  </Button>
                ))}
              </nav>
              {createStep === 'general' && (
                <div className="space-y-3">
                  <Choice
                    items={[
                      { id: 'quote', label: 'Devis' },
                      { id: 'invoice', label: 'Facture' }
                    ]}
                    label="Type de pièce"
                    onChange={value => {
                      const kind = value as 'quote' | 'invoice'
                      setCreateKind(kind)
                      setSelectedFeeIds(kind === 'quote' ? fees.map(fee => fee.id) : unbilled.map(fee => fee.id))
                    }}
                    value={createKind}
                  />
                  {createKind === 'invoice' && (
                    <Choice
                      items={[
                        { id: 'standard', label: 'Facture d’honoraires' },
                        { id: 'provision_fees', label: 'Provision sur honoraires' },
                        { id: 'provision_expenses_fees', label: 'Provision sur frais et honoraires' }
                      ]}
                      label="Nature de la facture"
                      onChange={value => setCreatePurpose(value as typeof createPurpose)}
                      value={createPurpose}
                    />
                  )}
                  <Choice
                    items={matterChoices}
                    label="Dossier client"
                    onChange={value => {
                      setMatterId(value)

                      const matterFees = data.fees.filter(
                        fee => fee.matter_id === value && (createKind === 'quote' || !fee.invoice_id)
                      )

                      setSelectedFeeIds(matterFees.map(fee => fee.id))
                    }}
                    value={matterId}
                  />
                  <Choice
                    items={LEGAL_DOCUMENT_TEMPLATES.map(({ id, label }) => ({ id, label }))}
                    label="Modèle du document"
                    onChange={value => setTemplateId(value as typeof templateId)}
                    value={templateId}
                  />
                </div>
              )}
              {createStep === 'items' && (
                <div className="space-y-2">
                  <p className="text-sm text-(--ui-text-secondary)">
                    Sélectionnez les honoraires déjà saisis pour ce dossier. Les provisions ne sont pas imputées
                    automatiquement à une facture finale.
                  </p>
                  {availableFees.map(fee => (
                    <label
                      className="flex items-start gap-2 rounded-md border border-(--ui-stroke-secondary) p-3"
                      key={fee.id}
                    >
                      <input
                        checked={selectedFeeIds.includes(fee.id)}
                        onChange={event =>
                          setSelectedFeeIds(current =>
                            event.target.checked ? [...current, fee.id] : current.filter(id => id !== fee.id)
                          )
                        }
                        type="checkbox"
                      />
                      <span>
                        {fee.description}
                        <span className="block text-sm text-(--ui-text-secondary)">
                          {legalMoney(fee.net_cents + fee.tax_cents)} TTC · {fee.responsible_user || 'Non attribué'}
                        </span>
                      </span>
                    </label>
                  ))}
                  {!availableFees.length && (
                    <p>Aucune prestation disponible. Ajoutez des honoraires au dossier avant de continuer.</p>
                  )}
                </div>
              )}
              {createStep === 'payment' && (
                <div className="space-y-3">
                  <TextField label="Date d’échéance" onChange={setDueOn} type="date" value={dueOn} />
                  <p className="rounded-md bg-(--ui-bg-quaternary) p-3 text-sm">
                    Les coordonnées et conditions de paiement proviennent des réglages du cabinet. Vérifiez le régime de
                    TVA et les mentions avant validation.
                  </p>
                </div>
              )}
              <div className="flex flex-wrap justify-between gap-2 border-t border-(--ui-stroke-secondary) pt-3">
                <span className="font-semibold">Total TTC : {legalMoney(selectedTotal)}</span>
                {createStep !== 'payment' ? (
                  <Button onClick={() => setCreateStep(createStep === 'general' ? 'items' : 'payment')} type="button">
                    Suivant →
                  </Button>
                ) : (
                  <Button
                    disabled={!selectedFeeIds.length}
                    onClick={() =>
                      void write('legal.document.create', {
                        matter_id: matterId,
                        kind: createKind,
                        fee_ids: selectedFeeIds,
                        due_on: dueOn,
                        template_id: templateId,
                        purpose: createPurpose
                      }).then(ok => {
                        if (ok) {
                          setPreviewOpen(false)
                        }
                      })
                    }
                    type="button"
                  >
                    Créer le brouillon
                  </Button>
                )}
              </div>
            </section>
            <aside className="min-h-0 overflow-auto rounded-md bg-(--ui-bg-quaternary) p-3 sm:p-5">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="font-semibold">Aperçu du modèle</h3>
                <span className="text-sm text-(--ui-text-secondary)">
                  {LEGAL_DOCUMENT_TEMPLATES.find(template => template.id === templateId)?.label}
                </span>
              </div>
              <LegalDocumentPreview
                document={data.documents.find(doc => doc.id === previewDocId)}
                kind={
                  previewDocId
                    ? data.documents.find(doc => doc.id === previewDocId)?.kind === 'quote'
                      ? 'quote'
                      : 'invoice'
                    : createKind
                }
                templateId={templateId}
              />
            </aside>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog onOpenChange={setCreditOpen} open={creditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Créer un avoir d’annulation</DialogTitle>
            <DialogDescription>
              La facture reste conservée dans l’historique. L’avoir sera lié à cette pièce et ajustera le solde du
              brouillon.
            </DialogDescription>
          </DialogHeader>
          <TextField label="Motif de l’avoir" onChange={setCreditReason} required value={creditReason} />
          <Button
            disabled={!creditReason.trim()}
            onClick={() =>
              void write('legal.document.credit', { document_id: creditTargetId, reason: creditReason }).then(ok => {
                if (ok) {
                  setCreditOpen(false)
                  setCreditReason('')
                }
              })
            }
            type="button"
          >
            Créer l’avoir brouillon
          </Button>
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
              {doc.kind === 'invoice'
                ? ` — solde ${legalMoney(doc.balance_cents)}${doc.cancelled ? ' — annulée par avoir' : doc.credited_cents ? ` — avoirs ${legalMoney(doc.credited_cents)}` : ''}`
                : doc.kind === 'credit_note'
                  ? ` — annulation de ${doc.snapshot.credited_invoice_reference}`
                  : ''}
            </span>
            <Button
              onClick={() => {
                setPreviewDocId(doc.id)
                setCreateKind(doc.kind === 'quote' ? 'quote' : 'invoice')
                setCreatePurpose(doc.purpose as typeof createPurpose)
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
            {doc.kind === 'invoice' && !doc.cancelled && (
              <Button
                onClick={() => {
                  setCreditTargetId(doc.id)
                  setCreditReason('')
                  setCreditOpen(true)
                }}
                type="button"
                variant="outline"
              >
                Créer un avoir d’annulation
              </Button>
            )}
            {doc.kind === 'invoice' && doc.refund_due_cents > 0 && (
              <span className="text-sm text-(--ui-text-secondary)">
                Remboursement à suivre : {legalMoney(doc.refund_due_cents)}
              </span>
            )}
          </li>
        ))}
      </ul>
      <form
        className="space-y-3 rounded-lg border border-(--ui-stroke-secondary) p-4"
        onSubmit={submit(async () => {
          const parts = Object.entries(allocations).flatMap(([id, value]) => {
            if (!value.trim()) {
              return []
            }

            return [{ document_id: id, amount_cents: legalDecimal(value) }]
          })

          const amountCents = parts.reduce((sum, part) => sum + part.amount_cents, 0)

          if (
            parts.length &&
            amountCents > 0 &&
            (await write('legal.payment.allocate', {
              amount_cents: amountCents,
              allocations: parts,
              paid_on: paidOn,
              reference: paymentRef
            }))
          ) {
            setAllocations({})
            setPaymentRef('')
          }
        })}
      >
        <h3 className="font-semibold">Règlement reçu et lettrage</h3>
        <p className="text-sm text-(--ui-text-secondary)">
          Répartissez le même encaissement entre une ou plusieurs factures ouvertes. La somme affectée doit couvrir
          exactement le montant reçu.
        </p>
        <div className="space-y-2">
          {invoices
            .filter(doc => doc.balance_cents > 0)
            .map(doc => (
              <div
                className="grid items-center gap-2 rounded-md border border-(--ui-stroke-secondary) p-3 sm:grid-cols-[minmax(0,1fr)_12rem]"
                key={doc.id}
              >
                <span className="min-w-0">
                  {doc.reference} · {doc.snapshot.client.name}
                  <span className="block text-sm text-(--ui-text-secondary)">
                    Solde : {legalMoney(doc.balance_cents)}
                  </span>
                </span>
                <TextField
                  label="Affecter (€)"
                  onChange={value => setAllocations(current => ({ ...current, [doc.id]: value }))}
                  value={allocations[doc.id] ?? ''}
                />
              </div>
            ))}
          {!invoices.some(doc => doc.balance_cents > 0) && <p>Aucune facture ne reste à lettrer.</p>}
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <Field label="Total affecté">
            <output className="h-9 rounded-md border border-(--ui-stroke-secondary) px-2 py-2">
              {legalMoney(
                Object.values(allocations).reduce((sum, value) => {
                  try {
                    return sum + (value.trim() ? legalDecimal(value) : 0)
                  } catch {
                    return sum
                  }
                }, 0)
              )}
            </output>
          </Field>
          <TextField label="Date du règlement" onChange={setPaidOn} required type="date" value={paidOn} />
          <TextField label="Référence du règlement" onChange={setPaymentRef} required value={paymentRef} />
        </div>
        <Button disabled={!Object.values(allocations).some(value => value.trim())} type="submit">
          Enregistrer et lettrer le règlement
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

  const title =
    document?.kind === 'credit_note'
      ? `Avoir d’annulation de ${document.snapshot.credited_invoice_reference ?? 'facture'}`
      : document?.purpose === 'provision_fees'
        ? 'Facture de provision sur honoraires'
        : document?.purpose === 'provision_expenses_fees'
          ? 'Facture de provision sur frais et honoraires'
          : kind === 'quote'
            ? 'Devis'
            : 'Facture'

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
