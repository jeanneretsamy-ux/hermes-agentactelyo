/** Preserve evidence order; cancellation is checked before and during each upload. */
export async function attachImageBatch(
  blobs: Blob[],
  attach: (blob: Blob, isCurrent?: () => boolean) => Promise<boolean | void> | boolean | void,
  isCurrent: () => boolean
): Promise<boolean> {
  try {
    for (const blob of blobs) {
      if (!isCurrent() || (await attach(blob, isCurrent)) === false) {
        return false
      }
    }

    return isCurrent()
  } catch {
    return false
  }
}
