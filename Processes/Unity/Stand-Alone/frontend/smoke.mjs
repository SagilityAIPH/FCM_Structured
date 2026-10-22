// Synthetic browser workflow against the actual built frontend. No live bridge.
import { chromium } from '@playwright/test'
import { createServer } from 'node:http'
import { readFile, mkdtemp, rm, mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { join, resolve, sep } from 'node:path'
import assert from 'node:assert/strict'

const here = fileURLToPath(new URL('.', import.meta.url))
const dist = join(here, 'dist')
const evidence = resolve(here, '../acceptance')
const fixture = JSON.parse(await readFile(join(here, 'src', 'schema.json'), 'utf8'))
const scratch = await mkdtemp(join(here, '.browser-smoke-'))
process.env.TEMP = scratch
process.env.TMP = scratch
const errors = []
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, 'http://localhost')
    const path = resolve(dist, '.' + decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname))
    if (!path.startsWith(dist + sep)) { response.writeHead(403); response.end(); return }
    const content = await readFile(path)
    response.setHeader('Content-Type', path.endsWith('.js') ? 'text/javascript' : path.endsWith('.css') ? 'text/css' : 'text/html')
    response.end(content)
  } catch { response.writeHead(404); response.end() }
})
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
let context
try {
  context = await chromium.launchPersistentContext(join(scratch, 'profile'), {
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true, viewport: { width: 560, height: 900 },
  })
  const page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`http://127.0.0.1:${server.address().port}/?mock=1`)
  await page.getByLabel('Claim number *', {exact:true}).fill('SYNTHETIC-BROWSER-001')
  await page.getByLabel('Employer / customer *', {exact:true}).fill('Synthetic Widgets')
  await page.getByLabel('First name *', {exact:true}).fill('Invented')
  await page.getByLabel('Last name *', {exact:true}).fill('Example')
  const chooseDocument = page.getByRole('button', {name:'Choose referral document',exact:true,includeHidden:true})
  const useExports = page.getByRole('button', {name:'Use RRS export folder',exact:true,includeHidden:true})
  const attachmentSource = page.getByRole('status', {name:'Attachment source'})
  assert.match(await attachmentSource.innerText(), /RRS export folder/)
  await page.getByText('Supported files: PDF (.pdf), Outlook message (.msg), email (.eml).', {exact:false}).waitFor()
  await chooseDocument.click()
  await page.getByText('Local document · synthetic-selected.msg', {exact:true}).waitFor()
  await useExports.click()
  await page.getByText('RRS export folder · exactly one exported attachment required', {exact:true}).waitFor()
  await chooseDocument.click()
  await page.getByText('Local document · synthetic-selected.eml', {exact:true}).waitFor()
  await page.getByLabel('Stage', {exact:true}).selectOption('assign')
  await page.getByText('Assign ignores attachments entirely.', {exact:false}).waitFor()
  await page.getByLabel('Stage', {exact:true}).selectOption('all')
  const instructions = page.locator('textarea[name="specialInstructions"]')
  assert.equal(await instructions.count(), 1)
  assert.ok(await instructions.evaluate(el => el.rows > 1))
  for (const group of fixture.schema) for (const field of group.fields) {
    if (field.choices) continue
    const control = page.locator(`[name="${field.key}"]`)
    assert.equal(await control.evaluate(el => el.maxLength), field.maxLength)
    assert.equal(field.maxLength, field.key === 'specialInstructions' ? 32767 : 1000)
    assert.equal(await control.evaluate(el => el.tagName), field.key === 'specialInstructions' ? 'TEXTAREA' : 'INPUT')
  }
  await page.getByText('Up to 32,767 characters (Excel-compatible).', {exact:false}).waitFor()
  const prefix = ' \n\tSynthetic browser instructions\n', suffix = '\nEND-SYNTHETIC \t\n'
  let longValue
  for (const length of [1001, 32767]) {
    longValue = prefix + 'x'.repeat(length - prefix.length - suffix.length) + suffix
    await instructions.fill(longValue)
    assert.equal(await instructions.inputValue(), longValue)
    await page.getByRole('button', {name:'Validate fields'}).click()
    await page.getByText('Derived values', {exact:true}).waitFor()
    assert.equal(await instructions.inputValue(), longValue)
  }
  // Bypass the native editing cap to check explicit validation, not silent truncation.
  await instructions.evaluate((el, value) => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(el, value)
    el.dispatchEvent(new Event('input', {bubbles:true}))
  }, longValue + 'x')
  await page.getByRole('button', {name:'Validate fields'}).click()
  await page.getByRole('alert').filter({hasText:'specialInstructions. Use text up to 32,767 characters.'}).waitFor()
  assert.equal(await instructions.inputValue(), longValue + 'x')
  await instructions.fill(longValue)
  const claimID = page.locator('input[name="claimID"]')
  await claimID.fill('S'.repeat(1000))
  await page.getByRole('button', {name:'Validate fields'}).click()
  await page.getByText('Derived values', {exact:true}).waitFor()
  assert.equal(await instructions.inputValue(), longValue)
  assert.equal(await claimID.inputValue(), 'S'.repeat(1000))
  assert.equal(await attachmentSource.innerText(), 'Local document · synthetic-selected.eml')
  await page.getByRole('button', {name:'Run selected stage'}).click()
  await page.getByRole('dialog').waitFor()
  assert.equal(await chooseDocument.isDisabled(), true)
  assert.equal(await useExports.isDisabled(), true)
  await page.keyboard.press('Escape')
  assert.equal(await page.getByRole('dialog').count(), 1)
  await mkdir(evidence, {recursive:true})
  await page.screenshot({path:join(evidence, 'browser-confirm.png')})
  await page.getByRole('button', {name:'No · stop', exact:true}).click()
  await page.getByText('Process stopped', {exact:true}).waitFor()
  assert.match(await page.locator('.outcome').innerText(), /iCaseManager approval was declined/)
  await page.screenshot({path:join(evidence, 'browser-stopped.png')})
  await page.getByLabel('Stage', {exact:true}).selectOption('unity')
  await page.getByRole('button', {name:'Run selected stage'}).click()
  await page.getByText('Process completed', {exact:true}).waitFor()
  assert.equal(await attachmentSource.innerText(), 'Local document · synthetic-selected.eml')
  assert.equal(await chooseDocument.isEnabled(), true)
  await useExports.click()
  await page.getByText('RRS export folder · exactly one exported attachment required', {exact:true}).waitFor()
  assert.deepEqual(errors, [])
  const result = {mode:'synthetic browser mock',checks:['PDF/MSG/EML file type help','choose original synthetic MSG then EML and show filename/source','clear to RRS export folder','Assign attachment guidance','selection retained through validation and runs','attachment controls disabled while busy','grouped form editing','shared schema length metadata','multiline textarea','1001 and 32767 characters preserved including whitespace and suffix after validation','32768 explicitly rejected without truncation','ordinary inputs retain 1000 limit','validate preview','blocking accessible confirm','Escape cannot dismiss','decline stopped reason','unity completed'],pageErrors:errors}
  await writeFile(join(evidence, 'browser-smoke.json'), JSON.stringify(result,null,2)+'\n')
  console.log(JSON.stringify(result,null,2))
} finally {
  if(context)await context.close()
  await new Promise(resolve=>server.close(resolve))
  assert.ok(scratch.startsWith(here) && scratch.includes('.browser-smoke-'))
  await rm(scratch,{recursive:true,force:true,maxRetries:10,retryDelay:200})
}
