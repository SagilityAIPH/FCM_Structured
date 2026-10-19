import {test, expect} from '@playwright/test'

test('narrow pinned CMS sign-in is masked, reachable, and clears attention', async ({page}) => {
  await page.setViewportSize({width: 480, height: 600})
  await page.goto('/?preview=1')
  await page.evaluate(async () => {
    const url = '/src/lib/preview.ts'
    const {previewAPI} = await import(url) as typeof import('../src/lib/preview')
    const original = previewAPI.get_state
    let pending = true
    previewAPI.get_state = async () => ({...await original(), memory_only: true, compact: true,
      pending_prompt: pending ? {id: 'synthetic-credential-prompt', kind: 'credentials', title: 'CMS sign-in required', message: 'Enter credentials to continue.'} : null})
    previewAPI.answer_prompt = async (id, answer) => {
      if (id !== 'synthetic-credential-prompt' || !answer || typeof answer !== 'object' || answer.remember !== false) throw new Error('Invalid answer')
      // Only report that the answer was received; never mirror entered values into DOM.
      document.documentElement.dataset.promptAnswered = 'yes'
      pending = false
      return true
    }
  })
  const banner = page.getByRole('status', {name: 'Action required', exact: true})
  await expect(banner).toBeVisible()
  await expect(page.getByRole('status', {name: 'Operator action required'})).toBeVisible()
  await expect(page.locator('.compact-shell')).not.toHaveClass(/is-compact/)
  expect(await banner.evaluate(el => { const rect = el.getBoundingClientRect(); return rect.top < 90 && rect.right <= innerWidth && rect.bottom <= innerHeight })).toBeTruthy()
  const password = banner.getByRole('textbox', {name: 'CMS password'})
  await expect(password).toHaveAttribute('type', 'password')
  await page.screenshot({path: 'C:/Users/Administrator/AppData/Local/hermes/profiles/omniroute/cache/scratch/cms-pinned-credential-prompt.png'})
  await banner.getByRole('textbox', {name: 'CMS username'}).fill('synthetic-user')
  await password.fill('synthetic-secret')
  await expect(banner).not.toContainText('synthetic-secret')
  await banner.getByRole('button', {name: 'Continue to CMS'}).click()
  await expect(page.locator('html')).toHaveAttribute('data-prompt-answered', 'yes')
  await expect(banner).not.toContainText('CMS sign-in required')
  await expect(page.getByRole('status', {name: 'Operator action required'})).toBeVisible()
})

test('pending attended review stays above scrolling form with visible actions', async ({page}) => {
  await page.setViewportSize({width: 480, height: 600})
  await page.goto('/?preview=1')
  await page.evaluate(async () => {
    const url = '/src/lib/preview.ts'
    const {previewAPI} = await import(url) as typeof import('../src/lib/preview')
    const original = previewAPI.get_state
    previewAPI.get_state = async () => ({...await original(), memory_only: true, pending_review: {id: 'synthetic-review', document_id: 'synthetic-document'}})
  })
  const banner = page.getByRole('status', {name: 'Action required', exact: true})
  await expect(banner).toBeVisible()
  await page.screenshot({path: 'C:/Users/Administrator/AppData/Local/hermes/profiles/omniroute/cache/scratch/cms-pinned-review.png'})
  await expect(banner.getByRole('button', {name: 'Cancel run'})).toBeVisible()
  await expect(banner.getByRole('button', {name: 'Approve and continue'})).toBeDisabled()
  expect(await banner.evaluate(el => el.getBoundingClientRect().top < 90)).toBeTruthy()
})
