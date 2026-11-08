import { type ButtonHTMLAttributes, type ComponentType, type InputHTMLAttributes, useState } from 'react'

export type ControlData = {
  imports: {
    id: string
    filename: string
    row_count: number
    debit_cents: number
    credit_cents: number
    revenue_cents: number
    expense_cents: number
    matched_references: string[]
    unmatched_references: string[]
  }[]
  objectives: {
    id: string
    responsible_user: string
    role: string
    start_on: string
    end_on: string
    revenue_cents: number
    margin_cents: number
    minutes: number
    version: number
    actual_minutes: number
    production_cents: number
    production_margin_cents: number | null
  }[]
  forecasts: {
    id: string
    month: string
    label: string
    incoming_cents: number
    outgoing_cents: number
    version: number
  }[]
  mileage: {
    id: string
    route: string
    distance_milli: number
    amount_cents: number
    rate_source: string
  }[]
  reminders: {
    id: string
    document_id: string
    level: number
    content: string
    status: string
  }[]
}
type Receivable = {
  document_id: string
  reference: string
  due_on: string
  balance_cents: number
  overdue_days: number
}
type Props = {
  data: ControlData
  matterId: string
  receivables: Receivable[]
  prepare: (action: string, payload: Record<string, unknown>) => Promise<void>
  cents: (v: string) => number
  onEdit: () => void
  Button: ComponentType<ButtonHTMLAttributes<HTMLButtonElement>>
  Input: ComponentType<InputHTMLAttributes<HTMLInputElement>>
}

const euro = (n: number | null) =>
  n === null
    ? 'Coûts incomplets'
    : new Intl.NumberFormat('fr-FR', {
        style: 'currency',
        currency: 'EUR'
      }).format(n / 100)

const day = () => new Intl.DateTimeFormat('en-CA').format(new Date())
type Shared = Pick<Props, 'data' | 'prepare' | 'cents' | 'onEdit' | 'Button' | 'Input'> & {
  invoke: (action: string, payload: () => Record<string, unknown>) => void
}

function AccountingImport({ data, prepare, onEdit, Button, Input }: Shared) {
  const [file, setFile] = useState<{
    filename: string
    content: string
  } | null>(null)

  const [error, setError] = useState('')

  return (
    <details>
      <summary>Importer un FEC et rapprocher les pièces</summary>
      <p>
        Format débit/crédit à 18 colonnes, séparées par tabulation ou |. Limite actuelle : 60 000 caractères. Contrôle
        d’équilibre par écriture et détection des doublons. L’import conserve les écritures ; il ne recrée aucune
        facture.
      </p>
      <label>
        Fichier FEC
        <Input
          accept=".txt,.fec,.csv"
          onChange={async e => {
            onEdit()
            setFile(null)
            setError('')
            const selected = e.target.files?.[0]

            if (!selected) {
              return
            }

            try {
              if (selected.size > 240000) {
                throw Error('Fichier trop volumineux pour cet import.')
              }

              const bytes = await selected.arrayBuffer()
              let content: string

              try {
                content = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
              } catch {
                content = new TextDecoder('windows-1252').decode(bytes)
              }

              if (content.length > 60000) {
                throw Error('Limite actuelle : 60 000 caractères.')
              }

              if (new TextEncoder().encode(JSON.stringify({ filename: selected.name, content })).length > 85000) {
                throw Error('FEC trop volumineux pour le pont actuel.')
              }

              setFile({ filename: selected.name, content })
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Lecture impossible.')
            }
          }}
          type="file"
        />
      </label>
      {error && <p role="alert">{error}</p>}
      <Button disabled={!file} onClick={() => file && void prepare('finance.fec.import', file)} type="button">
        Contrôler et préparer l’import
      </Button>
      {data.imports.map(i => (
        <article key={i.id}>
          <strong>{i.filename}</strong>
          <p>
            {i.row_count} lignes · Débit {euro(i.debit_cents)} · Crédit {euro(i.credit_cents)}
          </p>
          <p>
            Produits comptables {euro(i.revenue_cents)} · Charges {euro(i.expense_cents)}
          </p>
          <p>
            Références rapprochées : {i.matched_references.join(', ') || 'aucune'}. À examiner :{' '}
            {i.unmatched_references.join(', ') || 'aucune'}.
          </p>
        </article>
      ))}
    </details>
  )
}

