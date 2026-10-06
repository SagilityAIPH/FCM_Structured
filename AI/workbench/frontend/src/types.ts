export type Status = 'Ready' | 'Queued' | 'Processing' | 'Completed' | 'Needs Review' | 'Failed'
export interface Settings { region: string; model: string; max_tokens: number; temperature: number; document_limit: number }
export interface DocumentRow { id: string; name: string; status: Status; pages: number; revision: number; error: string; elapsed: number; workbook: string; save_error: string; claimant: string; claim: string; next_step: 'Passed' | 'Failed' | null; issues: number }
export interface State { documents: DocumentRow[]; busy: boolean; stage: string; bedrock: string; elapsed: number; progress: { done: number; total: number }; settings: Settings; key_configured: boolean; output_directory: string }
export interface Field { key: string; label: string; value: string; provider_index: number | null; confidence: number | null; manual: boolean; optional: boolean; conditional: boolean }
export interface Edit { key: string; provider_index: number | null; value: string }
export interface AddressReport { target: string; status: string; reason: string; source: string; confidence: string; changes: Record<string, {original: string; suggested: string}>; applied_automatically?: boolean }
export interface Validation { status: 'Passed' | 'Failed'; missing_fields: string[]; provider_missing_fields: string[][]; confirmation_required: string[]; appointments: {provider_index: number; appointment_date: string; reasons: string[]; can_confirm: boolean; confirmed: boolean}[] }
export interface DocumentDetail extends DocumentRow { groups: {name: string; fields: Field[]}[]; is_pdf: boolean; text: string; raw: string; record_id: string | null; validation: Validation | null; address_report: AddressReport[]; name_inference: Record<string, unknown>[]; address_review: AddressReport[]; edits: {key: string; provider_index: number | null; before: string; after: string; at: string}[]; sent_characters: number; total_characters: number }
export interface API {
  get_state(): Promise<State>
  choose_documents(): Promise<string[]>
  get_document(id: string): Promise<DocumentDetail>
  render_page(id: string, page: number, scale: number): Promise<string>
  save_settings(settings: Settings, key: string): Promise<boolean>
  test_connection(): Promise<boolean>
  start_processing(ids: string[]): Promise<boolean>
  save_fields(id: string, edits: Edit[], revision: number): Promise<boolean>
  confirm_appointment(id: string, index: number): Promise<boolean>
  retry_save(id: string): Promise<string>
  export_document(id: string, kind: string): Promise<string | null>
  open_output(): Promise<boolean>
}
