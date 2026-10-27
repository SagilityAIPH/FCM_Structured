import { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { ClipboardList, FileSpreadsheet, Play, ShieldCheck } from 'lucide-react'
import { Button } from './components/ui/button'
import { Input } from './components/ui/input'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from './components/ui/dialog'
import fixture from './schema.json'
import './styles.css'

type Data = Record<string,string>
type Field = {key:string; label:string; required:boolean; choices:string[]|null; date:boolean; maxLength:number}
type Group = {title:string; fields:Field[]}
type Prompt = {id:string;kind:string;title:string;message:string}
type Result = {status:string;reason:string;steps:string[];error:Record<string,unknown>;attachment:string}
type Attachment = {source:string;filename:string}
type State = {status:string;busy:boolean;stage:string;elapsed:number;prompt:Prompt|null;result:Result|null;error:string;warnings:string[];attachment:Attachment}
type Row = {row:number;label:string;warning:string}
type Scenario = 'attended'|'ncm_present'|'assign_ncm'
type Reply<T=unknown> = {ok:boolean;data?:T;error?:string}
type API = {
 initialize():Promise<{schema:Group[];defaults:Data;state:State;jurisdictions:string[]}>
 get_state():Promise<State>
 open_excel():Promise<Reply<{filename:string;rows:Row[]}|null>>
 select_excel_row(row:number):Promise<Reply<{data:Data;warning:string}>>
 save_excel_template():Promise<Reply>
 choose_referral_document():Promise<Reply<Attachment|null>>
 use_rrs_export_folder():Promise<Reply<Attachment>>
 validate_fields(data:Data,stage:string,jurisdiction:string,assignNCMAfterApproval?:boolean):Promise<Reply<{fields:Data;warnings:string[];derived:Data}>>
 start(data:Data,stage:string,tracking:boolean,jurisdiction:string,nurseCaseManagerPresent?:boolean,assignNCMAfterApproval?:boolean):Promise<Reply>
 answer_prompt(id:string,answer:boolean):Promise<Reply>
}
declare global {interface Window {pywebview?:{api:API}}}
const initial:State={status:'idle',busy:false,stage:'',elapsed:0,prompt:null,result:null,error:'',warnings:[],attachment:{source:'rrs',filename:''}}
const preview = new URLSearchParams(location.search).get('mock') === '1'
let mockState = {...initial}
let mockSelections = 0
let mockAssignNCM = false
const mockSteps=(stage:string,nurseCaseManagerPresent=false,assignNCMAfterApproval=false)=>[
 ...(stage==='assign'?[]:['resolve_attachment','run_unity','record_assignment']),
 ...(stage==='unity'?[]:[nurseCaseManagerPresent?'skip_icasemanager_approval_ncm_present':'await_icasemanager_approval',...(assignNCMAfterApproval?['assign_ncm']:[]),'complete_assignment'])
]
const mock:API = {
 async initialize(){return {...fixture,state:mockState}},
 async get_state(){return {...mockState}},
 async open_excel(){return {ok:false,error:'Workbook dialogs are available in the desktop app.'}},
 async select_excel_row(){return {ok:false,error:'Open a workbook in the desktop app.'}},
 async save_excel_template(){return {ok:false,error:'Use the supplied Unity-Input.xlsx template.'}},
 async choose_referral_document(){const extension=mockSelections++%2===0?'msg':'eml';mockState={...mockState,attachment:{source:'local',filename:`synthetic-selected.${extension}`}};return {ok:true,data:mockState.attachment}},
 async use_rrs_export_folder(){mockState={...mockState,attachment:{source:'rrs',filename:''}};return {ok:true,data:mockState.attachment}},
 async validate_fields(data,stage,jurisdiction,assignNCMAfterApproval=false){
  for(const group of fixture.schema)for(const field of group.fields){
   if((data[field.key]||'').length>field.maxLength)return {ok:false,error:`Invalid value for ${field.key}. Use text up to ${field.maxLength.toLocaleString('en-US')} characters.`}
  }
  const keys=[...new Set([...(stage==='assign'?['claimNumber']:['claimNumber','customer','claimantFirst','claimantLast']),...(stage!=='unity'&&assignNCMAfterApproval?['claimantFirst','claimantLast','ncm']:[])])]
  if(keys.some(k=>!data[k]?.trim()))return {ok:false,error:'Required: '+keys.filter(k=>!data[k]?.trim()).join(', ')}
  return {ok:true,data:{fields:data,warnings:['Browser preview uses synthetic behavior. Desktop performs full validation.'],derived:{claimStateAbbr:jurisdiction,serviceType:data.serviceType||'Medical Full'}}}
 },
 async start(data,stage,tracking,jurisdiction,nurseCaseManagerPresent=false,assignNCMAfterApproval=false){
  const r=await mock.validate_fields(data,stage,jurisdiction,assignNCMAfterApproval); if(!r.ok)return r
  mockAssignNCM=assignNCMAfterApproval
  mockState={...initial,attachment:mockState.attachment,status:'running',busy:true,stage,warnings:[`Preview only · tracking ${tracking?'enabled':'disabled'}`]}
  setTimeout(()=>{if(stage==='unity'||nurseCaseManagerPresent)mockState={...mockState,busy:false,status:'completed',result:{status:'completed',reason:'',steps:mockSteps(stage,nurseCaseManagerPresent),error:{},attachment:stage==='assign'?'':mockState.attachment.filename||'synthetic-referral.pdf'}}
   else mockState={...mockState,prompt:{id:crypto.randomUUID(),kind:'confirm',title:'Complete Assignment Stopper',message:'Confirm the referral is approved in iCaseManager. Preview only.'}}},500)
  return {ok:true}
 },
 async answer_prompt(id,answer){if(mockState.prompt?.id!==id)return {ok:false,error:'Prompt is no longer pending.'}; const steps=mockSteps(mockState.stage,false,mockAssignNCM); mockState={...mockState,busy:false,prompt:null,status:answer?'completed':'stopped',result:{status:answer?'completed':'stopped',reason:answer?'':'icasemanager_declined',steps:answer?steps:steps.slice(0,mockAssignNCM?-2:-1),error:{},attachment:mockState.stage==='assign'?'':mockState.attachment.filename||'synthetic-referral.pdf'}};return {ok:true}}
}
const api=()=>preview?mock:window.pywebview?.api
const stopReasons:Record<string,string>={attachment_missing:'Stopped: no referral attachment. Choose a local referral document or export this referral through RRS Complete Triage, then retry.',attachment_ambiguous:'Stopped: more than one attachment. Choose a local referral document or clear the export folder and re-export this referral.',icasemanager_declined:'Stopped: iCaseManager approval was declined. Complete Assignment did not run.'}

function App(){
 const [groups,setGroups]=useState<Group[]>([]),[data,setData]=useState<Data>({})
 const [jurisdictions,setJurisdictions]=useState<string[]>([]),[jurisdiction,setJurisdiction]=useState('')
 const [state,setState]=useState<State>(initial),[connected,setConnected]=useState(false)
 const [stage,setStage]=useState('all'),[tracking,setTracking]=useState(true),[pending,setPending]=useState(false)
 const [scenario,setScenario]=useState<Scenario>('attended')
 const [error,setError]=useState(''),[note,setNote]=useState(''),[rows,setRows]=useState<Row[]>([]),[row,setRow]=useState(0)
 const [review,setReview]=useState<{warnings:string[];derived:Data}|null>(null)
 const main=useRef<HTMLElement>(null)
 useEffect(()=>{if(state.result&&!state.busy)main.current?.scrollTo({top:0})},[state.result?.status,state.result?.reason,state.busy])
 useEffect(()=>{
  let cancelled=false, initialized=false,timer:ReturnType<typeof setTimeout>
  async function poll(){try{const bridge=api();if(bridge){if(!initialized){const r=await bridge.initialize();if(cancelled)return;setGroups(r.schema);setData(r.defaults);setJurisdictions(r.jurisdictions);setConnected(true);initialized=true}const s=await bridge.get_state();if(cancelled)return;setState(s)}}catch(e){if(!cancelled)setError(String(e))}if(!cancelled)timer=setTimeout(poll,350)}
  void poll();return()=>{cancelled=true;clearTimeout(timer)}
 },[])
 async function act(work:()=>Promise<Reply>){setPending(true);setError('');try{const r=await work();if(!r.ok)setError(r.error||'Action failed')}catch(e){setError(String(e))}finally{setPending(false)}}
 const locked=state.busy||pending
 return <div className="shell">
  <header><div className="brand"><span className="app-icon"><ClipboardList size={22}/></span><div><h1>Unity</h1><p>FCM Workbench · Assignment</p></div><span className={'badge '+state.status}>{state.status}</span></div></header>
  <main ref={main}>
   <p className="intro">Load a workbook row or enter a referral. Review the intended claim and select a local referral document or use the RRS exported attachment before starting.</p>
   {preview?<div className="notice">Browser preview · synthetic flow only</div>:!connected?<div className="notice">Waiting for desktop bridge. Use <code>?mock=1</code> for browser preview.</div>:null}
   {(error||state.error)?<div role="alert" className="error">{error||state.error}</div>:null}
   {state.result?<section aria-live="polite" className={'outcome '+state.status}><h2>{state.status==='stopped'?'Process stopped':state.status==='failed'?'Process failed':'Process completed'}</h2><p>{stopReasons[state.result.reason]||state.result.reason||'Selected stage completed.'}</p>{Object.keys(state.result.error).length?<p>{Object.entries(state.result.error).map(([k,v])=>`${k}: ${String(v)}`).join(' · ')}</p>:null}<p className="muted">{state.result.steps.join(' → ')}</p></section>:null}
   <section className="card"><h2><FileSpreadsheet size={15}/>Excel input</h2><div className="content">
    <div className="actions"><Button disabled={!connected||locked} onClick={()=>void act(async()=>{const r=await api()!.open_excel();if(r.ok&&r.data){setRows(r.data.rows);setRow(r.data.rows[0]?.row||0);setNote(r.data.filename+' · choose a row to load')}return r})}>Open workbook</Button><Button variant="outline" disabled={!connected||locked} onClick={()=>void act(()=>api()!.save_excel_template())}>Save template</Button></div>
    {rows.length?<div className="actions"><select aria-label="Workbook row" value={row} disabled={locked} onChange={e=>setRow(Number(e.target.value))}>{rows.map(r=><option key={r.row} value={r.row}>{r.label}</option>)}</select><Button variant="outline" disabled={locked} onClick={()=>void act(async()=>{const r=await api()!.select_excel_row(row);if(r.ok&&r.data){setData(r.data.data);setJurisdiction('');setReview(null);setNote(r.data.warning||'Row loaded. Review before running.')}return r})}>Load row</Button></div>:null}
    <p className="muted" role="status">{note||'One referral and one provider per row. Loading replaces fields and resets jurisdiction.'}</p>
   </div></section>
   <section className="card"><h2>Referral attachment</h2><div className="content">
    <div className="actions"><Button disabled={!connected||locked} onClick={()=>void act(async()=>{const r=await api()!.choose_referral_document();if(r.ok&&r.data){const attachment=r.data;setState(s=>({...s,attachment}))}return r})}>Choose referral document</Button><Button variant="outline" disabled={!connected||locked} onClick={()=>void act(async()=>{const r=await api()!.use_rrs_export_folder();if(r.ok&&r.data){const attachment=r.data;setState(s=>({...s,attachment}))}return r})}>Use RRS export folder</Button></div>
    <p role="status" aria-label="Attachment source">{state.attachment.source==='local'?`Local document · ${state.attachment.filename}`:'RRS export folder · exactly one exported attachment required'}</p>
    <p className="muted">Supported files: PDF (.pdf), Outlook message (.msg), email (.eml). Local selection is session-only and uploads the original file without conversion. No file is copied or added to the workbook. Assign ignores attachments entirely.</p>
   </div></section>
   <fieldset disabled={locked}>
   {groups.map(group=><details className="card" open key={group.title}><summary><ClipboardList size={14}/>{group.title}</summary><div className="field-grid">{group.fields.map(f=><label key={f.key} className={f.key==='specialInstructions'?'instructions-field':undefined}><span>{f.label}{(f.key==='claimNumber'||f.required&&stage!=='assign'||scenario==='assign_ncm'&&stage!=='unity'&&['ncm','claimantFirst','claimantLast'].includes(f.key))?' *':''}</span>{f.choices?<select value={data[f.key]||''} onChange={e=>{const value=e.currentTarget.value;setData(d=>({...d,[f.key]:value}));setReview(null)}}>{f.choices.map(c=><option value={c} key={c}>{c||'Leave blank'}</option>)}</select>:f.key==='specialInstructions'?<><textarea name={f.key} rows={6} maxLength={f.maxLength} value={data[f.key]||''} aria-describedby="instructions-limit" onChange={e=>{const value=e.currentTarget.value;setData(d=>({...d,[f.key]:value}));setReview(null)}}/><span id="instructions-limit">Up to {f.maxLength.toLocaleString('en-US')} characters (Excel-compatible). Line breaks and surrounding whitespace are preserved.</span></>:<Input name={f.key} maxLength={f.maxLength} value={data[f.key]||''} placeholder={f.date?'MM/DD/YYYY':undefined} onChange={e=>{const value=e.currentTarget.value;setData(d=>({...d,[f.key]:value}));setReview(null)}}/>}</label>)}</div></details>)}
   <section className="card"><h2><ShieldCheck size={15}/>Review and run</h2><div className="content">
    <label>Claim jurisdiction (optional derivation context)<select aria-label="Claim jurisdiction (optional derivation context)" value={jurisdiction} onChange={e=>{setJurisdiction(e.target.value);setReview(null)}}>{jurisdictions.map(s=><option key={s} value={s}>{s||'Unknown — review in Unity'}</option>)}</select></label>
    <p className="muted">Claim jurisdiction is separate from claimant State. Blank service type uses Medical Full; Continental Tire / Auto / MI derives Medical Task. An explicit service type overrides that fallback.</p>
    <label>Stage<select aria-label="Stage" value={stage} onChange={e=>{setStage(e.target.value);setReview(null)}}><option value="all">All · Unity + assignment</option><option value="unity">Unity · portal + tracking</option><option value="assign">Assign · approval + RRS completion</option></select></label>
    <fieldset aria-describedby="scenario-help" disabled={locked}>
     <legend>Assignment scenario</legend>
     <label className="checkbox"><input type="radio" name="assignment-scenario" value="ncm-present" checked={scenario==='ncm_present'} onChange={()=>{setScenario('ncm_present');setReview(null)}}/>Scenario 1 - Nurse Case Manager present</label>
     <label className="checkbox"><input type="radio" name="assignment-scenario" value="assign-ncm" checked={scenario==='assign_ncm'} onChange={()=>{setScenario('assign_ncm');setReview(null)}}/>Scenario 2 - Assign NCM after approval</label>
     <p id="scenario-help" className="muted">No scenario selected means the existing attended workflow. Scenario 1 skips ONLY iCaseManager approval in All/Assign. Scenario 2 keeps that approval: after Yes, search the task queue by claimant, open the first row in its existing newest-first list, verify claimant/claim, Assign Task, select the exact workbook NCM full name, set today's Assigned date, Complete Task, then continue RRS. Identical NCM names require one dropdown match to claimant address State, not jurisdiction or provider state; missing or ambiguous matches stop safely. No NCM city/state column is needed. All reuses its initial browser with no second login. Fresh Assign waits for manual sign-in once and reuses that browser for lookup. Initial login and pre-Complete-Task validation remain. Unity-only stays portal/tracking-only; neither scenario adds a postapproval action.</p>
     <Button variant="outline" disabled={locked||scenario==='attended'} onClick={()=>{setScenario('attended');setReview(null)}}>Use attended flow</Button>
    </fieldset>
    <label className="checkbox"><input type="checkbox" checked={tracking} onChange={e=>setTracking(e.target.checked)}/>Record tracking attempt even when Unity fails (legacy default)</label>
    <Button variant="outline" disabled={!connected||locked} onClick={()=>void act(async()=>{const r=await api()!.validate_fields(data,stage,jurisdiction,scenario==='assign_ncm');if(r.ok&&r.data){setData(r.data.fields);setReview(r.data)}return r})}>Validate fields</Button>
    {review?<div className="review"><p>Derived values</p><dl>{Object.entries(review.derived).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v||'Unknown'}</dd></div>)}</dl>{review.warnings.map(w=><p className="muted" key={w}>{w}</p>)}</div>:null}
   </div></section></fieldset>
   <details className="card"><summary>Workflow help</summary><div className="content muted">Save the template, fill it in Excel, open it and load the intended row. Default Assign needs only claim number; Scenario 2 All/Assign also needs claimant first/last names and NCM full name. Unity and All require customer and claimant names. Choose a local referral document (PDF, MSG or EML) for Unity/All, or export exactly one attachment through RRS Complete Triage. Assign ignores attachments and tracking. Scenario 1 skips only iCaseManager approval. Scenario 2 keeps approval and, only after Yes, selects the first claimant-filtered task in the existing newest-first queue, verifies claimant/claim, claims it with Assign Task, selects the exact NCM full name and today's Assigned date, then Complete Task before RRS. Name matching ignores case, extra whitespace and the dropdown location suffix, but never uses fuzzy or prefix selection. Identical names require exactly one match to claimant address State (full state name or code), not claim jurisdiction or provider state. Missing, invalid, unmatched or duplicate same-state candidates stop safely, including disabled duplicates. A unique exact name needs no state; no NCM location column is needed. Source supports explicitly owned body-mounted popup options and verifies the chosen full caption in the readonly selected-manager field, including after date blur. No or any failure stops before downstream work. All uses one browser/login; fresh Assign scenario 2 has one manual sign-in and reuses that browser for later lookup. Unity-only has no postapproval action. Use attended flow clears the scenario; it is not saved to Excel or persisted. NCM name is operator data in the appended workbook column; old workbooks load it blank. Browser preview is synthetic, not a live-login or save-outcome simulation. A previous isolated guarded live field probe succeeded, but corrected production source is not live verified; server Complete Task/persistence and RRS handoff remain untested. There is no mid-operation cancellation; finish prompts before closing. Live changes remain after a stop or failure.</div></details>
  </main>
  <footer><div className="actions"><Button disabled={!connected||locked} onClick={()=>void act(()=>api()!.start(data,stage,tracking,jurisdiction,scenario==='ncm_present',scenario==='assign_ncm'))}><Play size={14}/>{state.busy?'Running…':'Run selected stage'}</Button><span role="status">{state.busy?`${state.stage} · ${state.elapsed}s`:preview?'Preview ready':'Live desktop wiring'}</span></div></footer>
  <Dialog open={!!state.prompt} onOpenChange={()=>{}}>{state.prompt?<DialogContent className="prompt operator-prompt" onEscapeKeyDown={e=>e.preventDefault()} onPointerDownOutside={e=>e.preventDefault()}><DialogTitle>{state.prompt.title}</DialogTitle><DialogDescription>{state.prompt.message}</DialogDescription><div className="actions"><Button autoFocus disabled={pending} onClick={()=>void act(()=>api()!.answer_prompt(state.prompt!.id,true))}>{state.prompt.kind==='notify'?'Acknowledge':'Yes · approved'}</Button>{state.prompt.kind==='confirm'?<Button variant="outline" disabled={pending} onClick={()=>void act(()=>api()!.answer_prompt(state.prompt!.id,false))}>No · stop</Button>:null}</div></DialogContent>:null}</Dialog>
 </div>
}
createRoot(document.getElementById('root')!).render(<App/> )
