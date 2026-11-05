import {
  type ButtonHTMLAttributes,
  type ComponentType,
  type InputHTMLAttributes,
  useState,
} from "react";

export interface CabinetOperationsData {
  parties: {
    id: string;
    name: string;
    role: string;
    email: string;
    phone: string;
    address: string;
    notes: string;
    version: number;
  }[];
  contracts: {
    id: string;
    party_id: string;
    title: string;
    start_on: string;
    end_on: string;
    amount_cents: number;
    status: string;
    version: number;
  }[];
  purchases: {
    id: string;
    supplier_id: string;
    reference: string;
    due_on: string;
    total_cents: number;
    balance_cents: number;
    status: string;
    version: number;
  }[];
  timers: {
    id: string;
    matter_id: string;
    description: string;
    elapsed_seconds: number;
    seconds: number;
    status: string;
    version: number;
  }[];
  supplier_balance_cents: number;
  scope: string;
}
interface Props {
  data: CabinetOperationsData;
  matterId: string;
  prepare: (action: string, payload: Record<string, unknown>) => Promise<void>;
  cents: (value: string) => number;
  onEdit: () => void;
  Button?: ComponentType<ButtonHTMLAttributes<HTMLButtonElement>>;
  Input?: ComponentType<InputHTMLAttributes<HTMLInputElement>>;
}

const euros = (value: number) =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(
    value / 100,
  );

