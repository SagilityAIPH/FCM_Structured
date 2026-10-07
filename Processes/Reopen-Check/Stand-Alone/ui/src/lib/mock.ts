import type { BrowseExcelResult, Config, LoadRecordResult, StartRequest, StartResult, StatusResult } from "@/types"

/** In-browser stand-in for window.pywebview.api, used only in `npm run dev`
 * so the UI can be iterated on without launching the Python/WebView2 host. */
export function createMockApi() {
  let running = false
  let result: StatusResult["result"] = null
  let status = "Ready (mock) \u2014 choose offline testing or configure live CMS."

  return {
    async get_config(): Promise<Config> {
      return {
        stages: [
          { label: "Both: re-open + customer", key: "all" },
          { label: "Re-open only", key: "reopen" },
          { label: "Customer only", key: "customer" },
        ],
        inputs: [
          { key: "claimNumber", label: "Claim Number" },
          { key: "customer", label: "Customer Name" },
          { key: "claimID", label: "Claim ID" },
          { key: "claimantFull", label: "Claimant Full Name" },
          { key: "referralType", label: "Referral Type" },
        ],
        scenarios: ["happy-path.json", "decline.json"],
        defaultUsername: "",
        sampleData: {
          username: "cconcepcion",
          password: "Spider@1",
          claimNumber: "WC413M15192",
          customer: "PAVESTONE LLC",
          claimID: "952200227",
          claimantFull: "ENGELEN,GARAN",
          referralType: "Full Case Management",
        },
      }
    },
    async browse_excel(): Promise<BrowseExcelResult | null> {
      return { path: "C:/fake/daily-output.xlsx", records: ["REC-001", "REC-002"] }
    },
    async load_record(): Promise<LoadRecordResult> {
      return {
        data: { claimNumber: "DEMO", customer: "Example Co", claimID: "ID1", claimantFull: "Jane Doe", referralType: "Full Case Management" },
        assessment: { status: "Passed" },
      }
    },
    async start(request: StartRequest): Promise<StartResult> {
      running = true
      result = null
      status = `Running ${request.mode} process (mock)...`
      setTimeout(() => {
        running = false
        result = { result: { status: "completed" }, mode: request.mode }
        status = "Process completed."
      }, 1500)
      return { ok: true }
    },
    async poll_status(): Promise<StatusResult> {
      return { running, status, pendingPrompt: null, result }
    },
    async answer_prompt(): Promise<{ ok: boolean }> {
      return { ok: true }
    },
    async save_result(): Promise<{ ok?: boolean; error?: string; path?: string }> {
      return { ok: true, path: "C:/fake/CMSCustomerSearch-result.json" }
    },
  }
}
