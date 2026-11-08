import { type ButtonHTMLAttributes, type ComponentType, type InputHTMLAttributes, useState } from 'react'
export type BillingOrder = {
  id: string
  matter_id: string
  reference: string
  purpose: string
  status: string
  version: number
  net_cents: number
  tax_cents: number
  total_cents: number
  document_id: string | null
  lines: {
    id: string
    description: string
    net_cents: number
    tax_cents: number
  }[]
}
type Props = {
  orders: BillingOrder[]
  fees: {
    id: string
    matter_id: string
    description: string
    net_cents: number
  }[]
  matterId: string
  onEdit: () => void
  prepare: (action: string, payload: Record<string, unknown>) => Promise<void>
  Button: ComponentType<ButtonHTMLAttributes<HTMLButtonElement>>
  Input: ComponentType<InputHTMLAttributes<HTMLInputElement>>
}

const euros = (value: number) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(value / 100)

const today = () => {
  const d = new Date()

  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function BillingOrders({ orders, fees, matterId, onEdit, prepare, Button, Input }: Props) {
  const [selected, setSelected] = useState<string[]>([]),
    [purpose, setPurpose] = useState('standard'),
    [due, setDue] = useState(today)

  const available = fees.filter(f => f.matter_id === matterId)
  const chosen = selected.filter(id => available.some(f => f.id === id))

  const reserved = new Set(orders.filter(o => o.status === 'ready').flatMap(o => o.lines.map(l => l.id)))

  return (
    <details>
      <summary>Bons à facturer numérotés</summary>
      <p>
        Un bon réserve les lignes approuvées et fige leurs montants. La conversion crée une facture interne après
        vérification des lignes ; l’émission fiscale reste une étape distincte.
      </p>
      {available.map(f => (
        <label key={f.id}>
          <input
            checked={chosen.includes(f.id)}
            disabled={reserved.has(f.id)}
            onChange={e => {
              onEdit()
              setSelected(e.target.checked ? [...chosen, f.id] : chosen.filter(id => id !== f.id))
            }}
            type="checkbox"
          />
          {f.description} · {euros(f.net_cents)} HT {reserved.has(f.id) ? '· déjà réservée' : ''}
        </label>
      ))}
      <label>
        Nature du bon
        <select
          aria-label="Nature du bon"
          onChange={e => {
            onEdit()
            setPurpose(e.target.value)
          }}
          value={purpose}
        >
          <option value="standard">Standard</option>
          <option value="provision_fees">Provision sur honoraires</option>
          <option value="provision_expenses">Provision sur frais</option>
          <option value="provision_expenses_fees">Provision sur frais et honoraires</option>
        </select>
      </label>
      <Button
        disabled={!matterId || !chosen.length || chosen.some(id => reserved.has(id))}
        onClick={() =>
          void prepare('finance.billing_order.create', {
            matter_id: matterId,
            fee_ids: chosen,
            purpose
          })
        }
        type="button"
      >
        Préparer le bon à facturer
      </Button>
      <label>
        Échéance de la facture issue du bon
        <Input
          onChange={e => {
            onEdit()
            setDue(e.target.value)
          }}
          required
          type="date"
          value={due}
        />
      </label>
      {orders
        .filter(o => o.matter_id === matterId)
        .map(o => (
          <article aria-label={o.reference} key={o.id}>
            <h4>{o.reference}</h4>
            <p>
              {(
                {
                  ready: 'À facturer',
                  invoiced: 'Converti en facture interne',
                  cancelled: 'Annulé'
                } as Record<string, string>
              )[o.status] || o.status}{' '}
              · HT {euros(o.net_cents)} · TVA {euros(o.tax_cents)} · TTC {euros(o.total_cents)}
            </p>
            <ul>
              {o.lines.map(l => (
                <li key={l.id}>
                  {l.description} · {euros(l.net_cents)} HT
                </li>
              ))}
            </ul>
            {o.document_id && <p>Facture liée : {o.document_id}</p>}
            {o.status === 'ready' && (
              <>
                <Button
                  disabled={!due}
                  onClick={() =>
                    void prepare('finance.billing_order.invoice', {
                      billing_order_id: o.id,
                      expected_version: o.version,
                      due_on: due,
                      template_id: 'classique'
                    })
                  }
                  type="button"
                >
                  Préparer la facture de ce bon
                </Button>
                <Button
                  onClick={() =>
                    void prepare('finance.billing_order.cancel', {
                      billing_order_id: o.id,
                      expected_version: o.version
                    })
                  }
                  type="button"
                >
                  Préparer l’annulation du bon
                </Button>
              </>
            )}
          </article>
        ))}
    </details>
  )
}