const today = () => {
  const d = new Date();

  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export default function CabinetOperations({
  data,
  matterId,
  prepare,
  cents,
  onEdit,
  Button = (props) => <button {...props} />,
  Input = (props) => <input {...props} />,
}: Props) {
  const [name, setName] = useState(""),
    [role, setRole] = useState("supplier"),
    [email, setEmail] = useState(""),
    [phone, setPhone] = useState(""),
    [address, setAddress] = useState(""),
    [notes, setNotes] = useState(""),
    [partyId, setPartyId] = useState("");

  const [contractParty, setContractParty] = useState(""),
    [contractTitle, setContractTitle] = useState(""),
    [start, setStart] = useState(today),
    [end, setEnd] = useState(today),
    [contractAmount, setContractAmount] = useState("0");

  const [supplier, setSupplier] = useState(""),
    [reference, setReference] = useState(""),
    [due, setDue] = useState(today),
    [line, setLine] = useState(""),
    [unit, setUnit] = useState(""),
    [quantity, setQuantity] = useState("1"),
    [tax, setTax] = useState("0");

  const [lines, setLines] = useState<
    {
      description: string;
      quantity_milli: number;
      unit_cents: number;
      tax_bps: number;
    }[]
  >([]);

  const [orderId, setOrderId] = useState(""),
    [paid, setPaid] = useState(""),
    [paidReference, setPaidReference] = useState(""),
    [paidOn, setPaidOn] = useState(today);

  const [timerUser, setTimerUser] = useState("");

  const [timerDescription, setTimerDescription] = useState(""),
    [timerRate, setTimerRate] = useState("0"),
    [timerCost, setTimerCost] = useState(""),
    [timerBillable, setTimerBillable] = useState(true);

  const [error, setError] = useState("");

  function invoke(action: string, payload: () => Record<string, unknown>) {
    setError("");

    try {
      void prepare(action, payload()).catch((e) =>
        setError((e as Error).message),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function field(
    label: string,
    value: string,
    set: (value: string) => void,
    type = "text",
  ) {
    return (
      <label>
        {label}
        <Input
          onChange={(e) => set(e.target.value)}
          type={type}
          value={value}
        />
      </label>
    );
  }

  const party = data.parties.find((p) => p.id === partyId);

  const partyName = (id: string) =>
    data.parties.find((p) => p.id === id)?.name || id;

  const states: Record<string, string> = {
    draft: "Brouillon",
    ordered: "Commandé en interne",
    received: "Réceptionné",
    closed: "Clôturé",
    cancelled: "Annulé",
    active: "Actif",
    running: "En cours",
    paused: "Suspendu",
    finished: "Converti en diligence",
  };

  return (
    <section
      aria-label="Gestion commerciale du cabinet"
      className="finance-operations space-y-4"
      onChangeCapture={onEdit}
      onClickCapture={onEdit}
    >
      <h3>Tiers, contrats, achats et minuteurs</h3>
      <p>{data.scope}</p>
      {error && <p role="alert">{error}</p>}
      <details>
        <summary>Prospects, fournisseurs et partenaires</summary>
        <label>
          Tiers à modifier
          <select
            onChange={(e) => {
              const p = data.parties.find((p) => p.id === e.target.value);
              setPartyId(p?.id || "");
              setName(p?.name || "");
              setRole(p?.role || "supplier");
              setEmail(p?.email || "");
              setPhone(p?.phone || "");
              setAddress(p?.address || "");
              setNotes(p?.notes || "");
            }}
            value={partyId}
          >
            <option value="">Nouveau tiers</option>
            {data.parties.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {p.role}
              </option>
            ))}
          </select>
        </label>
        {field("Nom du tiers", name, setName)}
        <label>
          Rôle du tiers
          <select onChange={(e) => setRole(e.target.value)} value={role}>
            <option value="prospect">Prospect</option>
            <option value="supplier">Fournisseur</option>
            <option value="partner">Partenaire</option>
          </select>
        </label>
        {field("Email du tiers", email, setEmail, "email")}
        {field("Téléphone du tiers", phone, setPhone, "tel")}
        {field("Adresse du tiers", address, setAddress)}
        {field("Notes sur le tiers", notes, setNotes)}
        <Button
          disabled={!name.trim()}
          onClick={() =>
            invoke("business.party.save", () => ({
              id: partyId || null,
              expected_version: party?.version || 0,
              name,
              role,
              email,
              phone,
              address,
              notes,
            }))
          }
          type="button"
        >
          Préparer le tiers
        </Button>
        <ul>
          {data.parties.map((p) => (
            <li key={p.id}>
              {p.name} · {p.role} · {p.email} · {p.phone}
            </li>
          ))}
        </ul>
      </details>
      <details>
        <summary>Contrats et échéances commerciales</summary>
        <p>
          Suivi administratif des contrats. La signature et l’envoi restent des
          opérations distinctes.
        </p>
        <label>
          Partie au contrat
          <select
            onChange={(e) => setContractParty(e.target.value)}
            value={contractParty}
          >
            <option value="">Choisir un tiers</option>
            {data.parties.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        {field("Titre du contrat", contractTitle, setContractTitle)}
        {field("Début du contrat", start, setStart, "date")}
        {field("Fin du contrat", end, setEnd, "date")}
        {field("Montant du contrat HT (€)", contractAmount, setContractAmount)}
        <Button
          disabled={!contractParty || !contractTitle.trim()}
          onClick={() =>
            invoke("business.contract.save", () => ({
              party_id: contractParty,
              title: contractTitle,
              start_on: start,
              end_on: end,
              amount_cents: cents(contractAmount),
              status: "draft",
              expected_version: 0,
            }))
          }
          type="button"
        >
          Préparer le contrat
        </Button>
        {data.contracts.map((c) => (
          <article key={c.id}>
            <p>
              {c.title} · {partyName(c.party_id)} · {c.start_on} → {c.end_on} ·{" "}
              {euros(c.amount_cents)} HT · {states[c.status]}
            </p>
            {c.status !== "closed" && (
              <Button
                onClick={() =>
                  invoke("business.contract.save", () => ({
                    id: c.id,
                    party_id: c.party_id,
                    title: c.title,
                    start_on: c.start_on,
                    end_on: c.end_on,
                    amount_cents: c.amount_cents,
                    expected_version: c.version,
                    status: c.status === "draft" ? "active" : "closed",
                  }))
                }
                type="button"
              >
                {c.status === "draft"
                  ? "Préparer l’activation du contrat"
                  : "Préparer la clôture du contrat"}
              </Button>
            )}
          </article>
        ))}
      </details>
      <details>
        <summary>Achats et règlements fournisseurs</summary>
        <p>
          Solde des achats réceptionnés : {euros(data.supplier_balance_cents)}{" "}
          TTC. Aucun ordre bancaire n’est émis.
        </p>
        <label>
          Fournisseur de l’achat
          <select
            onChange={(e) => setSupplier(e.target.value)}
            value={supplier}
          >
            <option value="">Choisir un fournisseur</option>
            {data.parties
              .filter((p) => p.role === "supplier")
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
          </select>
        </label>
        {field("Référence achat", reference, setReference)}
        {field("Échéance achat", due, setDue, "date")}
        {field("Libellé de la ligne achat", line, setLine)}
        {field("Quantité achat", quantity, setQuantity)}
        {field("Prix unitaire HT achat (€)", unit, setUnit)}
        {field("Taxe achat (%)", tax, setTax)}
        <Button
          disabled={!line.trim() || lines.length >= 100}
          onClick={() => {
            try {
              if (!/^\d+(?:[.,]\d{1,3})?$/.test(quantity))
                {throw Error("Quantité positive à trois décimales maximum.");}

              const qty = Math.round(Number(quantity.replace(",", ".")) * 1000);

              if (qty < 1 || qty > 1000000)
                {throw Error("Quantité hors limites.");}

              const bps = cents(tax);

              if (bps > 10000) {throw Error("Taux de taxe hors limites.");}
              setLines([
                ...lines,
                {
                  description: line,
                  quantity_milli: qty,
                  unit_cents: cents(unit),
                  tax_bps: bps,
                },
              ]);
              setLine("");
              setError("");
            } catch (e) {
              setError((e as Error).message);
            }
          }}
          type="button"
        >
          Ajouter la ligne achat
        </Button>
        <ol>
          {lines.map((l, i) => (
            <li key={i}>
              {l.description} · {l.quantity_milli / 1000} ×{" "}
              {euros(l.unit_cents)} HT{" "}
              <Button
                onClick={() => setLines(lines.filter((_, n) => n !== i))}
                type="button"
              >
                Retirer la ligne {i + 1}
              </Button>
            </li>
          ))}
        </ol>
        <Button
          disabled={!supplier || !reference.trim() || !lines.length}
          onClick={() =>
            invoke("business.purchase.save", () => ({
              supplier_id: supplier,
              reference,
              due_on: due,
              lines,
            }))
          }
          type="button"
        >
          Préparer l’achat
        </Button>
        {data.purchases.map((p) => (
          <article key={p.id}>
            <p>
              {p.reference} · {partyName(p.supplier_id)} ·{" "}
              {euros(p.total_cents)} TTC · Solde {euros(p.balance_cents)} ·{" "}
              {states[p.status]}
            </p>
            {(
              {
                draft: ["ordered", "cancelled"],
                ordered: ["received", "cancelled"],
                received: ["closed"],
              }[p.status] || []
            ).map((status) => (
              <Button
                key={status}
                onClick={() =>
                  invoke("business.purchase.transition", () => ({
                    order_id: p.id,
                    expected_version: p.version,
                    status,
                  }))
                }
                type="button"
              >
                {
                  (
                    {
                      ordered: "Préparer la commande interne",
                      received: "Préparer la réception",
                      closed: "Préparer la clôture achat",
                      cancelled: "Préparer l’annulation achat",
                    } as Record<string, string>
                  )[status]
                }
              </Button>
            ))}
          </article>
        ))}
        <label>
          Achat à régler
          <select onChange={(e) => setOrderId(e.target.value)} value={orderId}>
            <option value="">Choisir un achat réceptionné</option>
            {data.purchases
              .filter((p) => p.status === "received" && p.balance_cents > 0)
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.reference} · {euros(p.balance_cents)}
                </option>
              ))}
          </select>
        </label>
        {field("Règlement fournisseur TTC (€)", paid, setPaid)}
        {field("Date du règlement fournisseur", paidOn, setPaidOn, "date")}
        {field(
          "Référence du règlement fournisseur",
          paidReference,
          setPaidReference,
        )}
        <Button
          disabled={!orderId || !paidReference.trim()}
          onClick={() =>
            invoke("business.supplier_payment.add", () => ({
              order_id: orderId,
              amount_cents: cents(paid),
              paid_on: paidOn,
              reference: paidReference,
            }))
          }
          type="button"
        >
          Préparer le règlement fournisseur
        </Button>
      </details>
      <details>
        <summary>Minuteur persistant par dossier</summary>
        <p>
          Sélectionnez le dossier dans le pilotage. Suspendez le minuteur avant
          conversion ; chaque minute commencée est arrondie à la minute
          supérieure. Actualisez pour relire le temps mesuré par le serveur.
        </p>
        {field("Responsable du minuteur", timerUser, setTimerUser)}
        {field("Diligence chronométrée", timerDescription, setTimerDescription)}
        {field("Taux horaire du minuteur (€)", timerRate, setTimerRate)}
        {field(
          "Coût horaire du minuteur (€), facultatif",
          timerCost,
          setTimerCost,
        )}
        <label className="finance-check">
          <Input
            checked={timerBillable}
            onChange={(e) => setTimerBillable(e.target.checked)}
            type="checkbox"
          />
          Minuteur facturable
        </label>
        <Button
          disabled={!matterId || !timerDescription.trim()}
          onClick={() =>
            invoke("finance.timer.start", () => ({
              matter_id: matterId,
              description: timerDescription,
              responsible_user: timerUser,
              rate_cents: cents(timerRate),
              cost_rate_cents: timerCost.trim() ? cents(timerCost) : null,
              billable: timerBillable,
            }))
          }
          type="button"
        >
          Préparer le démarrage du minuteur
        </Button>
        {data.timers
          .filter((t) => t.status !== "finished")
          .map((t) => (
            <article key={t.id}>
              <p>
                {t.description} · {t.elapsed_seconds} secondes ·{" "}
                {states[t.status]}
              </p>
              {(t.status === "running" ? ["pause"] : ["resume", "finish"]).map(
                (command) => (
                  <Button
                    disabled={command === "finish" && t.seconds < 1}
                    key={command}
                    onClick={() =>
                      invoke("finance.timer.change", () => ({
                        timer_id: t.id,
                        expected_version: t.version,
                        command,
                      }))
                    }
                    type="button"
                  >
                    {
                      (
                        {
                          pause: "Préparer la suspension",
                          resume: "Préparer la reprise",
                          finish: "Préparer la diligence chronométrée",
                        } as Record<string, string>
                      )[command]
                    }
                  </Button>
                ),
              )}
            </article>
          ))}
      </details>
    </section>
  );
}
