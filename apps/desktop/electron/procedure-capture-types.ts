export interface ProcedureSource {
  id: string
  name: string
}

export interface ProcedureCaptureApi {
  sources(): Promise<ProcedureSource[]>
  start(sourceId: string): Promise<{ token: string; name: string } | null>
  capture(token: string): Promise<{ png: Uint8Array; at: string }>
  stop(token: string): Promise<void>
}
