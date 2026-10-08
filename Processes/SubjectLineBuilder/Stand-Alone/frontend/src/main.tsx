import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { ClipboardList, ListChecks, CircleHelp, ChevronDown, Play, Square, Check, AlertCircle } from 'lucide-react'
import { Button } from './components/ui/button'
import { Input } from './components/ui/input'
import './styles.css'
import './manual.css'

type Field = { key: string; label: string; required: boolean; choices?: string[]; date: boolean }
type Group = { title: string; fields: Field[] }
type State = { status: string; stage: string; progress: number; prompt: string; error: string; busy: boolean; elapsed: number; review_id: number }
type Reply = { ok: boolean; error?: string }
type ExcelRow = { row: number; label: string }
type API = { initialize(): Promise<{schema: Group[]; defaults: Record<string,string>; state: State}>;
  open_excel(): Promise<Reply & {cancelled?: boolean; filename?: string; rows?: ExcelRow[]}>;
  select_excel_row(row: number): Promise<Reply & {data?: Record<string,string>; warning?: string}>;
  save_excel_template(): Promise<Reply & {cancelled?: boolean}>;
  get_state(): Promise<State>; start(data: Record<string,string>): Promise<Reply>;
  proceed(id: number, create: boolean): Promise<Reply>; stop(): Promise<Reply> }
declare global { interface Window { pywebview?: { api: API } } }

