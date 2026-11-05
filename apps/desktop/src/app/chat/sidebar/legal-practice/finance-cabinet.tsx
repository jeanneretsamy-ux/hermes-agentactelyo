import {
  useEffect,
  useRef,
  useState,
  type ComponentType,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
} from "react";
import CabinetOperations, {
  type CabinetOperationsData,
} from "./CabinetOperations";
import FinanceControls, { type ControlData } from "./FinanceControls";
import BillingOrders, { type BillingOrder } from "./BillingOrders";
import FinanceDocuments, {
  type FinanceFile,
  type SaveFinancePdf,
} from "./FinanceDocuments";
export type FinanceCall = (
  operation: string,
  input?: Record<string, unknown>,
) => Promise<any>;
type Metrics = {
  minutes: number;
  billable_minutes: number;
  unbilled_cents: number;
  pending_cents: number;
  cost_cents: number;
  billed_net_cents: number;
  cash_received_cents: number;
  outstanding_cents: number;
  missing_costs: number;
  margin_cents: number | null;
};
type Matter = Metrics & {
  id: string;
  title: string;
  reference: string;
  client: string;
  budget: null | {
    budget_minutes: number;
    revenue_cents: number;
    cost_cents: number;
    version: number;
  };
  time_over_budget: boolean;
  cost_over_budget: boolean;
};
type Fee = {
  id: string;
  matter_id: string;
  description: string;
  net_cents: number;
  activity_date: string;
  expense_type: string;
};
type Snapshot = {
  project_id: string;
  as_of: string;
  totals: Metrics;
  matters: Matter[];
  ageing: Record<string, number>;
  receivables: {
    document_id: string;
    reference: string;
    client: string;
    balance_cents: number;
    overdue_days: number;
    due_on: string;
  }[];
  pending_fees: Fee[];
  ready_fees: Fee[];
  scope: string;
  operations?: CabinetOperationsData & {
    controls?: ControlData;
    billing_orders?: BillingOrder[];
    files?: FinanceFile[];
  };
};
export function financeCents(value: string) {
  const m = value
    .trim()
    .replace(",", ".")
    .match(/^(\d+)(?:\.(\d{1,2}))?$/);
  if (!m) throw Error("Montant positif avec deux décimales maximum requis.");
  const n = Number(m[1]) * 100 + Number((m[2] || "").padEnd(2, "0"));
  if (!Number.isSafeInteger(n) || n > 1_000_000_000)
    throw Error("Montant trop élevé.");
  return n;
}
const money = (n: number | null) =>
  n === null
    ? "Coûts à compléter"
    : new Intl.NumberFormat("fr-FR", {
        style: "currency",
        currency: "EUR",
      }).format(n / 100);
const localDay = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const NativeButton = (props: ButtonHTMLAttributes<HTMLButtonElement>) => (
  <button {...props} />
);
const NativeInput = (props: InputHTMLAttributes<HTMLInputElement>) => (
  <input {...props} />
);

