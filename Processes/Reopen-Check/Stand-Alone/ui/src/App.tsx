import { useEffect, useRef, useState } from "react"
import { FileSpreadsheet, FolderOpen, Play, RotateCcw, Save, PencilLine, Loader2, FlaskConical } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { PromptModal } from "@/components/PromptModal"
import { backend, whenReady } from "@/lib/backend"
import type { Config, PendingPrompt } from "@/types"

type Mode = "offline" | "live"

export default function App() {
  const [ready, setReady] = useState(false)
  const [config, setConfig] = useState<Config | null>(null)

  const [mode, setMode] = useState<Mode>("offline")
  const [stageKey, setStageKey] = useState("")
  const [scenario, setScenario] = useState("")

  const [excelPath, setExcelPath] = useState("")
  const [records, setRecords] = useState<string[]>([])
  const [recordId, setRecordId] = useState("")
  const [assessment, setAssessment] = useState(
    "No workbook selected. Manual input is available for live runs."
  )
  const [manualMode, setManualMode] = useState(true)

  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")

  const [running, setRunning] = useState(false)
  const [status, setStatus] = useState("Ready \u2014 choose offline testing or configure live CMS.")
  const [pendingPrompt, setPendingPrompt] = useState<PendingPrompt | null>(null)
  const [result, setResult] = useState<unknown>(null)
  const [formError, setFormError] = useState("")

  const pollTimer = useRef<number | null>(null)

  useEffect(() => {
    whenReady().then(async () => {
      const cfg = await backend.getConfig()
      setConfig(cfg)
      setStageKey(cfg.stages[0]?.key ?? "")
      setScenario(cfg.scenarios[0] ?? "")
      setUsername(cfg.defaultUsername ?? "")
      setReady(true)
    })
  }, [])

  useEffect(() => {
    if (!running) return
    let cancelled = false
    const poll = async () => {
      const current = await backend.pollStatus()
      if (cancelled) return
      setStatus(current.status)
      setPendingPrompt(current.pendingPrompt)
      if (!current.running) {
        setRunning(false)
        setResult(current.result)
        return
      }
      pollTimer.current = window.setTimeout(poll, 400)
    }
    poll()
    return () => {
      cancelled = true
      if (pollTimer.current) window.clearTimeout(pollTimer.current)
    }
  }, [running])

  async function handleBrowseExcel() {
    const outcome = await backend.browseExcel()
    if (!outcome) return
    if (outcome.error) {
      setAssessment("Cannot load workbook: " + outcome.error)
      return
    }
    setExcelPath(outcome.path ?? "")
    setRecords(outcome.records ?? [])
    const first = outcome.records?.[0] ?? ""
    setRecordId(first)
    setManualMode(false)
    if (first) await handleLoadRecord(outcome.path ?? "", first)
  }

  async function handleLoadRecord(path = excelPath, id = recordId) {
    if (!path || !id) {
      setAssessment("Select a workbook containing a Referrals record.")
      return
    }
    const outcome = await backend.loadRecord(path, id)
    if (outcome.error) {
      setAssessment("Workbook record could not be loaded: " + outcome.error)
      return
    }
    setInputs(outcome.data ?? {})
    setAssessment(
      "NEXT STEP: " + (outcome.assessment?.status ?? "Unknown") +
        " \u2014 Excel input is read-only; live runs recheck the file."
    )
  }

  function handleManualInput() {
    setExcelPath("")
    setRecords([])
    setRecordId("")
    setManualMode(true)
    setInputs({})
    setResult(null)
    setAssessment("Manual input selected. Required fields depend on the selected stage.")
  }

  function handleLoadSampleData() {
    if (!config?.sampleData) return
    const { username: sampleUser, password: samplePassword, ...fields } = config.sampleData
    handleManualInput()
    setInputs(fields)
    setUsername(sampleUser)
    setPassword(samplePassword)
    setAssessment("Sample test data loaded. Required fields depend on the selected stage.")
  }

  async function handleRun() {
    if (!config) return
    setFormError("")
    const request: Record<string, unknown> = { mode, stage: stageKey, scenario }
    if (mode === "live") {
      Object.assign(request, { input: inputs, username, password })
      if (excelPath) Object.assign(request, { excel: excelPath, record_id: recordId })
    }
    const outcome = await backend.start(request as never)
    if (outcome.error) {
      setFormError(outcome.error)
      return
    }
    setResult(null)
    setRunning(true)
  }

  async function handleSave() {
    const outcome = await backend.saveResult("CMSCustomerSearch-result.json")
    if (outcome.error) setFormError(outcome.error)
  }

  async function handlePromptAnswer(value: unknown) {
    await backend.answerPrompt(value)
    setPendingPrompt(null)
  }

  if (!ready || !config) {
    return (
      <div className="flex h-full items-center justify-center text-(--color-ink-muted)">
        <Loader2 className="mr-2 size-4 animate-spin" /> Loading CMSCustomerSearch...
      </div>
    )
  }

  return (
    <div className="mx-auto flex h-full max-w-5xl flex-col gap-4 p-5">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">CMSCustomerSearch</h1>
        <p className="text-sm text-(--color-ink-muted)">
          Test re-open checking and customer validation independently of the intake bot.
        </p>
      </header>

      <Card>
        <CardContent className="flex flex-wrap items-end gap-4 pt-3">
          <Field label="Mode">
            <Select value={mode} onValueChange={(v) => setMode(v as Mode)}>
              <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="offline">Offline scenario</SelectItem>
                <SelectItem value="live">Live CMS</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label="Stage">
            <Select value={stageKey} onValueChange={setStageKey}>
              <SelectTrigger className="w-64"><SelectValue /></SelectTrigger>
              <SelectContent>
                {config.stages.map((s) => <SelectItem key={s.key} value={s.key}>{s.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
          {mode === "offline" && (
            <Field label="Scenario">
              <Select value={scenario} onValueChange={setScenario}>
                <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {config.scenarios.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
            </Field>
          )}
          <p className="w-full text-xs text-(--color-ink-muted)">
            Offline mode uses synthetic scenario inputs. Live mode uses the Excel record or manual fields below.
          </p>
        </CardContent>
      </Card>

      {mode === "live" && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><FileSpreadsheet className="size-4" /> Daily Excel input</CardTitle>
              <CardDescription>{excelPath || "No workbook selected."}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap items-center gap-2">
              <Button variant="secondary" onClick={handleBrowseExcel}>
                <FolderOpen /> Choose daily Excel
              </Button>
              {records.length > 0 && (
                <Select value={recordId} onValueChange={(v) => { setRecordId(v); handleLoadRecord(excelPath, v) }}>
                  <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {records.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                  </SelectContent>
                </Select>
              )}
              <Button variant="outline" onClick={() => handleLoadRecord()} disabled={!excelPath}>
                <RotateCcw /> Reload record
              </Button>
              <Button variant="outline" onClick={handleManualInput}>
                <PencilLine /> Use manual input
              </Button>
              {config.sampleData && (
                <Button variant="outline" onClick={handleLoadSampleData}>
                  <FlaskConical /> Load sample data
                </Button>
              )}
              <p className="w-full text-xs text-(--color-ink-muted)">{assessment}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Process input</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              {config.inputs.map(({ key, label }) => (
                <div key={key} className="flex flex-col gap-1">
                  <Label htmlFor={key}>{label}</Label>
                  <Input
                    id={key}
                    value={inputs[key] ?? ""}
                    readOnly={!manualMode}
                    onChange={(e) => setInputs((prev) => ({ ...prev, [key]: e.target.value }))}
                  />
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="flex flex-wrap gap-4 pt-3">
              <div className="flex flex-col gap-1">
                <Label htmlFor="cms-username">CMS username</Label>
                <Input id="cms-username" value={username} onChange={(e) => setUsername(e.target.value)} className="w-56" />
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor="cms-password">Password</Label>
                <Input id="cms-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-56" />
              </div>
            </CardContent>
          </Card>
        </>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={handleRun} disabled={running}>
          {running ? <Loader2 className="animate-spin" /> : <Play />} Run selected process
        </Button>
        <Button variant="secondary" onClick={handleSave} disabled={!result}>
          <Save /> Save result JSON
        </Button>
      </div>

      {formError && <p className="text-sm text-(--color-danger)">{formError}</p>}
      <p className="text-sm text-(--color-ink-muted)">{status}</p>

      <Card className="flex min-h-0 flex-1 flex-col">
        <CardHeader><CardTitle>Output</CardTitle></CardHeader>
        <ScrollArea className="min-h-0 flex-1 border-t border-(--color-border)">
          <pre className="whitespace-pre-wrap p-4 font-(family-name:--font-mono) text-xs leading-relaxed text-(--color-ink)">
            {result ? JSON.stringify(result, null, 2) : "(no result yet)"}
          </pre>
        </ScrollArea>
      </Card>

      <PromptModal prompt={pendingPrompt} onAnswer={handlePromptAnswer} />
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <Label>{label}</Label>
      {children}
    </div>
  )
}
