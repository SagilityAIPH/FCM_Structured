import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'

test.use({ channel: 'msedge' })

for (const multipleProviders of [false, true]) {
 test(`session edits survive polling and reach Start (${multipleProviders ? 'multiple providers' : 'single provider'})`, async ({ page }) => {
  await page.route('http://cms-synthetic.test/**', async route => {
   const resource = new URL(route.request().url()).pathname
   const file = resource === '/' ? 'index.html' : path.basename(resource)
   const body = await readFile(path.join(process.cwd(), 'dist', resource === '/' ? '' : 'assets', file))
   await route.fulfill({ body, contentType: file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : 'text/html' })
  })
  await page.addInitScript(({ multipleProviders }) => {
   const form = { claim_number: 'SYN-0001', claimant_first_name: 'Synthetic', claimant_last_name: 'Example', referral_type: 'Medical', cms_case_id: '', referral_number: '', cem_employer_request: 'no' }
   const setup_fields = [{ key: 'dxCode', label: 'Diagnosis code' }, { key: 'Special_Instructions', label: 'Special instructions', multiline: true }, { key: 'xlProvider', label: 'Primary provider name' }, { key: 'provType', label: 'Primary provider type', choices: ['', 'doctor', 'facility'] }]
   const provider_fields = [{ key: 'name', label: 'Provider name' }, { key: 'type', label: 'Provider type', choices: ['', 'doctor', 'facility'] }, { key: 'first_name', label: 'Doctor first name' }, { key: 'last_name', label: 'Doctor last name' }, { key: 'phone', label: 'Phone' }]
   const data = (row:number) => ({ dxCode: row === 2 ? 'SYN-original' : '', Special_Instructions: '', xlProvider: 'Synthetic legacy provider', provType: 'facility', review_fields: { 'Original reference': 'Synthetic reference only' }, ...(multipleProviders ? { providers: [{ name: 'Synthetic facility', type: 'facility', phone: '555-0100' }, { name: 'Synthetic doctor', type: 'doctor', phone: '' }] } : {}) })
   const state = { status: 'idle', busy: false, stage: '', elapsed: 0, form, prompt: null, review: null, steps: [], result: null, error: '', preview_only: true, data_source: 'excel', excel: { id: 'SYN-workbook', filename: 'synthetic.xlsx', selected_row: 2, rows: [{ row: 2, label: 'SYN-0001', warning: '' }, { row: 3, label: 'SYN-0002', warning: '' }], data: data(2), warning: '' } }
   const mock = { submitted: [] as unknown[], polls: 0 }
   Object.assign(window, { synthetic: mock, pywebview: { api: {
    initialize: async () => ({ state, live: true, setup_fields, provider_fields }),
    get_state: async () => { mock.polls++; return structuredClone(state) },
    select_excel_row: async (row:number) => { state.excel.selected_row = row; state.excel.data = data(row); return { ok: true, data: form } },
    start: async (...args:unknown[]) => { mock.submitted = args; state.busy = true; return { ok: true, data: true } }
   } } })
  }, { multipleProviders })
  await page.goto('http://cms-synthetic.test/')
  await page.getByLabel('Diagnosis code', { exact: true }).fill('SYN-edited')
  await page.getByLabel('Special instructions', { exact: true }).fill('Synthetic first line\nSynthetic second line')
  if (multipleProviders) {
   await expect(page.getByLabel('Primary provider name', { exact: true })).toHaveCount(0)
   await expect(page.getByRole('group', { name: 'Provider 1', exact: true }).getByLabel('Doctor first name', { exact: true })).toHaveCount(0)
   await page.getByRole('group', { name: 'Provider 1', exact: true }).getByLabel('Provider name', { exact: true }).fill('Synthetic corrected facility')
   await page.getByRole('group', { name: 'Provider 1', exact: true }).getByLabel('Phone', { exact: true }).fill('')
   await page.getByRole('group', { name: 'Provider 2', exact: true }).getByLabel('Doctor first name', { exact: true }).fill('Synthetic')
   await page.getByRole('group', { name: 'Provider 2', exact: true }).getByLabel('Doctor last name', { exact: true }).fill('Corrected')
   await expect(page.getByRole('group', { name: 'Provider 2', exact: true }).getByLabel('Provider name', { exact: true })).toHaveValue('Synthetic Corrected')
  } else {
   await page.getByLabel('Primary provider name', { exact: true }).fill('Synthetic corrected provider')
  }
  const polls = await page.evaluate(() => (window as unknown as { synthetic:{polls:number} }).synthetic.polls)
  await expect.poll(() => page.evaluate(() => (window as unknown as { synthetic:{polls:number} }).synthetic.polls)).toBeGreaterThan(polls + 1)
  await expect(page.getByLabel('Diagnosis code', { exact: true })).toHaveValue('SYN-edited')
  await expect(page.getByLabel('Special instructions', { exact: true })).toHaveValue('Synthetic first line\nSynthetic second line')
  if (!multipleProviders) {
   await page.getByLabel('Excel row to load', { exact: true }).selectOption('3')
   await page.getByRole('button', { name: 'Load row', exact: true }).click()
   await expect(page.getByLabel('Diagnosis code', { exact: true })).toHaveValue('')
   await expect(page.getByLabel('Special instructions', { exact: true })).toHaveValue('')
   await page.getByLabel('Diagnosis code', { exact: true }).fill('SYN-edited')
   await page.getByLabel('Special instructions', { exact: true }).fill('Synthetic first line\nSynthetic second line')
   await page.getByLabel('Primary provider name', { exact: true }).fill('Synthetic corrected provider')
  }
  await page.getByRole('button', { name: 'Start preview', exact: true }).click()
  await expect(page.getByLabel('Diagnosis code', { exact: true })).toBeDisabled()
  const args = await page.evaluate(() => (window as unknown as { synthetic:{submitted:unknown[]} }).synthetic.submitted)
  expect(args[3]).toBe(true)
  const payload = args[4] as { workbook_id:string;row:number;values:Record<string,unknown> }
  expect(payload.workbook_id).toBe('SYN-workbook')
  expect(payload.row).toBe(multipleProviders ? 2 : 3)
  expect(payload.values.dxCode).toBe('SYN-edited')
  expect(payload.values.Special_Instructions).toBe('Synthetic first line\nSynthetic second line')
  expect(payload.values).not.toHaveProperty('review_fields')
  if (multipleProviders) {
   expect(payload.values).not.toHaveProperty('xlProvider')
   expect(payload.values.providers).toEqual([{ name: 'Synthetic corrected facility', type: 'facility', phone: '', first_name: '', last_name: '' }, { name: 'Synthetic Corrected', type: 'doctor', phone: '', first_name: 'Synthetic', last_name: 'Corrected' }])
  } else {
   expect(payload.values.xlProvider).toBe('Synthetic corrected provider')
  }
 })
}
