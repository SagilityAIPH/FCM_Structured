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
    executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    headless: true, viewport: { width: 560, height: 900 },
  })
  const page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`http://127.0.0.1:${server.address().port}/?mock=1`)
  await page.getByLabel('Claim number *', {exact:true}).fill('SYNTHETIC-BROWSER-001')
  await page.getByLabel('Employer / customer *', {exact:true}).fill('Synthetic Widgets')
  await page.getByLabel('First name *', {exact:true}).fill('Invented')
  await page.getByLabel('Last name *', {exact:true}).fill('Example')
  await page.getByRole('button', {name:'Validate fields'}).click()
  await page.getByText('Derived values', {exact:true}).waitFor()
  await page.getByRole('button', {name:'Run selected stage'}).click()
  await page.getByRole('dialog').waitFor()
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
  assert.deepEqual(errors, [])
  const result = {mode:'synthetic browser mock',checks:['grouped form editing','validate preview','blocking accessible confirm','Escape cannot dismiss','decline stopped reason','unity completed'],pageErrors:errors}
  await writeFile(join(evidence, 'browser-smoke.json'), JSON.stringify(result,null,2)+'\n')
  console.log(JSON.stringify(result,null,2))
} finally {
  if(context)await context.close()
  await new Promise(resolve=>server.close(resolve))
  assert.ok(scratch.startsWith(here) && scratch.includes('.browser-smoke-'))
  await rm(scratch,{recursive:true,force:true})
}