export default function FinanceCabinet({
  call,
  projectId,
  Button = NativeButton,
  Input = NativeInput,
  savePdf,
}: {
  call: FinanceCall;
  projectId: string;
  savePdf?: SaveFinancePdf;
  Button?: ComponentType<ButtonHTMLAttributes<HTMLButtonElement>>;
  Input?: ComponentType<InputHTMLAttributes<HTMLInputElement>>;
}) {
  const [data, setData] = useState<Snapshot | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [proposal, setProposal] = useState<any>(null),
    [csv, setCsv] = useState(""),
    [notice, setNotice] = useState("");
  const [purpose, setPurpose] = useState("standard");
  const [matterId, setMatterId] = useState(""),
    [description, setDescription] = useState(""),
    [kind, setKind] = useState("time"),
    [minutes, setMinutes] = useState("60"),
    [amount, setAmount] = useState(""),
    [cost, setCost] = useState(""),
    [tax, setTax] = useState("0"),
    [billable, setBillable] = useState(true),
    [responsible, setResponsible] = useState(""),
    [activityDate, setActivityDate] = useState(localDay);
  const [budgetMinutes, setBudgetMinutes] = useState("0"),
    [budgetRevenue, setBudgetRevenue] = useState("0"),
    [budgetCost, setBudgetCost] = useState("0"),
    [selectedFees, setSelectedFees] = useState<string[]>([]),
    [dueOn, setDueOn] = useState(localDay),
    [invoiceId, setInvoiceId] = useState(""),
    [payment, setPayment] = useState(""),
    [paymentRef, setPaymentRef] = useState("");
  const generation = useRef(0),
    pending = useRef(false);
  useEffect(() => {
    generation.current++;
    pending.current = false;
    setBusy(false);
    setData(null);
    setProposal(null);
    setCsv("");
    setMatterId("");
    setError("");
    setNotice("");
    setSelectedFees([]);
    setInvoiceId("");
    setPayment("");
    setPaymentRef("");
    return () => {
      generation.current++;
    };
  }, [projectId]);
  async function run(fn: () => Promise<void>) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    const version = generation.current;
    try {
      await fn();
    } catch (e) {
      if (version === generation.current) setError((e as Error).message);
    } finally {
      if (version === generation.current) {
        pending.current = false;
        setBusy(false);
      }
    }
  }
  async function refresh() {
    const version = generation.current;
    const value = await call("snapshot", { project_id: projectId });
    if (version === generation.current) {
      if (value.project_id !== projectId)
        throw Error("Le moteur a répondu pour un autre espace.");
      setData(value);
      setProposal(null);
    }
  }
  async function prepare(action: string, payload: Record<string, unknown>) {
    const version = generation.current;
    const value = await call("prepare", {
      project_id: projectId,
      action,
      payload,
    });
    if (version === generation.current) {
      setProposal(value);
      setNotice(
        "Préparation disponible : vérifiez les valeurs avant confirmation.",
      );
    }
  }
  const matter = data?.matters.find((m) => m.id === matterId);
  function selectMatter(id: string) {
    setMatterId(id);
    setProposal(null);
    setSelectedFees([]);
    const b = data?.matters.find((m) => m.id === id)?.budget;
    setBudgetMinutes(String(b?.budget_minutes || 0));
    setBudgetRevenue(((b?.revenue_cents || 0) / 100).toFixed(2));
    setBudgetCost(((b?.cost_cents || 0) / 100).toFixed(2));
  }
  const text = (
    label: string,
    value: string,
    setter: (v: string) => void,
    type = "text",
  ) => (
    <label>
      {label}
      <Input
        type={type}
        value={value}
        onChange={(e) => {
          setter(e.target.value);
          setProposal(null);
        }}
      />
    </label>
  );
  return (
    <section
      className="finance-cabinet min-w-0 space-y-4"
      aria-label="Pilotage financier du cabinet"
    >
      <h3 className="text-lg font-semibold">Production, budgets et encours</h3>
      <p>
        Source : moteur financier du Law Harness associé. Les écritures
        préparées ici utilisent ce même registre sur PC et mobile.
      </p>
      <Button
        type="button"
        disabled={busy || !projectId}
        onClick={() => void run(refresh)}
      >
        Actualiser le registre réel
      </Button>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {data && (
        <>
          <p>{data.scope}</p>
          <dl className="finance-metrics grid gap-3 md:grid-cols-3">
            {[
              ["Factures internes HT", data.totals.billed_net_cents],
              ["Non facturé approuvé HT", data.totals.unbilled_cents],
              ["À valider HT", data.totals.pending_cents],
              ["Encours TTC", data.totals.outstanding_cents],
              ["Règlements saisis TTC", data.totals.cash_received_cents],
              [
                "Projection de marge sur coûts saisis",
                data.totals.margin_cents,
              ],
            ].map(([label, value]) => (
              <div key={String(label)}>
                <dt>{String(label)}</dt>
                <dd>{money(value as number | null)}</dd>
              </div>
            ))}
          </dl>
          <p>
            {data.totals.minutes} minutes de travail ·{" "}
            {data.totals.billable_minutes} facturables ·{" "}
            {data.totals.missing_costs} coût(s) non renseigné(s)
          </p>
          <fieldset disabled={busy} className="min-w-0 space-y-4">
            {data.operations && (
              <CabinetOperations
                Button={Button}
                Input={Input}
                key={projectId}
                data={data.operations}
                matterId={matterId}
                cents={financeCents}
                onEdit={() => setProposal(null)}
                prepare={async (action, payload) => {
                  await run(() => prepare(action, payload));
                }}
              />
            )}
            <label>
              Dossier
              <select
                aria-label="Dossier"
                value={matterId}
                onChange={(e) => selectMatter(e.target.value)}
              >
                <option value="">Choisir un dossier du registre</option>
                {data.matters.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.reference} — {m.title} · {m.client}
                  </option>
                ))}
              </select>
            </label>
            {matter && (
              <>
                <details>
                  <summary>Budget et rentabilité de ce dossier</summary>
                  <p>
                    Travail : {matter.minutes} min · Factures internes HT :{" "}
                    {money(matter.billed_net_cents)} · Coûts saisis :{" "}
                    {money(matter.cost_cents)} · Marge :{" "}
                    {money(matter.margin_cents)}
                  </p>
                  {(matter.time_over_budget || matter.cost_over_budget) && (
                    <p role="alert">Budget de temps ou de coût dépassé.</p>
                  )}
                  {text(
                    "Budget de temps (minutes)",
                    budgetMinutes,
                    setBudgetMinutes,
                    "number",
                  )}
                  {text(
                    "Objectif de facturation HT (€)",
                    budgetRevenue,
                    setBudgetRevenue,
                  )}
                  {text(
                    "Budget de coûts internes (€)",
                    budgetCost,
                    setBudgetCost,
                  )}
                  <Button
                    type="button"
                    onClick={() =>
                      void run(() =>
                        prepare("finance.budget.save", {
                          matter_id: matterId,
                          expected_version: matter.budget?.version || 0,
                          budget_minutes: Number(budgetMinutes),
                          revenue_cents: financeCents(budgetRevenue),
                          cost_cents: financeCents(budgetCost),
                        }),
                      )
                    }
                  >
                    Préparer le budget
                  </Button>
                </details>
                <details>
                  <summary>Saisir une diligence ou une dépense</summary>
                  {text("Libellé", description, setDescription)}
                  <label>
                    Nature
                    <select
                      value={kind}
                      onChange={(e) => {
                        setKind(e.target.value);
                        setProposal(null);
                      }}
                    >
                      <option value="time">Temps passé</option>
                      <option value="fixed">Forfait</option>
                      <option value="office">Frais du cabinet</option>
                      <option value="disbursement">Débours client</option>
                    </select>
                  </label>
                  {kind === "time" &&
                    text("Durée (minutes)", minutes, setMinutes, "number")}
                  {text(
                    kind === "time"
                      ? "Taux facturable (€/heure)"
                      : "Montant HT (€)",
                    amount,
                    setAmount,
                  )}
                  {text(
                    kind === "time"
                      ? "Coût interne (€/heure), facultatif"
                      : "Coût interne total (€), facultatif",
                    cost,
                    setCost,
                  )}
                  {text("Taux de taxe (%) défini par le cabinet", tax, setTax)}
                  {text(
                    "Collaborateur / responsable",
                    responsible,
                    setResponsible,
                  )}
                  {text(
                    "Date de travail",
                    activityDate,
                    setActivityDate,
                    "date",
                  )}
                  <label className="finance-check">
                    <input
                      type="checkbox"
                      checked={billable}
                      onChange={(e) => {
                        setBillable(e.target.checked);
                        setProposal(null);
                      }}
                    />
                    Facturable
                  </label>
                  <Button
                    type="button"
                    disabled={!description.trim()}
                    onClick={() =>
                      void run(() =>
                        prepare("fee.add", {
                          matter_id: matterId,
                          description,
                          kind:
                            kind === "time" || kind === "fixed"
                              ? kind
                              : "expense",
                          ...(kind === "time"
                            ? {
                                minutes: Number(minutes),
                                rate_cents: financeCents(amount || "0"),
                              }
                            : { amount_cents: financeCents(amount || "0") }),
                          ...(cost.trim()
                            ? {
                                [kind === "time"
                                  ? "cost_rate_cents"
                                  : "cost_cents"]: financeCents(cost),
                              }
                            : {}),
                          tax_bps: financeCents(tax),
                          responsible_user: responsible,
                          activity_date: activityDate,
                          billable,
                          approval_status: "draft",
                          expense_type:
                            kind === "office" || kind === "disbursement"
                              ? kind
                              : "",
                        }),
                      )
                    }
                  >
                    Préparer la diligence à valider
                  </Button>
                </details>
                <details>
                  <summary>Contrôler les diligences en attente</summary>
                  {data.pending_fees
                    .filter((f) => f.matter_id === matterId)
                    .map((f) => (
                      <article key={f.id}>
                        <p>
                          {f.activity_date} · {f.description} ·{" "}
                          {money(f.net_cents)} HT{" "}
                          {f.expense_type === "disbursement" ? "· Débours" : ""}
                        </p>
                        {(["approved", "rejected"] as const).map((status) => (
                          <Button
                            type="button"
                            key={status}
                            onClick={() =>
                              void run(() =>
                                prepare("finance.fee.review", {
                                  fee_id: f.id,
                                  approval_status: status,
                                  reason:
                                    status === "approved"
                                      ? "Diligence contrôlée et validée depuis le pilotage."
                                      : "Diligence refusée depuis le pilotage.",
                                }),
                              )
                            }
                          >
                            {status === "approved"
                              ? "Préparer la validation"
                              : "Préparer le refus"}
                          </Button>
                        ))}
                      </article>
                    ))}
                </details>
                <details>
                  <summary>Préparer une facture ou un devis interne</summary>
                  <p>
                    Choisissez les lignes approuvées. Les paramètres de
                    facturation et l’identité du cabinet sont contrôlés par le
                    moteur.
                  </p>
                  {data.ready_fees
                    .filter((f) => f.matter_id === matterId)
                    .map((f) => (
                      <label className="finance-check" key={f.id}>
                        <input
                          type="checkbox"
                          checked={selectedFees.includes(f.id)}
                          onChange={(e) => {
                            setSelectedFees(
                              e.target.checked
                                ? [...selectedFees, f.id]
                                : selectedFees.filter((id) => id !== f.id),
                            );
                            setProposal(null);
                          }}
                        />
                        {f.description} · {money(f.net_cents)} HT
                      </label>
                    ))}
                  <label>
                    Type de facture
                    <select
                      aria-label="Type de facture"
                      value={purpose}
                      onChange={(e) => {
                        setPurpose(e.target.value);
                        setProposal(null);
                      }}
                    >
                      <option value="standard">Facture standard</option>
                      <option value="provision_fees">
                        Provision sur honoraires
                      </option>
                      <option value="provision_expenses">
                        Provision sur frais
                      </option>
                      <option value="provision_expenses_fees">
                        Provision sur frais et honoraires
                      </option>
                    </select>
                  </label>
                  {text("Échéance", dueOn, setDueOn, "date")}
                  {(["quote", "invoice"] as const).map((type) => (
                    <Button
                      key={type}
                      type="button"
                      disabled={!selectedFees.length}
                      onClick={() =>
                        void run(() =>
                          prepare("document.create", {
                            matter_id: matterId,
                            kind: type,
                            purpose: type === "quote" ? "standard" : purpose,
                            fee_ids: selectedFees,
                            due_on: dueOn,
                          }),
                        )
                      }
                    >
                      {type === "quote"
                        ? "Préparer le devis"
                        : "Préparer la facture interne"}
                    </Button>
                  ))}
                </details>
              </>
            )}
            <details>
              <summary>Encours, échéances et règlements</summary>
              <p>
                Au {data.as_of}, montants TTC. Les règlements enregistrés ici ne
                déclenchent aucun mouvement bancaire.
              </p>
              <ul>
                {Object.entries(data.ageing).map(([key, value]) => (
                  <li key={key}>
                    {{
                      not_due: "Non échu",
                      days_1_30: "Retard 1–30 jours",
                      days_31_60: "Retard 31–60 jours",
                      days_61_90: "Retard 61–90 jours",
                      days_over_90: "Retard supérieur à 90 jours",
                    }[key] || key}{" "}
                    : {money(value)}
                  </li>
                ))}
              </ul>
              {data.receivables.map((r) => (
                <p key={r.document_id}>
                  {r.client} · {r.reference} · {r.due_on} · {r.overdue_days}{" "}
                  jour(s) de retard · {money(r.balance_cents)}
                </p>
              ))}
              <label>
                Facture à rapprocher
                <select
                  aria-label="Facture à rapprocher"
                  value={invoiceId}
                  onChange={(e) => {
                    setInvoiceId(e.target.value);
                    setProposal(null);
                  }}
                >
                  <option value="">Choisir une facture</option>
                  {data.receivables.map((r) => (
                    <option key={r.document_id} value={r.document_id}>
                      {r.client} · {r.reference} · {money(r.balance_cents)}
                    </option>
                  ))}
                </select>
              </label>
              {text("Montant TTC du règlement (€)", payment, setPayment)}
              {text("Référence du règlement", paymentRef, setPaymentRef)}
              <Button
                type="button"
                disabled={!invoiceId || !payment.trim()}
                onClick={() =>
                  void run(() =>
                    prepare("payment.add", {
                      document_id: invoiceId,
                      amount_cents: financeCents(payment),
                      paid_on: localDay(),
                      reference: paymentRef,
                    }),
                  )
                }
              >
                Préparer le rapprochement
              </Button>
            </details>
            <Button
              type="button"
              onClick={() =>
                void run(async () => {
                  const version = generation.current;
                  const result = await call("export", {
                    project_id: projectId,
                  });
                  if (version === generation.current) setCsv(result.content);
                })
              }
            >
              Afficher l’export CSV de pilotage
            </Button>
          </fieldset>
          {data.operations?.controls && (
            <fieldset disabled={busy} onChange={() => setProposal(null)}>
              <FinanceControls
                data={data.operations.controls}
                matterId={matterId}
                receivables={data.receivables}
                prepare={async (action, payload) => {
                  await run(() => prepare(action, payload));
                }}
                cents={financeCents}
                onEdit={() => setProposal(null)}
                Button={Button}
                Input={Input}
              />
            </fieldset>
          )}
          <fieldset disabled={busy} onChange={() => setProposal(null)}>
            {data.operations?.billing_orders && (
              <BillingOrders
                key={"baf:" + projectId + ":" + matterId}
                orders={data.operations.billing_orders}
                fees={data.ready_fees}
                matterId={matterId}
                onEdit={() => setProposal(null)}
                prepare={async (action, payload) => {
                  await run(() => prepare(action, payload));
                }}
                Button={Button}
                Input={Input}
              />
            )}
            {data.operations?.files && (
              <FinanceDocuments
                key={"files:" + projectId + ":" + matterId}
                files={data.operations.files}
                projectId={projectId}
                matterId={matterId}
                call={call}
                refresh={refresh}
                prepare={async (action, payload) => {
                  await run(() => prepare(action, payload));
                }}
                Button={Button}
                Input={Input}
                savePdf={savePdf}
              />
            )}
          </fieldset>
          {proposal && (
            <section aria-label="Confirmation financière">
              <h4 className="font-semibold">Préparation à confirmer</h4>
              <p>{proposal.description}</p>
              <pre className="whitespace-pre-wrap break-words">
                {JSON.stringify(
                  {
                    operation: proposal.action,
                    espace: projectId,
                    parametres: proposal.params,
                  },
                  null,
                  2,
                )}
              </pre>
              <p>
                Les montants des paramètres sont exprimés en centimes ; les taux
                de taxe en centièmes de pourcentage.
              </p>
              <Button
                type="button"
                disabled={busy}
                onClick={() =>
                  void run(async () => {
                    const version = generation.current;
                    const result = await call("apply", {
                      proposal_id: proposal.proposal_id,
                      approved: true,
                    });
                    if (version !== generation.current) return;
                    if (
                      !result.applied ||
                      result.readback?.project_id !== projectId
                    )
                      throw Error(
                        "La relecture n’a pas confirmé l’espace financier.",
                      );
                    setData(result.readback);
                    setProposal(null);
                    setSelectedFees([]);
                    setNotice(
                      "Écriture enregistrée et registre relu. Référence : " +
                        result.native_request_id,
                    );
                  })
                }
              >
                Confirmer l’enregistrement
              </Button>
              <Button
                type="button"
                disabled={busy}
                onClick={() => setProposal(null)}
              >
                Annuler cette préparation
              </Button>
            </section>
          )}
          {csv && (
            <details open>
              <summary>
                Export de pilotage CSV — centimes, séparateur point-virgule
              </summary>
              <p>
                Export analytique consultable et copiable. Les connecteurs
                comptables et la facture électronique nécessitent un
                raccordement distinct.
              </p>
              <textarea readOnly rows={8} value={csv} />
            </details>
          )}
        </>
      )}
    </section>
  );
}
