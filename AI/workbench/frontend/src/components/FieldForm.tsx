import { useState } from 'react'
import { Check, CheckCheck, ChevronDown, CircleAlert, FileCheck2, LoaderCircle, Sparkles, UserRound, ClipboardList, Briefcase, Building2, Scale, Send, Users, Info, HeartPulse } from 'lucide-react'
import { Button } from './ui/button'
import { Input } from './ui/input'
import type { DocumentDetail, Edit, Field } from '@/types'
import { cn } from '@/lib/utils'

const fieldId = (field: Pick<Field, 'key' | 'provider_index'>) => `${field.provider_index ?? 'main'}:${field.key}`
const groupIcons = { 'Claimant Information': UserRound, 'Claim Information': ClipboardList, 'Case Manager Information': Briefcase, 'Attorney Information': Scale, 'Referral Information': Send, 'Employer Information': Users, 'Other Information': Info, 'NCM Information': HeartPulse }
export default function FieldForm({ doc, busy, draft, onDraft, onConfirm, onRetrySave }: {
  doc: DocumentDetail | null; busy: boolean; draft: Record<string, Edit>; onDraft: (draft: Record<string, Edit>) => void; onConfirm: (index: number) => void; onRetrySave: () => void
}) {
  const [query, setQuery] = useState('')
  const edits = Object.values(draft)
  const missing = new Set(doc?.validation?.missing_fields || [])
  const update = (field: Field, value: string) => {
    const next = {...draft}
    if (value === field.value) delete next[fieldId(field)]
    else next[fieldId(field)] = {key: field.key, provider_index: field.provider_index, value}
    onDraft(next)
  }
  return <section className="fields-panel" aria-label="Extracted fields">
    {!doc?.groups.length ? <div className="empty-panel">{doc?.status === 'Processing' || doc?.status === 'Queued' ? <LoaderCircle className="animate-spin" /> : <FileCheck2 />}<strong>{doc?.status === 'Processing' ? 'Extracting your document' : doc ? 'Fields will appear here' : 'Ready when you are'}</strong><p>{doc?.error || (doc ? 'Extraction starts automatically after import when Bedrock is configured.' : 'Import a document. Extraction, address checks, and daily Excel output run automatically.')}</p></div> : <>
      <div className={cn('validation-strip', doc.validation?.status === 'Passed' ? 'passed' : 'review')}>
        {doc.validation?.status === 'Passed' ? <CheckCheck size={17} /> : <CircleAlert size={17} />}
        <div><strong>NEXT STEP: {doc.validation?.status}</strong><span>{doc.validation?.status === 'Passed' ? 'Required information is complete.' : `${doc.issues} required field or appointment check${doc.issues === 1 ? '' : 's'} need attention.`}</span></div>
      </div>
      {doc.save_error ? <div className="inline-error"><span>{doc.save_error}</span><Button variant="outline" size="sm" disabled={busy} onClick={onRetrySave}>Retry Excel save</Button></div> : null}
      <div className="field-filter"><Input aria-label="Find extracted field" placeholder="Find a field or value…" value={query} onChange={e => setQuery(e.target.value)} /><span title="The current extraction engine does not provide calibrated probabilities.">Confidence: not scored</span></div>
      <div className="field-groups">
        {doc.sent_characters < doc.total_characters ? <div className="note warning"><CircleAlert size={14} /><p>Only {doc.sent_characters.toLocaleString()} of {doc.total_characters.toLocaleString()} characters were sent to Bedrock. Increase the document limit in Settings and retry to cover the complete document.</p></div> : null}
        {doc.validation?.appointments.filter(a => a.reasons.length).map(a => <div className={cn('note', a.confirmed ? 'success' : 'warning')} key={a.provider_index}><CircleAlert size={15} /><div><strong>Provider {a.provider_index} · {a.appointment_date}</strong><p>{a.reasons.join('. ')}.</p>{a.confirmed ? <span className="text-emerald-700">Appointment confirmed</span> : a.can_confirm ? <Button variant="outline" size="sm" className="mt-2" disabled={busy || !!edits.length} onClick={() => onConfirm(a.provider_index)}><Check />Confirm this appointment</Button> : null}</div></div>)}
        {doc.address_report.length ? <details className="automation-note"><summary><Sparkles size={14} />Automatic address check<span>{doc.address_report.filter(a => a.status === 'accepted').length} applied</span><ChevronDown size={13} /></summary><div>{doc.address_report.map((item, i) => <div key={i} className="address-result"><strong>{item.target} · {item.status === 'accepted' ? 'Applied automatically' : 'Unresolved'}</strong><p>{item.reason}</p>{Object.entries(item.changes).map(([key, change]) => <p key={key}>{key}: {change.original} → {change.suggested}</p>)}<small>{item.source}. {item.confidence}.</small></div>)}</div></details> : null}
        {doc.name_inference.length ? <details className="automation-note"><summary><CircleAlert size={14} />Inferred names require review<ChevronDown size={13} /></summary><div className="p-3">{doc.name_inference.map((item, i) => <p key={i} className="mb-2 text-xs">{Object.entries(item).map(([key, value]) => `${key}: ${String(value)}`).join(' · ')}</p>)}</div></details> : null}
        {doc.groups.map(group => {
          const visible = group.fields.filter(field => `${field.label} ${draft[fieldId(field)]?.value ?? field.value}`.toLowerCase().includes(query.toLowerCase()))
          if (!visible.length) return null
          const Icon = group.name.startsWith('Provider ') ? Building2 : groupIcons[group.name as keyof typeof groupIcons] || Info
          return <details className="field-section" key={group.name} open><summary><span><Icon size={14} />{group.name}</span><span className="section-count">{visible.length}<ChevronDown size={13} /></span></summary><div className="field-grid">{visible.map(field => {
            const id = fieldId(field)
            const value = draft[id]?.value ?? field.value
            const gap = missing.has(`${group.name} / ${field.label}`) || (field.conditional && missing.has(`${group.name} / Facility name or doctor first and last names`))
            const large = /Description|Instructions|Compensable/.test(field.key)
            const wide = large || /Address|Email|E-mail|Customer Name|Contact Name|Claims Office Name|Response To|Provider \/ Facility/.test(field.label) || field.label.length > 25
            return <label key={id} className={cn('field-control', wide && 'field-wide')}><span className="field-label">{field.label}{field.optional ? <small>Optional</small> : field.conditional ? <small>Conditional</small> : <span className="required-mark" title="Required">*</span>}</span>
              {large ? <textarea aria-label={`${group.name} / ${field.label}`} className={cn('field-textarea', gap && 'has-gap')} value={value} disabled={busy} onChange={e => update(field, e.target.value)} rows={field.key === 'Special Instructions' ? 9 : 3} /> : <Input aria-label={`${group.name} / ${field.label}`} className={cn(gap && 'has-gap', value === 'Not found' && 'text-slate-400')} value={value} disabled={busy} onChange={e => update(field, e.target.value)} />}
              <span className="field-meta">{gap ? <span className="text-amber-700">Required information missing</span> : field.manual || draft[id] ? <span className="text-blue-600">{draft[id] ? 'Unsaved edit' : 'Manually edited'}</span> : <span>{field.confidence === null ? 'Not scored' : `${field.confidence}% confidence`}</span>}</span>
            </label>
          })}</div></details>
        })}
        {!doc.groups.some(group => group.fields.some(field => `${field.label} ${draft[fieldId(field)]?.value ?? field.value}`.toLowerCase().includes(query.toLowerCase()))) ? <p className="p-5 text-center text-slate-500">No matching fields.</p> : null}
      </div>
    </>}
  </section>
}