function Objectives({ invoke, data, prepare, cents, onEdit, Button, Input }: Shared) {
  const [user, setUser] = useState(''),
    [role, setRole] = useState('collaborator'),
    [start, setStart] = useState(day),
    [end, setEnd] = useState(day)

  const [revenue, setRevenue] = useState('0'),
    [margin, setMargin] = useState('0'),
    [minutes, setMinutes] = useState('0')

  const old = data.objectives.find(o => o.responsible_user === user && o.start_on === start && o.end_on === end)

  return (
    <details>
      <summary>Objectifs des collaborateurs et associés</summary>
      <p>
        Utiliser l’identifiant exact « responsable » des diligences. Les montants réalisés mesurent la production
        approuvée ; les encaissements restent suivis au dossier.
      </p>
      <form
        onChange={onEdit}
        onSubmit={e => {
          e.preventDefault()
          invoke('finance.objective.save', () => ({
            responsible_user: user,
            role,
            start_on: start,
            end_on: end,
            revenue_cents: cents(revenue),
            margin_cents: cents(margin),
            minutes: Number(minutes),
            expected_version: old?.version || 0
          }))
        }}
      >
        <label>
          Responsable
          <Input onChange={e => setUser(e.target.value)} required value={user} />
        </label>
        <select aria-label="Rôle du responsable" onChange={e => setRole(e.target.value)} value={role}>
          <option value="collaborator">Collaborateur</option>
          <option value="partner">Associé</option>
        </select>
        <label>
          Début de période
          <Input onChange={e => setStart(e.target.value)} required type="date" value={start} />
        </label>
        <label>
          Fin de période
          <Input onChange={e => setEnd(e.target.value)} required type="date" value={end} />
        </label>
        <label>
          Objectif de production HT (€)
          <Input
            inputMode="decimal"
            onChange={e => setRevenue(e.target.value)}
            pattern="[0-9]+([.,][0-9]{1,2})?"
            required
            value={revenue}
          />
        </label>
        <label>
          Objectif de marge (€)
          <Input
            inputMode="decimal"
            onChange={e => setMargin(e.target.value)}
            pattern="[0-9]+([.,][0-9]{1,2})?"
            required
            value={margin}
          />
        </label>
        <label>
          Objectif de temps (minutes)
          <Input min="0" onChange={e => setMinutes(e.target.value)} required step="1" type="number" value={minutes} />
        </label>
        <Button type="submit">Préparer l’objectif</Button>
      </form>
      {data.objectives.map(o => (
        <p key={o.id}>
          {o.responsible_user} · {o.role === 'partner' ? 'Associé' : 'Collaborateur'} · {o.start_on} → {o.end_on}
          <br />
          Production {euro(o.production_cents)} / {euro(o.revenue_cents)} · Marge {euro(o.production_margin_cents)} /{' '}
          {euro(o.margin_cents)} · Temps {o.actual_minutes} / {o.minutes} min
        </p>
      ))}
    </details>
  )
}

function Forecast({
  invoke,
  data,
  receivables,
  prepare,
  cents,
  onEdit,
  Button,
  Input
}: Shared & Pick<Props, 'receivables'>) {
  const [month, setMonth] = useState(day().slice(0, 7)),
    [label, setLabel] = useState('Scénario de base'),
    [incoming, setIncoming] = useState('0'),
    [outgoing, setOutgoing] = useState('0')

  const old = data.forecasts.find(f => f.month === month && f.label === label)

  return (
    <details>
      <summary>Prévisionnel mensuel de trésorerie</summary>
      <p>
        Les hypothèses sont saisies séparément des créances enregistrées. Le solde ci-dessous est un flux prévisionnel,
        sans solde bancaire initial.
      </p>
      <form
        onChange={onEdit}
        onSubmit={e => {
          e.preventDefault()
          invoke('finance.forecast.save', () => ({
            month,
            label,
            incoming_cents: cents(incoming),
            outgoing_cents: cents(outgoing),
            expected_version: old?.version || 0
          }))
        }}
      >
        <label>
          Mois
          <Input onChange={e => setMonth(e.target.value)} required type="month" value={month} />
        </label>
        <label>
          Scénario
          <Input onChange={e => setLabel(e.target.value)} required value={label} />
        </label>
        <label>
          Entrées prévues (€)
          <Input
            onChange={e => setIncoming(e.target.value)}
            pattern="[0-9]+([.,][0-9]{1,2})?"
            required
            value={incoming}
          />
        </label>
        <label>
          Sorties prévues (€)
          <Input
            onChange={e => setOutgoing(e.target.value)}
            pattern="[0-9]+([.,][0-9]{1,2})?"
            required
            value={outgoing}
          />
        </label>
        <Button type="submit">Préparer la prévision</Button>
      </form>
      {data.forecasts.map(f => (
        <p key={f.id}>
          {f.month} · {f.label} · Entrées {euro(f.incoming_cents)} · Sorties {euro(f.outgoing_cents)} · Flux net{' '}
          {euro(f.incoming_cents - f.outgoing_cents)}
          <br />
          Créances à échéance dans ce mois :{' '}
          {euro(receivables.filter(r => r.due_on.startsWith(f.month)).reduce((n, r) => n + r.balance_cents, 0))},
          présentées séparément.
        </p>
      ))}
    </details>
  )
}

