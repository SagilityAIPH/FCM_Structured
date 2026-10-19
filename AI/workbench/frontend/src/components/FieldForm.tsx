import { useState } from 'react'
import { Check, CheckCheck, ChevronDown, CircleAlert, FileCheck2, LoaderCircle, Sparkles, UserRound, ClipboardList, Briefcase, Building2, Scale, Send, Users, Info, HeartPulse, Tags } from 'lucide-react'
import { Button } from './ui/button'
import { Input } from './ui/input'
import type { DocumentDetail, Edit, Field } from '@/types'
import { cn } from '@/lib/utils'

const fieldId = (field: Pick<Field, 'key' | 'provider_index'>) => `${field.provider_index ?? 'main'}:${field.key}`
const groupIcons = { 'Claimant Information': UserRound, 'Claim Information': ClipboardList, 'RRS Classification': Tags, 'Case Manager Information': Briefcase, 'Attorney Information': Scale, 'Referral Information': Send, 'Employer Information': Users, 'Other Information': Info, 'NCM Information': HeartPulse }
const sourceLabels = { AI: 'AI · from RRS list', Rules: 'Legacy rules', Manual: 'Manually edited', None: 'No injury details found' }
const fieldPath = (group: string, label: string) => `${group} / ${label}`
const isProvider = (name: string) => /^Provider [1-9]\d*$/.test(name)
const providerNumber = (name: string) => Number(name.slice('Provider '.length))

// Display is not storage: keep a complete, validated date for the gate and adapter.
export function appointmentDate(value: string): string | null {
  const text = value.trim()
  let year: number, month: number, day: number
  let match = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(text)
  if (match) {
    year = Number(match[1]); month = Number(match[2]); day = Number(match[3])
  } else {
    match = /^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/.exec(text)
    if (match) {
      month = Number(match[1]); day = Number(match[2]); year = Number(match[3])
    } else {
      match = /^([A-Za-z]+) (\d{1,2}), (\d{4})$/.exec(text)
      if (!match) return null
      const names = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
      month = names.indexOf(match[1].toLowerCase()) + 1
      if (!month) month = names.findIndex(name => name.slice(0, 3) === match![1].toLowerCase()) + 1
      day = Number(match[2]); year = Number(match[3])
    }
  }
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > 31) return null
  const parsed = new Date(0)
  parsed.setUTCFullYear(year, month - 1, day)
  if (parsed.getUTCFullYear() !== year || parsed.getUTCMonth() + 1 !== month || parsed.getUTCDate() !== day) return null
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

