import { useEffect, useState } from 'react'
import { Cable, KeyRound, Save, ShieldCheck } from 'lucide-react'
import { Button } from './ui/button'
import { Input } from './ui/input'
import type { Settings } from '@/types'
export default function SettingsForm({settings, configured, busy, onSave, onTest, onDirty}: {settings: Settings; configured: boolean; busy: boolean; onSave: (settings: Settings, key: string) => Promise<boolean>; onTest: () => void; onDirty: (dirty: boolean) => void}) {
  const [draft, setDraft] = useState(settings)
  const [key, setKey] = useState('')
  const dirty = !!key || JSON.stringify(draft) !== JSON.stringify(settings)
  useEffect(() => { onDirty(dirty) }, [dirty, onDirty])
  return <div className="settings-page"><div className="settings-title"><Cable size={19} /><div><h2>Amazon Bedrock</h2><p>Configure the extraction engine for this session.</p></div></div>
    <form onSubmit={async e => { e.preventDefault(); if (await onSave(draft, key)) setKey('') }}>
      <div className="settings-grid"><label className="col-span-2">AWS region<Input value={draft.region} disabled={busy} onChange={e => setDraft({...draft, region: e.target.value})} required /></label><label className="col-span-2">Model ID<Input value={draft.model} disabled={busy} onChange={e => setDraft({...draft, model: e.target.value})} required /></label>
      <label className="col-span-2">Bedrock API key<div className="relative"><KeyRound size={14} className="absolute left-3 top-2 text-slate-400" /><Input className="pl-8" type="password" autoComplete="off" value={key} disabled={busy} onChange={e => setKey(e.target.value)} placeholder={configured ? 'Configured · leave blank to keep current key' : 'Enter your Bedrock bearer token'} /></div><small>Kept in Python memory for this session. Never saved in the browser or returned by the bridge.</small></label>
      <label>Output token budget<Input type="number" min={128} max={16384} value={draft.max_tokens} disabled={busy} onChange={e => setDraft({...draft, max_tokens: Number(e.target.value)})} required /></label><label>Temperature<Input type="number" step="0.05" min="0" max="0.5" value={draft.temperature} disabled={busy} onChange={e => setDraft({...draft, temperature: Number(e.target.value)})} required /></label>
      <label className="col-span-2">Document character limit<Input type="number" min={5000} max={400000} value={draft.document_limit} disabled={busy} onChange={e => setDraft({...draft, document_limit: Number(e.target.value)})} required /></label></div>
      <div className="note mt-5"><ShieldCheck size={16} /><p>Importing starts extraction automatically. Missing addresses are checked with the U.S. Census service; a single compatible match fills missing components. Conflicts remain unresolved. Every extracted result is saved to the daily workbook with its Passed/Failed status.</p></div>
      <div className="mt-5 flex gap-2"><Button type="submit" disabled={busy}><Save />Save settings</Button><Button type="button" variant="outline" disabled={busy || !configured || !!key || JSON.stringify(draft) !== JSON.stringify(settings)} onClick={onTest}><Cable />Test connection</Button></div>
    </form></div>
}
