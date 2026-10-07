export interface StageOption {
  label: string
  key: string
}

export interface InputField {
  key: string
  label: string
}

export interface SampleData {
  username: string
  password: string
  claimNumber: string
  customer: string
  claimID: string
  claimantFull: string
  referralType: string
}

export interface Config {
  stages: StageOption[]
  inputs: InputField[]
  scenarios: string[]
  defaultUsername: string
  sampleData: SampleData | null
}

export interface BrowseExcelResult {
  path?: string
  records?: string[]
  error?: string
}

export interface Assessment {
  status: string
  [key: string]: unknown
}

export interface LoadRecordResult {
  data?: Record<string, string>
  assessment?: Assessment
  error?: string
}

export interface StartRequest {
  mode: "offline" | "live"
  stage: string
  scenario: string
  input?: Record<string, string>
  excel?: string
  record_id?: string
  username?: string
  password?: string
}

export interface PendingPrompt {
  kind: "yes_no" | "text" | "notify"
  title: string
  message: string
}

export interface StatusResult {
  running: boolean
  status: string
  pendingPrompt: PendingPrompt | null
  result: Record<string, unknown> | null
}

export interface StartResult {
  ok?: boolean
  error?: string
}
