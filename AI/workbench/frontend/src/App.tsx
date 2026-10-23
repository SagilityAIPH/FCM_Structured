import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ArrowDownToLine, CheckCheck, CircleAlert, FileCheck2, Files, FileSpreadsheet, FileText, FolderOpen, LoaderCircle, Minimize2, Maximize2, Plus, RotateCcw, Save, Settings2, X } from 'lucide-react'
import { Button } from './components/ui/button'
import { Input } from './components/ui/input'
import { StatusBadge } from './components/StatusBadge'
import PdfPreview from './components/PdfPreview'
import FieldForm from './components/FieldForm'
import SettingsForm from './components/SettingsForm'
import { getAPI, previewMode } from './lib/bridge'
import { cn } from './lib/utils'
import type { API, DocumentDetail, Edit, State } from './types'

type Panel = 'Documents' | 'PDF' | 'Output' | 'Settings'
const navigation = [{name: 'Documents', icon: Files}, {name: 'PDF', icon: FileText}, {name: 'Output', icon: FileSpreadsheet}, {name: 'Settings', icon: Settings2}] as const

import { CmsSection } from '@/components/CmsSection'

export default function App() {
  const [state, setState] = useState<State | null>(null)
  const [selected, setSelected] = useState('')
  const [detail, setDetail] = useState<DocumentDetail | null>(null)
  const [panels, setPanels] = useState<Panel[]>([])
  const [visible, setVisible] = useState<Panel[]>([])
  const [scrollTarget, setScrollTarget] = useState<Panel | 'Fields' | null>(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('All statuses')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [reviewSubmitting, setReviewSubmitting] = useState(false)
  const [reviewError, setReviewError] = useState('')
  const [promptUsername, setPromptUsername] = useState('')
  const [promptPassword, setPromptPassword] = useState('')
  const [promptRemember, setPromptRemember] = useState(false)
  const [promptSending, setPromptSending] = useState(false)
  const [promptError, setPromptError] = useState('')
  const reviewAnswered = useRef<string | null>(null)
  const [draft, setDraft] = useState<Record<string, Edit>>({})
  const [settingsDirty, setSettingsDirty] = useState(false)
  const formRef = useRef<HTMLElement>(null)
  const normalScroll = useRef(0)
  const wasCompact = useRef(false)
  const compact = !!state?.compact
  useLayoutEffect(() => {
    if (!compact && wasCompact.current && formRef.current) formRef.current.scrollTop = normalScroll.current
    wasCompact.current = compact
  }, [compact])
  const edits = Object.values(draft)
  const dirty = edits.length > 0
  useEffect(() => {
    document.documentElement.dataset.unsaved = String(dirty || settingsDirty)
    getAPI().then(api => api.set_unsaved(dirty || settingsDirty)).catch(() => {})
  }, [dirty, settingsDirty])
  const mounted = useRef(true)
  const busy = pending || !!state?.busy
  const refresh = useCallback(async () => {
    const api = await getAPI()
    const next = await api.get_state()
    // Defensive fallback for a prompt published while a compact resize was in flight.
    if (next.pending_prompt && next.compact) {
      await api.set_compact(false)
      next.compact = false
    }
    if (next.memory_only && next.pending_review && next.compact) {
      await api.set_compact(false)
      next.compact = false
    }
    if (mounted.current) {
      setState(next)
      setSelected(value => (next.memory_only && next.pending_review?.document_id) || value || next.documents[0]?.id || '')
    }
  }, [])
  useEffect(() => {
    mounted.current = true
    let timer: ReturnType<typeof setTimeout>
    const tick = async () => {
      try { await refresh() } catch (err) { if (mounted.current) setError((err as Error).message) }
      if (mounted.current) timer = setTimeout(tick, 1200)
    }
    void tick()
    return () => { mounted.current = false; clearTimeout(timer) }
  }, [refresh])
  const review = state?.memory_only ? state.pending_review : null
  const prompt = state?.pending_prompt
  const blocking = state?.memory_only && state.workflow_result && ['stopped', 'ended', 'failed'].includes(state.workflow_result.outcome)
  const attention = !!prompt || !!review || !!blocking || (!!state?.memory_only && !state.workflow_active && !state.workflow_result)
  useEffect(() => {
    setPromptUsername(''); setPromptPassword(''); setPromptRemember(false); setPromptError('')
  }, [prompt?.id])
  const answerPrompt = async (id: string, value: boolean | {username: string; password: string; remember: boolean} | null) => {
    if (promptSending || prompt?.id !== id) return
    setPromptSending(true); setPromptError('')
    try {
      await (await getAPI()).answer_prompt(id, value)
      setPromptUsername(''); setPromptPassword('')
      await refresh()
    } catch {
      // Do not render arbitrary bridge exception text: it may include entered credentials.
      setPromptError('Could not send the answer. Check the fields and try again.')
    } finally { setPromptSending(false) }
  }
  const row = state?.documents.find(d => d.id === selected)
  useEffect(() => {
    if (review?.id !== reviewAnswered.current) setReviewError('')
  }, [review?.id])
  useEffect(() => {
    let active = true
    if (!selected) { setDetail(null); return }
    void getAPI().then(api => api.get_document(selected)).then(doc => {
      if (active) { setDetail(doc); setDraft({}) }
    }).catch(err => { if (active) setError((err as Error).message) })
    return () => { active = false }
  }, [selected, row?.revision, row?.status])
  useEffect(() => {
    if (!scrollTarget) return
    const frame = requestAnimationFrame(() => {
      document.getElementById(`group-${scrollTarget}`)?.scrollIntoView({block: 'start'})
      setScrollTarget(null)
    })
    return () => cancelAnimationFrame(frame)
  }, [scrollTarget, visible])
  const act = async (work: (api: API) => Promise<unknown>, success = '') => {
    setPending(true); setError(''); setNotice('')
    try { await work(await getAPI()); await refresh(); setNotice(success); return true }
    catch (err) { setError((err as Error).message); return false }
    finally { setPending(false) }
  }
  const answerReview = async (id: string, approve: boolean) => {
    if (reviewSubmitting || reviewAnswered.current === id || !state?.memory_only || state.pending_review?.id !== id) return
    if (approve && (dirty || settingsDirty)) { setReviewError('Save field changes before approving.'); return }
    if (approve && (busy || !detail || detail.id !== state.pending_review.document_id)) return
    reviewAnswered.current = id
    setReviewSubmitting(true); setReviewError('')
    let answered = false
    try {
      const api = await getAPI()
      if (approve) await api.set_unsaved(false)
      await api.answer_review(id, approve)
      answered = true
      await refresh()
    } catch (err) {
      if (!answered) reviewAnswered.current = null
      const message = (err as Error).message
      setReviewError(message.includes('Save field changes before approving') ? 'Save field changes before approving.' : message)
    } finally { setReviewSubmitting(false) }
  }
  const leave = () => !dirty || window.confirm('Discard unsaved field edits?')
  const choose = (id: string) => {
    if (id !== selected && leave()) { setDetail(null); setSelected(id); setDraft({}); setScrollTarget('Fields') }
  }
  const show = (panel: Panel) => {
    setPanels(current => current.includes(panel) ? current : [...current, panel])
    setVisible(current => current.includes(panel) ? current : [...current, panel])
    setScrollTarget(panel)
  }
  const toggle = (panel: Panel) => {
    if (visible.includes(panel)) setVisible(current => current.filter(item => item !== panel))
    else show(panel)
  }
  const documents = state?.documents || []
  const filtered = documents.filter(d => (filter === 'All statuses' || d.status === filter) && `${d.name} ${d.claim} ${d.claimant}`.toLowerCase().includes(query.toLowerCase()))
  const shownDetail = detail?.id === selected ? detail : null
  const progress = state?.progress || {done: 0, total: 0}
  const indeterminate = (busy || !!state?.workflow_active) && (progress.total === 0 || progress.done === progress.total || !!state?.stage.startsWith('Checking missing addresses'))
  return <div className={cn("compact-shell", compact && "is-compact")}>
    <header className="app-header"><div className="title-row"><span className="app-icon"><FileText size={19} /></span><div><h1>{state?.memory_only ? 'Referral Intake' : 'AI PDF Reader'}</h1><p>{state?.memory_only ? 'Captured from RRS' : 'Referral intake form'}</p></div>{state?.memory_only ? <><Button size="sm" disabled={!state || busy || !!state.workflow_active} onClick={() => void act(api => api.start_attended())}>Start</Button>{attention && <span className="start-attention" role="status" aria-label="Operator action required"><CircleAlert size={17} aria-hidden="true" /></span>}</> : <Button size="sm" disabled={busy || !state} onClick={() => {
      if (leave()) void act(async api => {
        const ids = await api.choose_documents()
        if (ids[0]) {
          if (ids[0] !== selected) { setDetail(null); setSelected(ids[0]) }
          setDraft({}); setScrollTarget('Fields')
        }
      })
    }}><Plus />{previewMode ? 'Load examples' : 'Open'}</Button>}<Button variant="ghost" size="icon" disabled={!state} aria-label={compact ? 'Exit compact mode' : 'Enter compact mode'} aria-pressed={compact} onClick={() => {
      if (!compact && formRef.current) normalScroll.current = formRef.current.scrollTop
      void act(api => api.set_compact(!compact))
    }}>{compact ? <Maximize2 /> : <Minimize2 />}</Button></div>
      {documents.length ? <div className="document-selector"><select aria-label="Current document" value={selected} onChange={e => choose(e.target.value)}>{documents.map(doc => <option key={doc.id} value={doc.id}>{doc.name}</option>)}</select>{row ? <StatusBadge status={row.status} /> : null}</div> : null}
      {previewMode ? <div className="preview-label">Synthetic preview · no Bedrock calls</div> : null}
    </header>
    {attention && <section className="urgent-banner" role="status" aria-live="polite" aria-label="Action required">
      <span className="attention-marker" aria-hidden="true" /><strong>Action required</strong>
      {prompt ? <>
        <div className="urgent-copy"><b>{prompt.title}</b><p>{prompt.message}</p></div>
        {prompt.kind === 'credentials' ? <form className="urgent-credentials" autoComplete="off" onSubmit={e => { e.preventDefault(); void answerPrompt(prompt.id, {username: promptUsername, password: promptPassword, remember: promptRemember}) }}>
          <label>CMS username<Input autoComplete="off" value={promptUsername} onChange={e => setPromptUsername(e.target.value)} /></label>
          <label>CMS password<Input type="password" autoComplete="new-password" value={promptPassword} onChange={e => setPromptPassword(e.target.value)} /></label>
          <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={promptRemember} disabled={promptSending} onChange={e => setPromptRemember(e.target.checked)} />Remember on this computer (CMS)</label>
          <div className="urgent-actions"><Button type="submit" size="sm" disabled={promptSending || !promptUsername.trim() || !promptPassword}>Continue to CMS</Button><Button type="button" size="sm" variant="outline" disabled={promptSending} onClick={() => void answerPrompt(prompt.id, null)}>Cancel run</Button></div>
        </form> : <div className="urgent-actions">{prompt.kind === 'confirm' ? <><Button size="sm" variant="outline" disabled={promptSending} onClick={() => void answerPrompt(prompt.id, false)}>No</Button><Button size="sm" disabled={promptSending} onClick={() => void answerPrompt(prompt.id, true)}>Yes</Button></> : <Button size="sm" disabled={promptSending} onClick={() => void answerPrompt(prompt.id, true)}>Acknowledge</Button>}</div>}
        {promptError && <p className="review-hint" role="alert">{promptError}</p>}
      </> : review ? <>
        <p>Review the extracted fields below. Save edits before approving, or cancel this run.</p>
        <div className="urgent-actions" role="group" aria-label="Attended review actions"><Button size="sm" disabled={busy || reviewSubmitting || reviewAnswered.current === review.id || dirty || settingsDirty || !shownDetail || shownDetail.id !== review.document_id} onClick={() => void answerReview(review.id, true)}><CheckCheck />Approve and continue</Button><Button size="sm" variant="outline" disabled={reviewSubmitting || reviewAnswered.current === review.id} onClick={() => void answerReview(review.id, false)}>Cancel run</Button>
        {(dirty || settingsDirty || reviewError) && <p className="review-hint" role={reviewError ? 'alert' : undefined}>{reviewError || 'Save field changes before approving.'}</p>}
        </div>
      </> : blocking ? <p>Run {state.workflow_result?.outcome}. Review the CMS result below and take the indicated manual action before starting again.</p> : <p>Select Start to capture from RRS.</p>}
    </section>}
    <main ref={formRef} className="form-scroll" aria-label="Referral form" hidden={compact} onScroll={e => { if (!compact) normalScroll.current = e.currentTarget.scrollTop }}>
      <div id="group-Fields" className="scroll-anchor" />
      {error ? <div className="message error" role="alert"><CircleAlert size={15} /><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}><X size={14} /></button></div> : null}
      {notice ? <div className="message success" role="status"><CheckCheck size={15} /><span>{notice}</span><button aria-label="Dismiss message" onClick={() => setNotice('')}><X size={14} /></button></div> : null}
      {!state?.key_configured && state ? <div className="setup-banner"><span>Configure Bedrock to start automatic extraction.</span><button onClick={() => show('Settings')}>Open settings</button></div> : null}
      {state?.memory_only && !state.workflow_active && !state.workflow_result ? <div className="setup-banner" role="status">Waiting for Start. Select Start when ready to capture from RRS.</div> : null}
      {state?.memory_only && state.cms_remembered && <div className="setup-banner"><span>CMS sign-in remembered for this Windows account.</span><button disabled={busy} onClick={() => void act(api => api.forget_credential('cms'), 'Saved CMS sign-in forgotten.')}>Forget saved CMS sign-in</button></div>}
      <CmsSection result={state?.workflow_result} />
      <FieldForm key={`${shownDetail?.id}-${shownDetail?.revision}-${state?.memory_only}`} doc={shownDetail} memoryOnly={!!state?.memory_only} busy={busy} draft={draft} onDraft={setDraft}
              onConfirm={index => { if (window.confirm(`Confirm that Provider ${index}'s appointment is correct despite the displayed warnings?`)) void act(api => api.confirm_appointment(selected, index), state?.memory_only ? 'Appointment confirmed for this run.' : 'Appointment confirmed and Excel updated.') }}
        onRetrySave={() => void act(api => api.retry_save(selected), 'Daily Excel saved.')} />
      {panels.map(panel => <section id={`group-${panel}`} key={panel} className="extra-group" hidden={!visible.includes(panel)} aria-label={`${panel} group`}>
        <div className="group-heading"><h2>{panel === 'PDF' ? 'Document preview' : panel}</h2><Button variant="ghost" size="icon" aria-label={`Hide ${panel}`} onClick={() => toggle(panel)}><X /></Button></div>
        {panel === 'Settings' && state ? <SettingsForm settings={state.settings} configured={state.key_configured} remembered={state.key_remembered} needsModelTest={state.remembered_model_needs_test} busy={busy} onDirty={setSettingsDirty}
          onSave={(settings, key, remember) => act(api => api.save_settings(settings, key, remember), 'Settings saved. Ready documents start automatically.')} onForget={() => act(api => api.forget_credential('bedrock'), 'Saved Bedrock key and model forgotten.')} onTest={() => void act(api => api.test_connection())} /> : null}
        {panel === 'PDF' ? <PdfPreview doc={shownDetail} /> : null}
        {panel === 'Documents' ? <div className="group-content"><div className="document-filters"><Input aria-label="Search documents" placeholder="Search documents or claims…" value={query} onChange={e => setQuery(e.target.value)} /><select aria-label="Filter document status" value={filter} onChange={e => setFilter(e.target.value)}>{['All statuses', 'Ready', 'Queued', 'Processing', 'Completed', 'Needs Review', 'Failed'].map(value => <option key={value}>{value}</option>)}</select></div>
          <div className="document-list">{filtered.map(doc => <div className={cn('document-item', selected === doc.id && 'selected')} key={doc.id}>
            <button className="document-name" onClick={() => choose(doc.id)} aria-pressed={selected === doc.id}><FileText size={16} /><span><strong>{doc.name}</strong><small>{doc.claimant} · {doc.claim}</small><small>{doc.pages} pages{state?.memory_only ? '' : doc.save_error ? ' · Excel save needs attention' : doc.workbook ? ' · Saved to daily Excel' : ''}</small></span></button>
            <div className="document-actions"><StatusBadge status={doc.status} />{!state?.memory_only && ['Failed', 'Completed', 'Needs Review'].includes(doc.status) ? <Button variant="ghost" size="icon" disabled={busy} aria-label={`Retry extraction for ${doc.name}`} onClick={() => {
              if ((doc.id !== selected || leave()) && window.confirm('Run extraction again? This creates a new daily Excel record.')) void act(api => api.start_processing([doc.id]))
            }}><RotateCcw /></Button> : null}</div>
          </div>)}</div>{!filtered.length ? <p className="empty-text">{documents.length ? 'No matching documents.' : state?.memory_only ? 'Waiting for the referral capture from RRS.' : 'Open a PDF, DOCX, or TXT document to begin.'}</p> : null}</div> : null}
        {panel === 'Output' ? <div className="group-content">{state?.memory_only ? <p className="output-path">Referral JSON is saved automatically. Daily Excel output is disabled for Final Code.</p> : <><p className="output-path">{state?.output_directory}</p><Button variant="outline" size="sm" disabled={busy} onClick={() => void act(api => api.open_output())}><FolderOpen />Open output folder</Button></>}
          <p className="output-help">{state?.memory_only ? 'Extraction, saved changes, approval checks and run outcomes are saved to a referral JSON file.' : 'Every extraction is saved to a referral JSON file and the daily workbook, including Passed and Failed results.'}</p>
          {shownDetail?.groups.length ? <><p className="output-file">{shownDetail.name}</p><div className="export-actions">{['json', 'csv', 'txt'].map(kind => <Button key={kind} variant="outline" size="sm" disabled={busy || dirty} onClick={() => void act(api => api.export_document(selected, kind))}><ArrowDownToLine />{kind.toUpperCase()}</Button>)}</div>
          {shownDetail.save_error && !state?.memory_only ? <div className="note warning"><p>{shownDetail.save_error}</p><Button variant="outline" size="sm" disabled={busy} onClick={() => void act(api => api.retry_save(selected), 'Daily Excel saved.')}>Retry Excel save</Button></div> : null}</> : <p className="empty-text">Extracted output will be available here.</p>}</div> : null}
      </section>)}
    </main>
    <footer className="bottom-dock">
      <div className="save-row"><Button size="sm" disabled={busy || !dirty || !shownDetail} onClick={() => void act(api => api.save_fields(selected, edits, shownDetail!.revision), 'Changes saved. Address checks and validation run automatically.')}><Save />Save field changes{dirty ? ` (${edits.length})` : ''}</Button><span>{dirty ? 'Unsaved edits' : state?.memory_only ? shownDetail ? 'Review fields before approving' : 'Awaiting RRS capture' : shownDetail?.save_error ? 'Excel save failed' : shownDetail?.workbook ? 'Saved to daily Excel' : 'Awaiting extraction'}</span></div>
      <div className="processing-status" role="status"><span title={state?.stage}>{busy ? <LoaderCircle size={12} className="animate-spin" /> : null}{state?.stage || 'Connecting to desktop…'}</span><small>{progress.total ? `${progress.done}/${progress.total} complete · ` : ''}{state?.elapsed.toFixed(1) || '0.0'}s</small></div>
      {(state?.memory_only || !row ? state?.referral_notice : row.referral_notice) ? <div className="processing-status" role="status" aria-live="polite"><span title={state?.memory_only || !row ? state?.referral_notice : row.referral_notice}>{state?.memory_only || !row ? state?.referral_notice : row.referral_notice}</span></div> : null}
      <div className="progress-wrap"><progress className="processing-progress" aria-label="Processing progress" aria-valuetext={indeterminate ? state?.stage : `${progress.done} of ${progress.total} documents complete`} max={progress.total || 1} value={indeterminate ? undefined : progress.done} />{indeterminate ? <span className="progress-indicator" aria-hidden="true" /> : null}</div>
      <div className="connection-status">Bedrock: {state?.bedrock || '—'}</div>
      <nav className="bottom-navigation" aria-label="Form navigation"><button onClick={() => setScrollTarget('Fields')}><FileCheck2 size={18} /><span>Fields</span></button>{navigation.map(item => <button key={item.name} aria-expanded={visible.includes(item.name)} aria-controls={`group-${item.name}`} className={cn(visible.includes(item.name) && 'active')} onClick={() => toggle(item.name)}><item.icon size={18} /><span>{item.name}</span></button>)}</nav>
    </footer>
  </div>
}
