import type {
  BrowseExcelResult,
  Config,
  LoadRecordResult,
  StartRequest,
  StartResult,
  StatusResult,
} from "@/types"

declare global {
  interface Window {
    pywebview?: {
      api: {
        get_config(): Promise<Config>
        browse_excel(): Promise<BrowseExcelResult | null>
        load_record(path: string, recordId: string): Promise<LoadRecordResult>
        start(request: StartRequest): Promise<StartResult>
        poll_status(): Promise<StatusResult>
        answer_prompt(value: unknown): Promise<{ ok: boolean }>
        save_result(suggestedName?: string): Promise<{ ok?: boolean; error?: string; path?: string }>
      }
    }
  }
}

let mockApiPromise: Promise<ReturnType<typeof import("@/lib/mock").createMockApi>> | null = null

async function api() {
  if (window.pywebview) return window.pywebview.api
  if (import.meta.env.DEV) {
    if (!mockApiPromise) {
      mockApiPromise = import("@/lib/mock").then((m) => m.createMockApi())
    }
    return mockApiPromise
  }
  throw new Error(
    "window.pywebview is not available. Run this UI inside the CMSCustomerSearch desktop app."
  )
}

/** Waits for pywebview's injected API (it arrives slightly after page load). */
export function whenReady(): Promise<void> {
  if (window.pywebview || import.meta.env.DEV) return Promise.resolve()
  return new Promise((resolve) => {
    window.addEventListener("pywebviewready", () => resolve(), { once: true })
  })
}

export const backend = {
  getConfig: async () => (await api()).get_config(),
  browseExcel: async () => (await api()).browse_excel(),
  loadRecord: async (path: string, recordId: string) => (await api()).load_record(path, recordId),
  start: async (request: StartRequest) => (await api()).start(request),
  pollStatus: async () => (await api()).poll_status(),
  answerPrompt: async (value: unknown) => (await api()).answer_prompt(value),
  saveResult: async (suggestedName?: string) => (await api()).save_result(suggestedName),
}
