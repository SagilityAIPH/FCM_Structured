import {useEffect,useState} from 'react'
import {createRoot} from 'react-dom/client'
import {ClipboardList,Play,ShieldCheck} from 'lucide-react'
import {Button} from './components/ui/button'
import {Input} from './components/ui/input'
import './styles.css'

type Form={employer_name:string;claim_number:string;claim_id:string;claimant_first_name:string;claimant_last_name:string;address1:string;address2:string;city:string;state:string;postal_code:string;country:string;referral_number:string;record_id:string}
type Step={step:string;status:string;detail:string}
type Result={outcome:string;reason:string;stage:string;steps:Step[];request_status:string;request_reference:string;tracking_status:string;warning:string;problems:string[];error:{message:string;stage?:string;type?:string}|null}
type Review={id:string;values:Record<string,string>}
type Prompt={id:string;kind:string;title:string;message:string;environment:string}
type State={status:string;busy:boolean;stage:string;elapsed:number;form:Form;environment:string;review:Review|null;prompt:Prompt|null;steps:Step[];result:Result|null;error:string}
type Reply={ok:boolean;data?:boolean;error?:string}
type API={initialize():Promise<{state:State;live:boolean}>;get_state():Promise<State>;start(form:Form):Promise<Reply>;answer_review(id:string,approved:boolean):Promise<Reply>;answer_prompt(id:string,confirmed:boolean):Promise<Reply>}
declare global {interface Window {pywebview?:{api:API}}}
const fields:[keyof Form,string][]=[['employer_name','Employer name *'],['claim_number','Claim number *'],['claim_id','Claim ID * (separate from claim number)'],['claimant_first_name','Claimant first name *'],['claimant_last_name','Claimant last name *'],['address1','Address line 1 *'],['address2','Address line 2'],['city','City *'],['state','State *'],['postal_code','Postal code *'],['country','Country *'],['referral_number','Referral number'],['record_id','Record ID']]
const defaults=Object.fromEntries(fields.map(([field])=>[field,field==='country'?'USA':''])) as Form
const initial:State={status:'idle',busy:false,stage:'',elapsed:0,form:defaults,environment:'UAT',review:null,prompt:null,steps:[],result:null,error:''}
function App(){
 const [state,setState]=useState<State>(initial),[form,setForm]=useState<Form>(defaults),[connected,setConnected]=useState(false),[live,setLive]=useState(false),[pending,setPending]=useState(false),[error,setError]=useState('')
 useEffect(()=>{let cancelled=false;let timer:ReturnType<typeof setTimeout>;let initialized=false;async function poll(){try{const api=window.pywebview?.api;if(api){if(!initialized){const init=await api.initialize();if(cancelled)return;setForm(init.state.form);setLive(init.live);setConnected(true);initialized=true}const s=await api.get_state();if(!cancelled)setState(s)}}catch(e){if(!cancelled)setError(String(e))}if(!cancelled)timer=setTimeout(poll,350)}void poll();return()=>{cancelled=true;clearTimeout(timer)}},[])
 async function act(fn:()=>Promise<Reply>){setPending(true);setError('');try{const r=await fn();if(!r.ok)setError(r.error||'Action rejected')}catch(e){setError(String(e))}finally{setPending(false)}}
 const locked=state.busy||pending;const result=state.result
 return <div className="shell"><header><div className="brand"><span className="app-icon"><ClipboardList size={22}/></span><div><h1>CEM Employer Request</h1><p>Separate operator-started app · {live?'attended live':'offline synthetic'}</p></div><span className={'badge '+state.status}>{state.environment}</span></div></header>
 <main><p className="intro">Create only a new employer request after CMS Customer Search stops. Start is explicit; submitted does not mean approved. Never retry an uncertain submission without reconciling in the portal.</p>
 {!connected?<div className="notice">Waiting for the desktop bridge.</div>:null}
 {error||state.error?<div role="alert" className="error">{error||state.error}</div>:null}
 {result?<section aria-live="polite" className={'outcome '+result.outcome}><h2>{result.outcome==='completed'?'Request submitted':result.outcome==='stopped'?'Request stopped':result.outcome==='cancelled'?'Request cancelled':'Request failed'}</h2><p>{result.reason.replaceAll('_',' ')}</p><p className="muted">Stopped at {result.stage} · request {result.request_status}{result.request_reference?` · reference ${result.request_reference}`:''} · tracking {result.tracking_status}</p>{result.warning?<p role="alert" className="error">{result.warning}</p>:null}{result.problems.map(x=><p key={x}>{x}</p>)}{result.error?<p>{result.error.message}</p>:null}</section>:null}
 <section className="card"><h2><ShieldCheck size={15}/>Employer request</h2><div className="field-grid">{fields.map(([key,label])=><label key={key}><span>{label}</span><Input value={form[key]} disabled={locked} onChange={e=>setForm(f=>({...f,[key]:e.target.value}))}/></label>)}</div></section>
 {state.busy?<section className="notice" role="status">Running · {state.stage} · {state.elapsed}s. Complete the review and final confirmation to proceed.</section>:null}
 {state.steps.length?<section className="card"><h2>Progress</h2><div className="content">{state.steps.map((s,i)=><p key={i}><strong>{s.step}</strong> · {s.status}{s.detail?` — ${s.detail}`:''}</p>)}</div></section>:null}</main>
 <footer><div className="actions"><Button disabled={!connected||locked} onClick={()=>void act(()=>window.pywebview!.api.start(form))}><Play size={14}/>{state.busy?'Running…':'Start employer request'}</Button><span role="status">{live?'Attended live':'Offline synthetic'} · {state.environment}</span></div></footer>
 {state.review?<div className="overlay" role="presentation"><div className="prompt review-dialog" role="dialog" aria-modal="true" aria-label="Review CEM form"><h2>Review portal read-back before Submit</h2><table><tbody>{Object.entries(state.review.values).map(([key,value])=><tr key={key}><th scope="row">{key.replaceAll('_',' ')}</th><td>{value||'—'}</td></tr>)}</tbody></table><p>Verify employer, bill-to name AND code, address, claim number, distinct Claim ID and claimant. Approval does not submit.</p><div className="actions"><Button disabled={pending} onClick={()=>void act(()=>window.pywebview!.api.answer_review(state.review!.id,true))}>Approve read-back</Button><Button variant="outline" disabled={pending} onClick={()=>void act(()=>window.pywebview!.api.answer_review(state.review!.id,false))}>Cancel</Button></div></div></div>:null}
 {state.prompt?<div className="overlay" role="presentation"><div className="prompt" role="dialog" aria-modal="true" aria-label="Final submit confirmation"><h2>{state.prompt.title} · {state.prompt.environment}</h2><p>{state.prompt.message}</p><div className="actions"><Button disabled={pending} onClick={()=>void act(()=>window.pywebview!.api.answer_prompt(state.prompt!.id,true))}>Submit once to {state.prompt.environment}</Button><Button variant="outline" disabled={pending} onClick={()=>void act(()=>window.pywebview!.api.answer_prompt(state.prompt!.id,false))}>Decline submit</Button></div></div></div>:null}</div>
}
createRoot(document.getElementById('root')!).render(<App/>)