function Mileage({ invoke, data, matterId, prepare, cents, onEdit, Button, Input }: Shared & Pick<Props, 'matterId'>) {
  const [user, setUser] = useState(''),
    [date, setDate] = useState(day),
    [route, setRoute] = useState(''),
    [distance, setDistance] = useState(''),
    [rate, setRate] = useState(''),
    [source, setSource] = useState('')

  return (
    <details>
      <summary>Indemnités kilométriques</summary>
      <p>
        Le taux saisi est un taux convenu, à justifier. Le barème fiscal annuel n’est pas calculé automatiquement.
        L’enregistrement crée un frais non facturable en attente de validation.
      </p>
      <form
        onChange={onEdit}
        onSubmit={e => {
          e.preventDefault()
          const km = distance.replace(',', '.')

          if (!/^\d+(\.\d{1,3})?$/.test(km)) {
            return
          }
          invoke('finance.mileage.add', () => ({
            matter_id: matterId,
            responsible_user: user,
            activity_date: date,
            route,
            distance_milli: Math.round(Number(km) * 1000),
            rate_cents: cents(rate),
            rate_source: source,
            billable: false
          }))
        }}
      >
        <label>
          Bénéficiaire
          <Input onChange={e => setUser(e.target.value)} required value={user} />
        </label>
        <label>
          Date du déplacement
          <Input onChange={e => setDate(e.target.value)} required type="date" value={date} />
        </label>
        <label>
          Trajet et motif
          <Input onChange={e => setRoute(e.target.value)} required value={route} />
        </label>
        <label>
          Distance (km)
          <Input
            inputMode="decimal"
            onChange={e => setDistance(e.target.value)}
            pattern="[0-9]+([.,][0-9]{1,3})?"
            required
            value={distance}
          />
        </label>
        <label>
          Taux convenu (€/km)
          <Input onChange={e => setRate(e.target.value)} pattern="[0-9]+([.,][0-9]{1,2})?" required value={rate} />
        </label>
        <label>
          Justification du taux
          <Input onChange={e => setSource(e.target.value)} required value={source} />
        </label>
        <Button disabled={!matterId} type="submit">
          Préparer le frais kilométrique
        </Button>
      </form>
      {data.mileage.map(m => (
        <p key={m.id}>
          {m.route} · {m.distance_milli / 1000} km · {euro(m.amount_cents)} · {m.rate_source}
        </p>
      ))}
    </details>
  )
}

function Reminders({ data, receivables, prepare, onEdit, Button, Input }: Shared & Pick<Props, 'receivables'>) {
  const [invoice, setInvoice] = useState(''),
    [message, setMessage] = useState('Merci de vérifier le règlement de cette facture.')

  const level = Math.max(0, ...data.reminders.filter(r => r.document_id === invoice).map(r => r.level)) + 1

  return (
    <details>
      <summary>Relances graduées et recouvrement amiable</summary>
      <p>
        Trois niveaux de projets : rappel amiable, deuxième relance, mise en demeure à vérifier. Aucun courrier n’est
        envoyé automatiquement.
      </p>
      <form
        onChange={onEdit}
        onSubmit={e => {
          e.preventDefault()
          void prepare('finance.reminder.prepare', {
            document_id: invoice,
            level,
            message
          })
        }}
      >
        <select
          aria-label="Créance échue à relancer"
          onChange={e => setInvoice(e.target.value)}
          required
          value={invoice}
        >
          <option value="">Choisir une créance échue</option>
          {receivables
            .filter(r => r.overdue_days > 0)
            .map(r => (
              <option key={r.document_id} value={r.document_id}>
                {r.reference} · {euro(r.balance_cents)}
              </option>
            ))}
        </select>
        <label>
          Message du projet
          <Input onChange={e => setMessage(e.target.value)} required value={message} />
        </label>
        <Button disabled={!invoice || level > 3} type="submit">
          Préparer la relance de niveau {level}
        </Button>
      </form>
      {data.reminders.map(r => (
        <article key={r.id}>
          <strong>Projet niveau {r.level} — non envoyé</strong>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{r.content}</pre>
        </article>
      ))}
    </details>
  )
}

export default function FinanceControls(props: Props) {
  const [error, setError] = useState('')

  const invoke = (action: string, payload: () => Record<string, unknown>) => {
    setError('')

    try {
      void props
        .prepare(action, payload())
        .catch(e => setError(e instanceof Error ? e.message : 'Préparation impossible.'))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Valeur invalide.')
    }
  }

  const shared = { ...props, invoke }

  return (
    <section aria-label="Comptabilité et prévisions">
      <h3>Comptabilité et prévisions</h3>
      {error && <p role="alert">{error}</p>}
      <AccountingImport {...shared} />
      <Objectives {...shared} />
      <Forecast {...shared} />
      <Mileage {...shared} />
      <Reminders {...shared} />
    </section>
  )
}
