// Synthetic browser workflow against the actual built frontend. No live bridge.
import { chromium } from '@playwright/test'
import { createServer } from 'node:http'
import { readFile, mkdtemp, rm, mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { join, resolve, sep } from 'node:path'
import assert from 'node:assert/strict'

const here = fileURLToPath(new URL('.', import.meta.url))
const dist = join(here, 'dist')
const evidence = resolve(here, process.env.UNITY_SMOKE_EVIDENCE || '../acceptance')
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
  await context.route('**/*', route => {
    const url = new URL(route.request().url())
    return url.hostname === '127.0.0.1' ? route.continue() : route.abort()
  })
  const page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`http://127.0.0.1:${server.address().port}/?mock=1`)
  await page.getByLabel('Claim number *', {exact:true}).fill('SYNTHETIC-BROWSER-001')
  await page.getByLabel('Employer / customer *', {exact:true}).fill('Synthetic Widgets')
  await page.getByLabel('First name *', {exact:true}).fill('Invented')
  await page.getByLabel('Last name *', {exact:true}).fill('Example')
  const scenarios = page.getByRole('group', {name:'Assignment scenario',exact:true,includeHidden:true})
  const ncm = scenarios.getByRole('radio', {name:'Scenario 1 - Nurse Case Manager present',exact:true,includeHidden:true})
  const assignScenario = scenarios.getByRole('radio', {name:'Scenario 2 - Assign NCM after approval',exact:true,includeHidden:true})
  const attended = scenarios.getByRole('button', {name:'Use attended flow',exact:true,includeHidden:true})
  assert.equal(await scenarios.getByRole('radio').count(), 2)
  assert.equal(await ncm.isChecked(), false)
  assert.equal(await assignScenario.isChecked(), false)
  assert.equal(await assignScenario.isDisabled(), false)
  assert.equal(await attended.isDisabled(), true)
  await page.getByText('No scenario selected means the existing attended workflow.', {exact:false}).waitFor()
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
  assert.equal(await ncm.isDisabled(), true)
  assert.equal(await assignScenario.isDisabled(), true)
  assert.equal(await attended.isDisabled(), true)
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
  assert.doesNotMatch(await page.locator('.outcome').innerText(), /icasemanager_approval/)
  assert.equal(await attachmentSource.innerText(), 'Local document · synthetic-selected.eml')
  assert.equal(await chooseDocument.isEnabled(), true)
  for (const stage of ['all', 'assign', 'unity']) {
    await page.getByLabel('Stage', {exact:true}).selectOption(stage)
    await ncm.check()
    await page.getByRole('button', {name:'Run selected stage'}).click()
    const expectedSteps = [
      ...(stage==='assign'?[]:['resolve_attachment','run_unity','record_assignment']),
      ...(stage==='unity'?[]:['skip_icasemanager_approval_ncm_present','complete_assignment']),
    ].join(' → ')
    await page.getByText(expectedSteps, {exact:true}).waitFor()
    await page.getByText('Process completed', {exact:true}).waitFor()
    assert.equal(await page.getByRole('dialog').count(), 0)
    const outcome = await page.locator('.outcome').innerText()
    assert.doesNotMatch(outcome, /await_icasemanager_approval/)
    if (stage === 'unity') assert.doesNotMatch(outcome, /skip_icasemanager_approval|complete_assignment/)
    else assert.match(outcome, /skip_icasemanager_approval_ncm_present → complete_assignment/)
  }
  await attended.click()
  assert.equal(await ncm.isChecked(), false)
  assert.equal(await assignScenario.isChecked(), false)
  await page.getByLabel('Stage', {exact:true}).selectOption('assign')
  await page.getByRole('button', {name:'Run selected stage'}).click()
  await page.getByRole('dialog').waitFor()
  await page.getByRole('button', {name:'Yes · approved',exact:true}).click()
  await page.getByText('Process completed', {exact:true}).waitFor()
  assert.match(await page.locator('.outcome').innerText(), /await_icasemanager_approval → complete_assignment/)
  // Scenario 2 keeps approval and requires real NCM/claimant operator inputs.
  await assignScenario.check()
  await page.getByLabel('NCM full name *', {exact:true}).waitFor()
  await page.getByLabel('First name *', {exact:true}).fill('')
  await page.getByRole('button', {name:'Validate fields'}).click()
  await page.getByRole('alert').filter({hasText:'claimantFirst, ncm'}).waitFor()
  await page.getByLabel('First name *', {exact:true}).fill('Invented')
  await page.getByLabel('NCM full name *', {exact:true}).fill('Synthetic Nurse')
  for (const stage of ['all','assign','unity']) {
    await page.getByLabel('Stage', {exact:true}).selectOption(stage)
    await page.getByRole('button', {name:'Run selected stage'}).click()
    if(stage!=='unity') {
      await page.getByRole('dialog').waitFor()
      assert.equal(await assignScenario.isDisabled(), true)
      await page.getByRole('button', {name:'Yes · approved',exact:true}).click()
    }
    const expectedSteps = [
      ...(stage==='assign'?[]:['resolve_attachment','run_unity','record_assignment']),
      ...(stage==='unity'?[]:['await_icasemanager_approval','assign_ncm','complete_assignment']),
    ].join(' → ')
    await page.getByText(expectedSteps, {exact:true}).waitFor()
    await page.getByText('Process completed', {exact:true}).waitFor()
    if(stage==='unity') assert.doesNotMatch(await page.locator('.outcome').innerText(), /assign_ncm|complete_assignment/)
  }
  await page.getByLabel('Stage', {exact:true}).selectOption('assign')
  await page.getByRole('button', {name:'Run selected stage'}).click()
  await page.getByRole('dialog').waitFor()
  await page.getByRole('button', {name:'No · stop',exact:true}).click()
  await page.getByText('Process stopped', {exact:true}).waitFor()
  assert.doesNotMatch(await page.locator('.outcome').innerText(), /assign_ncm|complete_assignment/)
  await attended.click()
  await useExports.click()
  await page.getByText('RRS export folder · exactly one exported attachment required', {exact:true}).waitFor()

  // Synthetic bridge spy: verify the actual UI passes only the append-only option.
  await page.addInitScript(({fixture}) => {
    window.__startCalls = []
    window.pywebview = {api:{
      async initialize(){return {...fixture,state:{status:'idle',busy:false,stage:'',elapsed:0,prompt:null,result:null,error:'',warnings:[],attachment:{source:'rrs',filename:''}}}},
      async get_state(){return {status:'idle',busy:false,stage:'',elapsed:0,prompt:null,result:null,error:'',warnings:[],attachment:{source:'rrs',filename:''}}},
      start(...args){window.__startCalls.push(args);return new Promise(resolve=>{window.__finishStart=()=>resolve({ok:true})})},
    }}
  }, {fixture})
  await page.goto(`http://127.0.0.1:${server.address().port}/`)
  await page.getByRole('button', {name:'Run selected stage'}).waitFor()
  assert.equal(await ncm.isChecked(), false) // Reload never persists the scenario.
  await ncm.check()
  await page.getByRole('button', {name:'Run selected stage'}).click()
  await page.waitForFunction(()=>window.__startCalls.length===1)
  assert.equal(await ncm.isDisabled(), true)
  assert.equal(await attended.isDisabled(), true) // Also locked during pending bridge replies.
  let calls = await page.evaluate(()=>window.__startCalls)
  assert.equal(calls[0].length, 6)
  assert.deepEqual(calls[0].slice(1), ['all',true,'',true,false])
  assert.deepEqual(Object.keys(calls[0][0]).sort(), Object.keys(fixture.defaults).sort())
  await page.evaluate(()=>window.__finishStart())
  await page.waitForFunction(()=>!document.querySelector('input[value="ncm-present"]').disabled)
  await attended.click()
  await page.getByRole('button', {name:'Run selected stage'}).click()
  await page.waitForFunction(()=>window.__startCalls.length===2)
  calls = await page.evaluate(()=>window.__startCalls)
  assert.deepEqual(calls[1].slice(1), ['all',true,'',false,false])
  await page.evaluate(()=>window.__finishStart())
  await page.waitForFunction(()=>!document.querySelector('input[value="assign-ncm"]').disabled)
  await assignScenario.check()
  await page.getByRole('button', {name:'Run selected stage'}).click()
  await page.waitForFunction(()=>window.__startCalls.length===3)
  calls = await page.evaluate(()=>window.__startCalls)
  assert.deepEqual(calls[2].slice(1), ['all',true,'',false,true])
  assert.equal(await ncm.isChecked(), false)
  assert.equal(await assignScenario.isDisabled(), true)
  await page.evaluate(()=>window.__finishStart())
  assert.deepEqual(errors, [])
  const result = {mode:'synthetic browser mock and bridge spy',checks:['PDF/MSG/EML file type help','choose original synthetic MSG then EML and show filename/source','clear to RRS export folder','Assign attachment guidance','selection retained through validation and runs','attachment controls disabled while busy','grouped form editing','shared schema length metadata','multiline textarea','1001 and 32767 characters preserved including whitespace and suffix after validation','32768 explicitly rejected without truncation','ordinary inputs retain 1000 limit','validate preview','blocking accessible confirm','Escape cannot dismiss','decline stopped reason','unity completed','two enabled native scenario radios','attended initial and reset behavior','NCM All/Assign skip-only steps and Unity unchanged','scenario controls locked while busy or bridge reply pending','append-only exclusive bridge boolean mapping','scenario not persisted after reload','scenario2 Assign claimant and NCM requirements and markers','scenario2 All/Assign approval then NCM before RRS; Unity unchanged','scenario2 decline has no downstream steps','all navigation intercepted to local server'],pageErrors:errors}
  await writeFile(join(evidence, 'browser-smoke.json'), JSON.stringify(result,null,2)+'\n')
  console.log(JSON.stringify(result,null,2))
} finally {
  if(context)await context.close()
  await new Promise(resolve=>server.close(resolve))
  assert.ok(scratch.startsWith(here) && scratch.includes('.browser-smoke-'))
  await rm(scratch,{recursive:true,force:true,maxRetries:10,retryDelay:200})
}