const INITIAL: State = {status:'idle',stage:'Connecting to desktop',progress:0,prompt:'',error:'',busy:false,elapsed:0,review_id:0}
function App() {
  const [groups, setGroups] = useState<Group[]>([])
  const [data, setData] = useState<Record<string,string>>({})
  const [state, setState] = useState<State>(INITIAL)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [extra, setExtra] = useState<'run'|'help'|null>(null)
  const [connected, setConnected] = useState(false)
  const [rows, setRows] = useState<ExcelRow[]>([])
  const [selectedRow, setSelectedRow] = useState(0)
  const [filename, setFilename] = useState('')
  const [excelNote, setExcelNote] = useState('')
  const scroll = useRef<HTMLElement>(null)
  const runPanel = useRef<HTMLElement>(null)
  const helpPanel = useRef<HTMLElement>(null)
  const lastReview = useRef(0)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    let initialized = false
    const poll = async () => {
      try {
        if (!window.pywebview) { timer=setTimeout(poll,250); return }
        if (!initialized) {
          const result = await window.pywebview.api.initialize()
          if (cancelled) return
          setGroups(result.schema); setData(result.defaults); setState(result.state); setConnected(true)
          initialized = true
        }
        const result = await window.pywebview.api.get_state()
        if (cancelled) return
        setState(result)
        if (result.prompt && result.review_id !== lastReview.current) {
          lastReview.current = result.review_id; setExtra('run')
          setTimeout(() => runPanel.current?.scrollIntoView({block:'start'}),50)
        }
      } catch (e) { if (!cancelled) setError(String(e)) }
      if (!cancelled) timer=setTimeout(poll,400)
    }
    void poll()
    return () => { cancelled=true; clearTimeout(timer) }
  }, [])

  async function act(action: () => Promise<Reply>) {
    setPending(true); setError('')
    try { const reply=await action(); if (!reply.ok) setError(reply.error || 'Action failed') }
    catch (e) { setError(String(e)) }
    finally { setPending(false) }
  }
  function navigate(panel: 'run'|'help'|null) {
    setExtra(panel)
    setTimeout(() => panel ? (panel==='run' ? runPanel : helpPanel).current?.scrollIntoView({block:'start'}) : scroll.current?.scrollTo({top:0}), 30)
  }
  async function openExcel() {
    const result = await window.pywebview!.api.open_excel()
    if (result.ok && !result.cancelled) {
      setRows(result.rows || []); setSelectedRow(result.rows?.[0]?.row || 0)
      setFilename(result.filename || ''); setExcelNote('Choose a row, then Load row to replace the form.')
    }
    return result
  }
  async function loadRow() {
    const result = await window.pywebview!.api.select_excel_row(selectedRow)
    if (result.ok && result.data) {
      setData(result.data)
      setExcelNote(`Row ${selectedRow} loaded. ${result.warning || 'Review the fields and defaults before starting.'}`)
    }
    return result
  }
  const locked = state.busy || pending
  return <div className="compact-shell">
    <header className="app-header"><div className="title-row"><span className="app-icon"><ClipboardList size={21}/></span><div><h1>Subject Line Builder</h1><p>FCM Workbench · Excel input</p></div><span className={'run-badge '+state.status}>{state.status.replace('_',' ')}</span></div></header>
    <main className="form-scroll" ref={scroll}>
      <p className="intro">Load an Excel row or enter details below. Open the intended referral’s Email Display in RRS before starting. Fields marked * are required.</p>
      {(error || state.error) && <div role="alert" className="error-box"><AlertCircle size={16}/><span>{error || state.error}</span></div>}
      <section className="extra-group"><div className="group-heading"><h2>Excel input</h2></div><div className="group-content excel-input">
        <div className="excel-actions"><Button disabled={!connected || locked} onClick={()=>void act(openExcel)}>Open Excel</Button><Button variant="outline" disabled={!connected || locked} onClick={()=>void act(async()=>{const r=await window.pywebview!.api.save_excel_template(); if(r.ok && !r.cancelled)setExcelNote('Template saved. Fill it in Excel, then use Open Excel.'); return r})}>Save template</Button></div>
        {filename && <p className="muted excel-filename">{filename} · {rows.length} row(s)</p>}
        {rows.length>0 && <><label className="field-control"><span className="field-label">Referral row</span><select aria-label="Referral row" disabled={locked} value={selectedRow} onChange={e=>setSelectedRow(Number(e.target.value))}>{rows.map(row=><option value={row.row} key={row.row}>{row.label}</option>)}</select></label><Button variant="outline" disabled={locked} onClick={()=>void act(loadRow)}>Load row</Button></>}
        <p className="muted" role="status">{excelNote || 'Use the supplied template. One referral and one provider per row.'}</p>
      </div></section>
      {groups.map(group => <details open className="field-section" key={group.title}><summary><span><ClipboardList size={14}/>{group.title}</span><ChevronDown size={13}/></summary><div className="field-grid">
        {group.fields.map(field => <label className="field-control" key={field.key}><span className="field-label">{field.label}{field.required && ' *'}</span>
          {field.choices ? <select aria-label={field.label} value={data[field.key] || ''} disabled={locked} onChange={e=>setData(d=>({...d,[field.key]:e.target.value}))}>{field.choices.map(c=><option key={c} value={c}>{c || 'Select…'}</option>)}</select>
          : <Input aria-label={field.label} name={field.key} maxLength={1000} disabled={locked} value={data[field.key] || ''} placeholder={field.date ? 'MM/DD/YYYY' : undefined} onChange={e=>setData(d=>({...d,[field.key]:e.target.value}))}/>}</label>)}
      </div></details>)}
      <section className="extra-group" hidden={extra!=='run'} ref={runPanel}><div className="group-heading"><h2>Processing and review</h2></div><div className="group-content">
        <p>{state.stage}</p>
        {state.prompt && <div className="review-box" role="status">{state.prompt}</div>}
        {['lookup','review'].includes(state.status) && <Button disabled={pending} onClick={()=>void act(()=>window.pywebview!.api.proceed(state.review_id,state.status==='review'))}><Check size={14}/>{state.status==='review' ? 'Create in RRS' : 'Continue after selection'}</Button>}
        {state.status==='completed' && <p className="success-text">Subject line created. The RRS window remains available.</p>}
        <p className="muted">Inputs stay visible during the run. Choose Fields below to reference addresses and phone numbers when adding a record in RRS.</p>
      </div></section>
      <section className="extra-group" hidden={extra!=='help'} ref={helpPanel}><div className="group-heading"><h2>How to use</h2></div><div className="group-content"><ol>
        <li>Save the Excel template and fill a row for each referral. Open Excel here, select a row and Load row.</li><li>Review or edit the imported fields. Loading another row replaces the entire form.</li><li>Open the correct Email Display in RRS. Keep only one intended builder open.</li><li>Start. In each RRS lookup, select or add the correct record, close the lookup, then Continue here.</li><li>Review the complete builder, including referral type and addresses, then click Create here.</li></ol>
        <p>One provider per run. Date-only appointments are supported. Input stays in this session only. Closing clears it.</p><p>Stop prevents further automation after the current UI call. Changes already made in RRS remain.</p></div></section>
    </main>
    <footer className="bottom-dock"><div className="save-row"><Button disabled={!connected || locked} onClick={()=>void act(()=>window.pywebview!.api.start(data))}><Play size={13}/>Start builder</Button><Button variant="outline" disabled={!state.busy || pending} onClick={()=>void act(()=>window.pywebview!.api.stop())}><Square size={12}/>Stop</Button><span>{state.elapsed}s</span></div>
      <div className="processing-status" role="status"><span>{state.prompt ? 'Action needed · open Review' : state.stage}</span><small>{state.progress}%</small></div>
      <div className="progress-wrap"><progress aria-label="Process progress" className="processing-progress" value={state.progress} max={100}/></div>
      <div className="connection-status">RRS desktop automation · {connected ? 'Ready' : 'Connecting'}</div>
      <nav className="bottom-navigation manual-navigation" aria-label="Sections"><button className={!extra?'active':''} onClick={()=>navigate(null)}><ClipboardList size={17}/>Fields</button><button className={extra==='run'?'active':''} onClick={()=>navigate('run')}><ListChecks size={17}/>Review</button><button className={extra==='help'?'active':''} onClick={()=>navigate('help')}><CircleHelp size={17}/>Help</button></nav>
    </footer>
  </div>
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
