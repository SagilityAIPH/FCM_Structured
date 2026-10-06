// Explicit synthetic browser preview. Never used by the desktop bridge.
import type { API, DocumentDetail, Field, State } from '@/types'

const state: State = {
  documents: [], busy: false, stage: 'Preview mode · example data only', bedrock: 'Preview only', elapsed: 0,
  progress: {done: 0, total: 0}, key_configured: true, output_directory: 'Preview / Output / AI',
  settings: {region: 'us-east-2', model: 'openai.gpt-oss-120b-1:0', max_tokens: 32768, temperature: 0, document_limit: 100000},
}
const records = new Map<string, DocumentDetail>()
const copy = <T,>(value: T): T => structuredClone(value)
function example(id: string, name: string, claimant: string, review: boolean): DocumentDetail {
  const field = (label: string, value: string, optional = false): Field => ({key: label, label, value, provider_index: null, confidence: null, manual: false, optional, conditional: false})
  const groups = [
    {name: 'Claimant Information', fields: [field('First Name', claimant.split(' ')[0]), field('Last Name', claimant.split(' ')[1]), field('Address-line-1', '125 Example Avenue'), field('Address-line-2', 'Not found', true), field('City', 'Worcester'), field('State', 'MA'), field('Zip', '01608'), field('Phone Number', '(508) 555-0142'), field('Date of Birth', '07/18/1985'), field('Gender', 'Female'), field('Customer Name', review ? 'Not found' : 'Example Manufacturing Inc.'), field('Customer Contact Name', 'Not found', true)]},
    {name: 'Claim Information', fields: [field('Claim Number', `WC-TEST-${id === 'example-1' ? '10482' : '10483'}`), field('Claim ID', 'DEMO-001'), field('Claim Type', 'Workers’ Compensation'), field('Date of Injury/Accident/Illness', '09/14/2026'), field('State/Jurisdiction of Claim', 'MA'), field('Diagnosis Code', 'Not found', true), field('Accident Description', 'Synthetic example for interface testing. No real claimant data.')]},
    {name: 'Case Manager Information', fields: [field('Claims Case Manager First Name', 'Jordan'), field('Claims Case Manager Last Name', 'Taylor'), field('Claims Office Name', 'Example Claims Office'), field('Claims Case Manager E-mail Address', 'jordan.taylor@example.com')]},
    {name: 'Provider 1', fields: [field('Provider / Facility', 'Example Medical Center'), field('Provider Address Line 1', '100 Sample Street'), field('City', 'Worcester'), field('State', 'MA'), field('Zip', '01608'), field('Appointment Date', '11/17/2026'), field('Appointment Time', 'Not found', true)].map(f => ({...f, provider_index: 0}))},
  ]
  return {id, name, claimant, claim: groups[1].fields[0].value, status: review ? 'Needs Review' : 'Completed', pages: 3, revision: 1, error: '', elapsed: 18.4, workbook: 'Preview / AI-output.xlsx', save_error: '', next_step: review ? 'Failed' : 'Passed', issues: review ? 1 : 0, groups, is_pdf: true, text: 'Synthetic document for the browser preview.', raw: '', record_id: id, validation: {status: review ? 'Failed' : 'Passed', missing_fields: review ? ['Claimant Information / Customer Name'] : [], provider_missing_fields: [], confirmation_required: [], appointments: []}, address_report: [], name_inference: [], address_review: [], edits: [], sent_characters: 8042, total_characters: 8042}
}
function sync() { state.documents = Array.from(records.values()).map(copy) }
export const previewAPI: API = {
  async get_state() { return copy(state) },
  async choose_documents() {
    if (!records.size) {
      records.set('example-1', example('example-1', 'MORGAN,AVERY.pdf', 'Avery Morgan', false))
      records.set('example-2', example('example-2', 'BENNETT,RILEY.pdf', 'Riley Bennett', true))
      state.stage = 'Synthetic examples loaded · no extraction or address service was called'
      state.progress = {done: 2, total: 2}; state.elapsed = 36.8; sync()
    }
    return Array.from(records.keys())
  },
  async get_document(id) { const doc = records.get(id); if (!doc) throw new Error('Example not found'); return copy(doc) },
  async render_page(id, page, scale) {
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(612 * scale); canvas.height = Math.round(792 * scale)
    const ctx = canvas.getContext('2d')!; ctx.scale(scale, scale)
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, 612, 792)
    ctx.fillStyle = '#334155'; ctx.font = 'bold 15px Segoe UI'; ctx.fillText('EXAMPLE CLAIMS', 45, 53)
    ctx.font = '9px Segoe UI'; ctx.fillStyle = '#94a3b8'; ctx.fillText('SYNTHETIC DOCUMENT · INTERFACE PREVIEW ONLY', 45, 71)
    ctx.fillStyle = '#0f172a'; ctx.font = 'bold 20px Segoe UI'; ctx.fillText('Nurse Case Management Referral', 45, 110)
    ctx.font = '10px Segoe UI'; ctx.fillStyle = '#64748b'; ctx.fillText(`Referral reference: ${records.get(id)?.claim}                           Page ${page + 1} of 3`, 45, 133)
    let y = 164
    const groups = records.get(id)!.groups.slice(page === 0 ? 0 : 2)
    for (const group of groups) {
      ctx.fillStyle = '#f1f5f9'; ctx.fillRect(45, y, 522, 26)
      ctx.fillStyle = '#334155'; ctx.font = 'bold 11px Segoe UI'; ctx.fillText(group.name.toUpperCase(), 54, y + 17); y += 45
      for (let i = 0; i < group.fields.length; i += 2) {
        for (let j = 0; j < 2 && group.fields[i + j]; j++) {
          const f = group.fields[i + j]; const x = 54 + j * 267
          ctx.font = '9px Segoe UI'; ctx.fillStyle = '#64748b'; ctx.fillText(f.label, x, y)
          ctx.font = '11px Segoe UI'; ctx.fillStyle = '#1e293b'; ctx.fillText(f.value === 'Not found' ? '—' : f.value.slice(0, 37), x, y + 17)
        }
        y += 44
      }
      y += 12
      if (y > 640) break
    }
    ctx.fillStyle = '#94a3b8'; ctx.font = '9px Segoe UI'; ctx.fillText('This is a generated preview fixture, not a real referral or model output.', 45, 753)
    return canvas.toDataURL('image/png')
  },
  async save_settings(settings) { state.settings = copy(settings); return true },
  async test_connection() { throw new Error('Live connection tests are available only in the Python desktop app.') },
  async start_processing() { throw new Error('Real extraction requires the Python desktop app. These are synthetic examples.') },
  async save_fields(id, edits, revision) {
    const doc = records.get(id)!
    if (revision !== doc.revision) throw new Error('Stale edits')
    for (const edit of edits) for (const group of doc.groups) for (const field of group.fields) if (field.key === edit.key && field.provider_index === edit.provider_index) { field.value = edit.value || 'Not found'; field.manual = true }
    const customer = doc.groups[0].fields.find(f => f.key === 'Customer Name')!
    const missing = customer.value === 'Not found'
    doc.next_step = missing ? 'Failed' : 'Passed'; doc.issues = missing ? 1 : 0; doc.status = missing ? 'Needs Review' : 'Completed'
    doc.validation!.status = doc.next_step; doc.validation!.missing_fields = missing ? ['Claimant Information / Customer Name'] : []
    doc.revision++; sync(); return true
  },
  async confirm_appointment() { return true },
  async retry_save() { throw new Error('Excel output is available in the Python desktop app.') },
  async export_document(id, kind) {
    const blob = new Blob([JSON.stringify(records.get(id), null, 2)], {type: 'application/json'})
    const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = `synthetic-preview-${kind}.json`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
    return anchor.download
  },
  async set_unsaved() { return true },
  async open_output() { throw new Error('The browser preview does not create local workbooks.') },
}
