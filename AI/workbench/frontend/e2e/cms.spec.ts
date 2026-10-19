import { test, expect, type Page } from '@playwright/test'
import type { Outcome, WorkflowResult } from '../src/types'

const result = (outcome: Outcome): WorkflowResult => ({outcome, reason: {completed: 'completed', ended: 'incomplete', stopped: 'tire_customer_open_tcm', failed: 'exception'}[outcome], customer: 'SYNTHETIC RESOLVED EMPLOYER', cases: [1, 2].map(i => ({cms_caseNum: `SYNTHETIC-CASE-${i}`, caseType: 'TCM', case_status: 'Open', message: 'SYNTHETIC '.repeat(30) + 'Unbroken'.repeat(50)})), missing_fields: ['Synthetic required field'], stages: ['CAPTURE', 'CMS'], payloads: {}, error: outcome === 'failed' ? {stage: 'CMS', type: 'SyntheticError', message: 'Synthetic failure message'} : undefined})
async function publish(page: Page, value: WorkflowResult) {
  await page.evaluate(async value => {
    const url = '/src/lib/preview.ts'
    const {previewAPI} = await import(url) as typeof import('../src/lib/preview')
    await previewAPI.set_workflow_result(value)
  }, value)
}

test('CMS outcomes are distinct and cases stack without overflow at 480px', async ({page}) => {
  await page.setViewportSize({width: 480, height: 900})
  await page.goto('/?preview=1')
  const section = page.getByRole('region', {name: 'CMS Customer Search'})
  const colors = []
  for (const outcome of ['completed', 'ended', 'stopped', 'failed'] as const) {
    await publish(page, result(outcome))
    const status = section.locator(`[data-outcome="${outcome}"]`)
    await expect(status).toBeVisible()
    colors.push(await status.evaluate(el => getComputedStyle(el).backgroundColor))
    await expect(section.getByText('SYNTHETIC RESOLVED EMPLOYER', {exact: true})).toHaveCount(1)
    await expect(section.getByRole('article')).toHaveCount(2)
    await expect(section.getByRole('table')).toHaveCount(0)
    expect(await section.evaluate(el => [el, ...el.querySelectorAll('*')].every(node => node.scrollWidth <= node.clientWidth + 1))).toBeTruthy()
    expect(await section.locator('dl').first().evaluate(el => getComputedStyle(el).flexDirection)).toBe('column')
    if (outcome === 'stopped') {
      await expect(status).toContainText('not completed')
      await expect(status).toContainText('send an email and handle this referral manually')
      await expect(status).toContainText('tire_customer_open_tcm')
    }
    if (outcome === 'ended') await expect(status).toContainText('Synthetic required field')
    if (outcome === 'failed') for (const text of ['CMS', 'SyntheticError', 'Synthetic failure message']) await expect(status).toContainText(text)
  }
  expect(new Set(colors).size).toBe(4)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})

for (const choice of ['Yes', 'No', 'Acknowledge'] as const) test(`live ${choice} prompt is above page, exits compact, and returns answer`, async ({page}) => {
  await page.setViewportSize({width: 480, height: 600})
  await page.goto('/?preview=1')
  await page.getByRole('button', {name: 'Enter compact mode'}).click()
  await expect(page.locator('.compact-shell')).toHaveClass(/is-compact/)
  await page.evaluate(async choice => {
    const url = '/src/lib/preview.ts'
    const {previewAPI} = await import(url) as typeof import('../src/lib/preview')
    const getState = previewAPI.get_state
    let pending = true
    previewAPI.get_state = async () => ({...await getState(), busy: true, pending_prompt: pending ? {id: 'synthetic-prompt', kind: choice === 'Acknowledge' ? 'notify' : 'confirm', title: 'Synthetic live prompt', message: 'Synthetic operator instruction. '.repeat(50)} : null})
    previewAPI.answer_prompt = async (id, answer) => {
      document.documentElement.dataset.promptAnswer = JSON.stringify({id, answer})
      pending = false
      return true
    }
  }, choice)
  const dialog = page.getByRole('status', {name: 'Action required', exact: true})
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText('Synthetic live prompt')
  await expect(page.locator('.compact-shell')).not.toHaveClass(/is-compact/)
  expect(await dialog.evaluate(el => {
    const rect = el.getBoundingClientRect()
    return rect.top < 100 && rect.left >= 0 && rect.right <= innerWidth && rect.bottom <= innerHeight
  })).toBeTruthy()
  await dialog.getByRole('button', {name: choice, exact: true}).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.locator('html')).toHaveAttribute('data-prompt-answer', JSON.stringify({id: 'synthetic-prompt', answer: choice !== 'No'}))
})