export function appointmentTime(value: string): string | null {
  const text = value.trim()
  const match = /^(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?$/i.exec(text)
    || /^(\d{1,2})(\d{2})\s*([ap])\.?m\.?$/i.exec(text)
  if (match) {
    const hour = Number(match[1]), minute = Number(match[2] ?? 0)
    if (hour < 1 || hour > 12 || minute > 59) return null
    return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')} ${match[3].toUpperCase()}M`
  }
  const clock = /^(\d{1,2}):(\d{2})$/.exec(text)
  if (!clock) return null
  const hour = Number(clock[1]), minute = Number(clock[2])
  if (hour > 23 || minute > 59) return null
  return `${String(hour % 12 || 12).padStart(2, '0')}:${String(minute).padStart(2, '0')} ${hour < 12 ? 'AM' : 'PM'}`
}

export function appointmentDisplay(key: string, value: string): string {
  if (key === 'Appointment Date') {
    const date = appointmentDate(value)
    return date ? `${date.slice(5, 7)}/${date.slice(8)}/${date.slice(0, 4)}` : value
  }
  if (key === 'Appointment Time') {
    const time = appointmentTime(value)
    return time ? `${Number(time.slice(0, 2))}${time.slice(3, 5) === '00' ? '' : ':' + time.slice(3, 5)} ${time.slice(6)}` : value
  }
  return value
}

export function appointmentStored(key: string, value: string): string {
  if (key === 'Appointment Date') return appointmentDate(value) ?? value
  if (key === 'Appointment Time') return appointmentTime(value) ?? value
  return value
}

export function appointmentEdit(key: string, value: string, previous: string): string | null {
  // Preserve an untouched extracted value, even when its original syntax is not canonical.
  if (value === appointmentDisplay(key, previous)) return null
  return appointmentStored(key, value)
}

export default function FieldForm({ doc, busy, draft, memoryOnly, onDraft, onConfirm, onRetrySave }: {
  doc: DocumentDetail | null; busy: boolean; draft: Record<string, Edit>; memoryOnly: boolean; onDraft: (draft: Record<string, Edit>) => void; onConfirm: (index: number) => void; onRetrySave: () => void
}) {
  const [query, setQuery] = useState('')
  const [appointmentInputs, setAppointmentInputs] = useState<Record<string, string>>({})
  const edits = Object.values(draft)
  const validation = doc?.validation
  const missing = new Set(validation?.missing_fields || [])
  const confirmations = validation?.appointments.filter(a => !a.confirmed && a.reasons.length &&
    validation.confirmation_required.some(item => item.startsWith(`Provider ${a.provider_index} / `))) || []
  const pendingProvider = (name: string) => confirmations.some(item => name === `Provider ${item.provider_index}`) ||
    (validation?.confirmation_required || []).some(item => item.startsWith(`${name} / `))
  const attention = (name: string) => {
    const providerGaps = isProvider(name) ? validation?.provider_missing_fields[providerNumber(name) - 1] || [] : []
    const required = (validation?.missing_fields || []).filter(item => item.startsWith(`${name} / `)).length
    const needsConfirmation = isProvider(name) && pendingProvider(name) ? 1 : 0
    return {required, providerGaps: providerGaps.length, needsConfirmation}
  }
  // FieldForm is keyed by document revision; toggling a group never resets draft in App.
  const [openGroups, setOpenGroups] = useState<string[]>(() => doc?.groups.filter((group, index) =>
    !memoryOnly || index === 0 || (validation?.missing_fields || []).some(item => item.startsWith(`${group.name} / `)) ||
    (isProvider(group.name) && (validation?.provider_missing_fields[providerNumber(group.name) - 1]?.length || 0) > 0) ||
    pendingProvider(group.name)).map(group => group.name) || [])
  const expanded = (name: string) => !!query.trim() || openGroups.includes(name)
  const toggleGroup = (name: string) => setOpenGroups(current => current.includes(name) ? current.filter(item => item !== name) : [...current, name])
  const update = (field: Field, value: string) => {
    const next = {...draft}
    const stored = appointmentEdit(field.key, value, field.value)
    if (stored === null || stored === field.value) delete next[fieldId(field)]
    else next[fieldId(field)] = {key: field.key, provider_index: field.provider_index, value: stored}
    onDraft(next)
  }
  return <section className="fields-panel" aria-label="Extracted fields">
    {!doc?.groups.length ? <div className="empty-panel">{doc?.status === 'Processing' || doc?.status === 'Queued' ? <LoaderCircle className="animate-spin" /> : <FileCheck2 />}<strong>{doc?.status === 'Processing' ? 'Extracting your document' : doc ? 'Fields will appear here' : memoryOnly ? 'Waiting for RRS capture' : 'Ready when you are'}</strong><p>{doc?.error || (memoryOnly ? doc ? 'Captured referral fields will appear when extraction finishes.' : 'Select Start to capture referral text from RRS for review.' : doc ? 'Extraction starts automatically after import when Bedrock is configured.' : 'Import a document. Extraction, address checks, and daily Excel output run automatically.')}</p></div> : <>
      <div className={cn('validation-strip', doc.validation?.status === 'Passed' ? 'passed' : 'review')}>
        {doc.validation?.status === 'Passed' ? <CheckCheck size={17} /> : <CircleAlert size={17} />}
        <div><strong>NEXT STEP: {doc.validation?.status}</strong><span>{doc.validation?.status === 'Passed' ? 'Required information is complete.' : `${missing.size} missing required · ${validation?.confirmation_required.length || 0} appointment ${validation?.confirmation_required.length === 1 ? 'check needs' : 'checks need'} confirmation.`}</span></div>
      </div>
      {doc.save_error && !memoryOnly ? <div className="inline-error"><span>{doc.save_error}</span><Button variant="outline" size="sm" disabled={busy} onClick={onRetrySave}>Retry Excel save</Button></div> : null}
      <div className="field-filter"><Input aria-label="Find extracted field" placeholder="Find a field or value…" value={query} onChange={e => setQuery(e.target.value)} /><span title="The current extraction engine does not provide calibrated probabilities.">Confidence: not scored</span></div>
      <div className="group-controls"><Button variant="outline" size="sm" onClick={() => setOpenGroups(doc.groups.map(group => group.name))}>Expand all</Button><Button variant="outline" size="sm" onClick={() => setOpenGroups([])}>Collapse all</Button></div>
      <div className="field-groups">
        {doc.total_characters > 0 && doc.sent_characters > 0 && doc.sent_characters < doc.total_characters ? <div className="note warning"><CircleAlert size={14} /><p>Only {doc.sent_characters.toLocaleString()} of {doc.total_characters.toLocaleString()} characters were sent to Bedrock.{memoryOnly ? ' Review the capture before continuing.' : ' Increase the document limit in Settings and retry to cover the complete document.'}</p></div> : null}
        {doc.validation?.appointments.filter(a => a.reasons.length).map(a => <div className={cn('note', a.confirmed ? 'success' : 'warning')} key={a.provider_index}><CircleAlert size={15} /><div><strong>Provider {a.provider_index} · {appointmentDisplay('Appointment Date', a.appointment_date)}</strong><p>{a.reasons.join('. ')}.</p>{a.confirmed ? <span className="text-emerald-700">Appointment confirmed</span> : a.can_confirm ? <Button variant="outline" size="sm" className="mt-2" disabled={busy || !!edits.length} onClick={() => onConfirm(a.provider_index)}><Check />Confirm this appointment</Button> : null}</div></div>)}
        {doc.address_report.length ? <details className="automation-note"><summary><Sparkles size={14} />Automatic address check<span>{doc.address_report.filter(a => a.status === 'accepted').length} applied</span><ChevronDown size={13} /></summary><div>{doc.address_report.map((item, i) => <div key={i} className="address-result"><strong>{item.target} · {item.status === 'accepted' ? 'Applied automatically' : 'Unresolved'}</strong><p>{item.reason}</p>{Object.entries(item.changes).map(([key, change]) => <p key={key}>{key}: {change.original} → {change.suggested}</p>)}<small>{item.source}. {item.confidence}.</small></div>)}</div></details> : null}
        {doc.name_inference.length ? <details className="automation-note"><summary><CircleAlert size={14} />Inferred names require review<ChevronDown size={13} /></summary><div className="p-3">{doc.name_inference.map((item, i) => <p key={i} className="mb-2 text-xs">{Object.entries(item).map(([key, value]) => `${key}: ${String(value)}`).join(' · ')}</p>)}</div></details> : null}
        {doc.classification?.some(item => item.review || item.list === 'provisional') ? <details className="automation-note"><summary><Tags size={14} />RRS classification review<span>{doc.classification.filter(item => item.review).length} to check</span><ChevronDown size={13} /></summary><div className="p-3">{doc.classification.filter(item => item.review).map(item => <p key={item.field} className="mb-2 text-xs"><strong>{item.field}:</strong> {item.review}</p>)}{doc.classification.some(item => item.list === 'provisional') ? <p className="text-xs text-slate-500">Using provisional RRS lists. Run AI/export_rrs_dropdowns.py with the RRS Subject Line Builder open to load the live lists.</p> : null}</div></details> : null}
        {doc.groups.map(group => {
          const visible = group.fields.filter(field => `${field.label} ${appointmentInputs[fieldId(field)] ?? appointmentDisplay(field.key, draft[fieldId(field)]?.value ?? field.display_value ?? field.value)}`.toLowerCase().includes(query.toLowerCase()))
          if (!visible.length) return null
          const Icon = group.name.startsWith('Provider ') ? Building2 : groupIcons[group.name as keyof typeof groupIcons] || Info
          const groupAttention = attention(group.name)
          const open = expanded(group.name)
          return <section className="field-section" key={group.name}><button type="button" className="field-section-header" aria-expanded={open} aria-controls={`fields-${group.name.replace(/[^a-zA-Z0-9-]/g, '-')}`} onClick={() => toggleGroup(group.name)}><span><Icon size={14} />{group.name}</span><span className="section-count">{groupAttention.required || groupAttention.providerGaps ? <span className="section-attention">{groupAttention.required ? `Missing ${groupAttention.required}` : `Provider gaps ${groupAttention.providerGaps}`}</span> : null}{groupAttention.needsConfirmation ? <span className="section-attention">Needs confirmation {groupAttention.needsConfirmation}</span> : null}{visible.length}<ChevronDown size={13} /></span></button><div id={`fields-${group.name.replace(/[^a-zA-Z0-9-]/g, '-')}`} className="field-grid" hidden={!open}>{visible.map(field => {
            const id = fieldId(field)
            const displayOnly = field.display_value != null && field.display_value !== field.value
            const value = displayOnly ? field.display_value! : appointmentInputs[id] ?? appointmentDisplay(field.key, draft[id]?.value ?? field.value)
            const providerGap = isProvider(group.name) && (validation?.provider_missing_fields[providerNumber(group.name) - 1] || []).includes(field.label)
            const identityGap = isProvider(group.name) && field.label === 'Doctor / Facility' && (validation?.provider_missing_fields[providerNumber(group.name) - 1] || []).includes('Facility name or doctor first and last names')
            const gap = missing.has(fieldPath(group.name, field.label)) || providerGap || identityGap
            const needsConfirmation = field.label === 'Appointment Date' && pendingProvider(group.name)
            const large = /Description|Instructions|Compensable/.test(field.key)
            const wide = large || /Address|Email|E-mail|Customer Name|Contact Name|Claims Office Name|Response To|Doctor \/ Facility/.test(field.label) || field.label.length > 25
            return <label key={id} className={cn('field-control', wide && 'field-wide')}><span className="field-label">{field.label}{field.optional ? <small>Optional</small> : field.conditional ? <small>Conditional</small> : <span className="required-mark" title="Required">*</span>}</span>
              {large ? <textarea aria-label={`${group.name} / ${field.label}`} className={cn('field-textarea', gap && 'has-gap', needsConfirmation && 'needs-confirmation')} value={value} disabled={busy} onChange={e => update(field, e.target.value)} rows={field.key === 'Special Instructions' ? 9 : 3} /> : <Input aria-label={`${group.name} / ${field.label}`} className={cn(gap && 'has-gap', needsConfirmation && 'needs-confirmation', value === 'Not found' && 'text-slate-400')} value={value} readOnly={displayOnly} disabled={busy} onChange={e => { if (field.key === 'Appointment Date' || field.key === 'Appointment Time') setAppointmentInputs(current => ({...current, [id]: e.target.value})); update(field, e.target.value) }} onBlur={() => setAppointmentInputs(current => { const next = {...current}; delete next[id]; return next })} />}
              {displayOnly ? <Input aria-label={`${group.name} / Facility name (preserved)`} value={draft[id]?.value ?? field.value} disabled={busy} onChange={e => update(field, e.target.value)} /> : null}
              <span className="field-meta">{displayOnly ? <span>Facility: {field.value}. Edit doctor names in their own fields.</span> : null}{gap ? <span className="text-amber-700">Required information missing</span> : needsConfirmation ? <span className="text-amber-700">Appointment needs confirmation</span> : field.manual || draft[id] ? <span className="text-blue-600">{draft[id] ? 'Unsaved edit' : 'Manually edited'}</span> : field.source ? <span>{sourceLabels[field.source]}</span> : <span>{field.confidence === null ? 'Not scored' : `${field.confidence}% confidence`}</span>}</span>
            </label>
          })}</div></section>
        })}
        {!doc.groups.some(group => group.fields.some(field => `${field.label} ${appointmentInputs[fieldId(field)] ?? appointmentDisplay(field.key, draft[fieldId(field)]?.value ?? field.display_value ?? field.value)}`.toLowerCase().includes(query.toLowerCase()))) ? <p className="p-5 text-center text-slate-500">No matching fields.</p> : null}
      </div>
    </>}
  </section>
}
