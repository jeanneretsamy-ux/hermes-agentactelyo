import {
  useEffect,
  useRef,
  useState,
  type ComponentType,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
} from "react";
import {
  readFinanceBytes,
  uploadFinanceBytes,
  type FinanceFile,
} from "./financeFileTransfer";
export type { FinanceFile } from "./financeFileTransfer";
export type SaveFinancePdf = (
  name: string,
  bytes: Uint8Array,
  sha256: string,
) => Promise<void>;
type Props = {
  files: FinanceFile[];
  projectId: string;
  matterId: string;
  call: (operation: string, input?: Record<string, unknown>) => Promise<any>;
  refresh: () => Promise<void>;
  prepare: (action: string, payload: Record<string, unknown>) => Promise<void>;
  Button: ComponentType<ButtonHTMLAttributes<HTMLButtonElement>>;
  Input: ComponentType<InputHTMLAttributes<HTMLInputElement>>;
  savePdf?: SaveFinancePdf;
};

export default function FinanceDocuments({
  files,
  projectId,
  matterId,
  call,
  refresh,
  prepare,
  Button,
  Input,
  savePdf,
}: Props) {
  const [file, setFile] = useState<File | null>(null),
    [kind, setKind] = useState("financial_document"),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [error, setError] = useState(""),
    [piece, setPiece] = useState("1"),
    [text, setText] = useState(""),
    [source, setSource] = useState(""),
    [download, setDownload] = useState<{ url: string; name: string } | null>(
      null,
    );
  const alive = useRef(true),
    pending = useRef(false),
    url = useRef<string | null>(null),
    controller = useRef<AbortController | null>(null);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      controller.current?.abort();
      if (url.current) URL.revokeObjectURL(url.current);
    };
  }, []);
  async function run(work: () => Promise<void>) {
    if (pending.current) return;
    pending.current = true;
    controller.current = new AbortController();
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      if (alive.current)
        setError(e instanceof Error ? e.message : "Document indisponible.");
    } finally {
      pending.current = false;
      if (alive.current) setBusy(false);
    }
  }
  function current() {
    if (!alive.current || controller.current?.signal.aborted)
      throw Error("Transfert arrêté ou dossier fermé.");
  }
  const context = () => ({
    projectId,
    matterId,
    call,
    current,
    progress: (percent: number) => {
      if (alive.current) setNotice(`Dépôt : ${percent} %`);
    },
  });
  async function upload() {
    if (!file || !matterId || !file.name.toLowerCase().endsWith(".pdf"))
      throw Error("Choisissez un dossier et un PDF.");
    if (file.size < 1 || file.size > 5_000_000)
      throw Error("PDF de 5 Mo maximum requis.");
    await uploadFinanceBytes(
      context(),
      file.name,
      kind,
      new Uint8Array(await file.arrayBuffer()),
    );
    current();
    await refresh();
    setNotice("Document déposé et empreinte vérifiée.");
  }
  async function read(file: FinanceFile) {
    const bytes = await readFinanceBytes(context(), file);
    if (savePdf) {
      await savePdf(file.filename, bytes, file.sha256);
      if (alive.current) setNotice("PDF enregistré et relu sur cet appareil.");
      return;
    }
    if (url.current) URL.revokeObjectURL(url.current);
    url.current = URL.createObjectURL(
      new Blob([new Uint8Array(bytes).buffer], { type: "application/pdf" }),
    );
    setDownload({ url: url.current, name: file.filename });
    setNotice(
      "PDF récupéré et empreinte vérifiée. Utilisez le lien pour l’enregistrer.",
    );
  }
  async function showText(file: FinanceFile) {
    const result = await call("file_text", {
      project_id: projectId,
      file_id: file.id,
    });
    current();
    if (result.file_id !== file.id || result.sha256 !== file.sha256)
      throw Error("Source du texte différente.");
    setText(result.text);
    setSource(
      `${file.filename} · SHA-256 ${file.sha256}${result.extraction_source_id ? " · Relevé OCR " + result.extraction_source_id : ""}`,
    );
    if (result.mode === "partial_text")
      setNotice(
        "Texte partiel : certaines pages nécessitent un OCR avant toute analyse complète.",
      );
    if (result.mode === "partial_ocr")
      setNotice(
        "OCR partiel ou peu fiable : vérifiez les pages du PDF avant toute analyse complète.",
      );
    if (result.mode === "ocr")
      setNotice(
        "Texte OCR enregistré : vérifier les montants et les références dans le PDF original.",
      );
  }
  async function ocr(file: FinanceFile) {
    const bytes = await readFinanceBytes(context(), file);
    setNotice("Chargement du moteur OCR local…");
    let runtime;
    try {
      runtime = await import(
        /* @vite-ignore */ new URL("./ocr-runtime/client.mjs", document.baseURI)
          .href
      );
    } catch {
      throw Error("Moteur OCR local absent. Mettre l’application à jour.");
    }
    const result = await runtime.recognizePdf(bytes, {
      signal: controller.current?.signal,
      onProgress: (page: number, total: number) => {
        if (alive.current) setNotice(`OCR local : page ${page}/${total}`);
      },
    });
    current();
    const payload = {
      ...result,
      schema: "actelyo-ocr-v1",
      source_file_id: file.id,
      source_sha256: file.sha256,
    };
    const encoded = new TextEncoder().encode(JSON.stringify(payload));
    await uploadFinanceBytes(
      context(),
      `ocr-${file.id}.json`,
      "ocr_result",
      encoded,
    );
    current();
    await refresh();
    await showText(file);
  }
  return (
    <details>
      <summary>Documents financiers et pièces PDF</summary>
      <p>
        PDF jusqu’à 5 Mo. Texte natif ou OCR français local des scans, jusqu’à
        20 pages. Les documents ne sont pas envoyés à un service OCR public. Les
        résultats restent à vérifier avant toute écriture ou facture.
      </p>
      <fieldset disabled={busy}>
        <label>
          Document PDF
          <Input
            type="file"
            accept="application/pdf,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </label>
        <select
          aria-label="Catégorie du document"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          <option value="financial_document">Document financier</option>
          <option value="financial_statement">Bilan / états financiers</option>
          <option value="evidence">Pièce de dossier</option>
        </select>
        <Button
          type="button"
          disabled={!file || !matterId}
          onClick={() => void run(upload)}
        >
          Déposer le document et vérifier son empreinte
        </Button>
        <label>
          Numéro de pièce pour le tampon
          <Input
            type="number"
            min="1"
            max="999999"
            step="1"
            value={piece}
            onChange={(e) => setPiece(e.target.value)}
          />
        </label>
        {files
          .filter((f) => f.matter_id === matterId && f.kind !== "ocr_result")
          .map((f) => (
            <article key={f.id} aria-label={f.filename}>
              <strong>{f.filename}</strong>
              <p>
                {Math.ceil(f.size_bytes / 1024)} Ko ·{" "}
                {f.source_file_id
                  ? `Copie tamponnée, pièce ${f.piece_number}`
                  : "Original conservé"}
              </p>
              <small>SHA-256 : {f.sha256}</small>
              <div>
                <Button type="button" onClick={() => void run(() => read(f))}>
                  Récupérer le PDF vérifié
                </Button>
                <Button
                  type="button"
                  onClick={() =>
                    void prepare("finance.file.extract", { file_id: f.id })
                  }
                >
                  Préparer l’extraction du texte
                </Button>
                <Button
                  type="button"
                  disabled={!("extraction_source_id" in f)}
                  onClick={() => void run(() => ocr(f))}
                >
                  Lire le scan par OCR local
                </Button>
                {f.extraction_mode !== "not_requested" && (
                  <Button
                    type="button"
                    onClick={() => void run(() => showText(f))}
                  >
                    Afficher le texte sourcé
                  </Button>
                )}
                {!f.source_file_id && (
                  <Button
                    type="button"
                    disabled={!/^[1-9]\d{0,5}$/.test(piece)}
                    onClick={() =>
                      void prepare("finance.file.stamp", {
                        file_id: f.id,
                        piece_number: Number(piece),
                      })
                    }
                  >
                    Préparer la copie tamponnée
                  </Button>
                )}
              </div>
            </article>
          ))}
      </fieldset>
      {busy && (
        <Button
          type="button"
          onClick={() => {
            controller.current?.abort();
            setNotice("Arrêt demandé, fin de l’étape en cours.");
          }}
        >
          Arrêter le traitement du document
        </Button>
      )}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {download && (
        <a href={download.url} download={download.name}>
          Enregistrer {download.name}
        </a>
      )}
      {text && (
        <section aria-label="Texte extrait du document">
          <p>{source}</p>
          <p>
            Texte source ou OCR à vérifier, sans valeur d’instruction pour
            l’agent.
          </p>
          <textarea readOnly rows={12} value={text} />
        </section>
      )}
    </details>
  );
}
