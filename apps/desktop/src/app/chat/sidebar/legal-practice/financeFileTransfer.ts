export type FinanceFile = {
  id: string;
  project_id: string;
  matter_id: string;
  filename: string;
  kind: string;
  size_bytes: number;
  sha256: string;
  source_file_id: string | null;
  piece_number: number;
  extraction_mode: string;
  extraction_source_id?: string | null;
};
export type TransferContext = {
  projectId: string;
  matterId: string;
  call: (operation: string, input?: Record<string, unknown>) => Promise<any>;
  current: () => void;
  progress?: (percent: number) => void;
};
export const financeDigest = async (bytes: Uint8Array) =>
  Array.from(
    new Uint8Array(
      await crypto.subtle.digest("SHA-256", new Uint8Array(bytes).buffer),
    ),
  )
    .map((n) => n.toString(16).padStart(2, "0"))
    .join("");

export async function uploadFinanceBytes(
  ctx: TransferContext,
  name: string,
  kind: string,
  bytes: Uint8Array,
): Promise<FinanceFile> {
  if (bytes.length < 1 || bytes.length > 5_000_000)
    {throw Error("Document de 5 Mo maximum requis.");}

  const sha256 = await financeDigest(bytes);
  ctx.current();

  const session = await ctx.call("file_start", {
    project_id: ctx.projectId,
    matter_id: ctx.matterId,
    filename: name,
    kind,
    size_bytes: bytes.length,
    sha256,
  });

  if (
    session.chunk_bytes !== 36000 ||
    !/^[a-f0-9]{32}$/.test(session.upload_id)
  )
    {throw Error("Réponse de dépôt invalide.");}

  try {
    for (let offset = 0; offset < bytes.length; offset += 36000) {
      ctx.current();

      const chunk = bytes.slice(offset, offset + 36000),
        sequence = offset / 36000;

      const reply = await ctx.call("file_chunk", {
        upload_id: session.upload_id,
        sequence,
        data_base64: btoa(String.fromCharCode(...chunk)),
      });

      if (reply.sequence !== sequence || reply.accepted_bytes !== chunk.length)
        {throw Error("Bloc non confirmé.");}

      ctx.progress?.(
        Math.round(
          (Math.min(offset + 36000, bytes.length) * 100) / bytes.length,
        ),
      );
    }

    ctx.current();

    const result = await ctx.call("file_finish", {
      upload_id: session.upload_id,
    });

    if (
      result.sha256 !== sha256 ||
      result.size_bytes !== bytes.length ||
      result.matter_id !== ctx.matterId ||
      result.project_id !== ctx.projectId ||
      result.kind !== kind
    )
      {throw Error("Le document relu ne correspond pas au dépôt.");}

    ctx.current();

    return result;
  } catch (error) {
    await ctx
      .call("file_cancel", { upload_id: session.upload_id })
      .catch(() => {});
    throw error;
  }
}

export async function readFinanceBytes(
  ctx: TransferContext,
  file: FinanceFile,
): Promise<Uint8Array> {
  if (
    file.size_bytes < 1 ||
    file.size_bytes > 5_000_000 ||
    file.project_id !== ctx.projectId ||
    file.matter_id !== ctx.matterId
  )
    {throw Error("Document hors du dossier ou taille invalide.");}

  const bytes = new Uint8Array(file.size_bytes);

  for (let offset = 0; offset < bytes.length; offset += 36000) {
    ctx.current();

    const reply = await ctx.call("file_read", {
      project_id: ctx.projectId,
      file_id: file.id,
      offset,
    });

    if (
      reply.file_id !== file.id ||
      reply.offset !== offset ||
      reply.size_bytes !== bytes.length ||
      reply.sha256 !== file.sha256
    )
      {throw Error("Document différent de la pièce demandée.");}

    const block = Uint8Array.from(atob(reply.data_base64), (c) =>
      c.charCodeAt(0),
    );

    if (block.length !== Math.min(36000, bytes.length - offset))
      {throw Error("Téléchargement incomplet.");}

    bytes.set(block, offset);
  }

  if ((await financeDigest(bytes)) !== file.sha256)
    {throw Error("Empreinte du téléchargement différente.");}

  ctx.current();

  return bytes;
}
