export type Status = 'Ready' | 'Queued' | 'Processing' | 'Completed' | 'Needs Review' | 'Failed'
export interface Settings { region: string; model: string; max_tokens: number; temperature: number; document_limit: number }
export interface DocumentRow { referral_notice?: string; id: string; name: string; status: Status; pages: number; revision: number; error: string; elapsed: number; workbook: string; save_error: string; claimant: string; claim: string; next_step: 'Passed' | 'Failed' | null; issues: number }
export type Outcome = 'completed' | 'ended' | 'stopped' | 'failed'
export interface CemHandoff { employer_name: string; claim_number: string; claim_id: string; claimant_full: string }
export interface WorkflowResult { outcome: Outcome; reason: string | null; customer: string | null; cases: {cms_caseNum?: string; caseType?: string; case_status?: string; message?: string}[]; missing_fields: string[]; confirmation_required?: string[]; stages: string[]; payloads: Record<string, unknown>; error?: {stage: string; type: string; message: string}; instruction?: string; cem_handoff?: CemHandoff }
export interface PendingPrompt { id: string; kind: 'notify' | 'confirm' | 'credentials'; title: string; message: string }
export interface PendingReview { id: string; document_id: string }
export interface State { referral_notice?: string; workflow_result?: WorkflowResult | null; pending_prompt?: PendingPrompt | null; pending_review: PendingReview | null; documents: DocumentRow[]; busy: boolean; compact: boolean; memory_only: boolean; workflow_active?: boolean; stage: string; bedrock: string; elapsed: number; progress: { done: number; total: number }; settings: Settings; remembered_model_needs_test: boolean; key_configured: boolean; key_remembered: boolean; cms_remembered: boolean; output_directory: string }
export type ClassificationSource = 'AI' | 'Rules' | 'Manual' | 'None'
export interface Field { key: string; label: string; value: string; display_value?: string | null; provider_index: number | null; confidence: number | null; manual: boolean; optional: boolean; conditional: boolean; source?: ClassificationSource | null }
export interface Classification { field: string; value: string; source: ClassificationSource; ai_value: string; rule_value: string; review: string; list: 'RRS' | 'provisional' }
export interface ReviewFlag { field: string; provider_index: number | null; kind: 'format' | 'disagreement'; reason: string; reader_value?: string }
export interface Edit { key: string; provider_index: number | null; value: string }
export interface AddressReport { target: string; status: string; reason: string; source: string; confidence: string; changes: Record<string, {original: string; suggested: string}>; applied_automatically?: boolean }
export interface Validation { status: 'Passed' | 'Failed'; missing_fields: string[]; provider_missing_fields: string[][]; confirmation_required: string[]; appointments: {provider_index: number; appointment_date: string; reasons: string[]; can_confirm: boolean; confirmed: boolean}[] }
export interface DocumentDetail extends DocumentRow { groups: {name: string; fields: Field[]}[]; preview_message?: string | null; is_pdf: boolean; text: string; raw: string; record_id: string | null; validation: Validation | null; address_report: AddressReport[]; name_inference: Record<string, unknown>[]; address_review: AddressReport[]; classification: Classification[]; review_flags?: ReviewFlag[]; edits: {key: string; provider_index: number | null; before: string; after: string; at: string}[]; sent_characters: number; total_characters: number }
export interface API {
  get_state(): Promise<State>
  start_attended(): Promise<boolean>
  answer_prompt(id: string, answer: boolean | {username: string; password: string; remember: boolean} | null): Promise<boolean>
  forget_credential(name: 'bedrock' | 'cms'): Promise<boolean>
  answer_review(id: string, approve: boolean): Promise<boolean>
  set_workflow_result(result: WorkflowResult | null): Promise<boolean>
  set_compact(value: boolean): Promise<boolean>
  set_stage(stage: string, done?: number, total?: number): Promise<boolean>
  choose_documents(): Promise<string[]>
  get_document(id: string): Promise<DocumentDetail>
  import_text(name: string, text: string): Promise<string>
  render_page(id: string, page: number, scale: number): Promise<string | {available: false; message: string}>
  save_settings(settings: Settings, key: string, remember?: boolean): Promise<boolean>
  test_connection(): Promise<boolean>
  start_processing(ids: string[]): Promise<boolean>
  save_fields(id: string, edits: Edit[], revision: number): Promise<boolean>
  confirm_appointment(id: string, index: number): Promise<boolean>
  retry_save(id: string): Promise<string>
  export_document(id: string, kind: string): Promise<string | null>
  set_unsaved(value: boolean): Promise<boolean>
  open_output(): Promise<boolean>
}
