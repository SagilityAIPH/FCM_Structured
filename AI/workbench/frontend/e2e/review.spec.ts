import {test, expect} from '@playwright/test'

async function openSyntheticReview(page: import('@playwright/test').Page) {
  await page.setViewportSize({width: 480, height: 650})
  await page.goto('/?preview=1')
  await page.getByRole('button', {name: 'Load examples'}).click()
  await page.evaluate(async () => {
    const url = '/src/lib/preview.ts'
    const {previewAPI} = await import(url) as typeof import('../src/lib/preview')
    const getState = previewAPI.get_state
    let pending = true
    previewAPI.get_state = async () => ({...await getState(), memory_only: true, pending_review: pending ? {id: 'synthetic-review', document_id: 'example-1'} : null})
    previewAPI.answer_review = async (id, approve) => {
      document.documentElement.dataset.reviewAnswer = JSON.stringify({id, approve})
      pending = false
      return true
    }
  })
  await expect(page.getByRole('group', {name: 'Attended review actions'})).toBeVisible()
}

test('Reader preview has no attended review controls', async ({page}) => {
  await page.goto('/?preview=1')
  await page.getByRole('button', {name: 'Load examples'}).click()
  await expect(page.getByRole('group', {name: 'Attended review actions'})).toHaveCount(0)
})

test('Final Code review stays docked, saves edits, and answers by review UUID', async ({page}) => {
  await openSyntheticReview(page)
  const actions = page.getByRole('group', {name: 'Attended review actions'})
  const approve = actions.getByRole('button', {name: 'Approve and continue'})
  const cancel = actions.getByRole('button', {name: 'Cancel run'})
  await expect(approve).toBeEnabled()
  await expect(cancel).toBeEnabled()
  const bounds = await actions.boundingBox()
  expect(bounds && bounds.y + bounds.height <= 650).toBeTruthy()
  await page.getByLabel('Claimant Information / First Name', {exact: true}).fill('Synthetic edit')
  await expect(approve).toBeDisabled()
  await expect(actions).toContainText('Save field changes before approving.')
  await page.getByRole('button', {name: /Save field changes/}).click()
  await expect(approve).toBeEnabled()
  await approve.click()
  await expect(page.locator('html')).toHaveAttribute('data-review-answer', JSON.stringify({id: 'synthetic-review', approve: true}))
  await expect(actions).toHaveCount(0)
})

test('Answer submission disables both actions until the bridge responds', async ({page}) => {
  await openSyntheticReview(page)
  await page.evaluate(async () => {
    const url = '/src/lib/preview.ts'
    const {previewAPI} = await import(url) as typeof import('../src/lib/preview')
    const answer = previewAPI.answer_review
    previewAPI.answer_review = async (id, approve) => {
      await new Promise<void>(resolve => { (window as typeof window & {releaseReview?: () => void}).releaseReview = resolve })
      return answer(id, approve)
    }
  })
  const actions = page.getByRole('group', {name: 'Attended review actions'})
  await actions.getByRole('button', {name: 'Approve and continue'}).click()
  await expect(actions.getByRole('button', {name: 'Approve and continue'})).toBeDisabled()
  await expect(actions.getByRole('button', {name: 'Cancel run'})).toBeDisabled()
  await page.evaluate(() => (window as typeof window & {releaseReview?: () => void}).releaseReview?.())
  await expect(actions).toHaveCount(0)
})

test('Cancel ends the run even with unsaved edits and only answers once', async ({page}) => {
  await openSyntheticReview(page)
  const actions = page.getByRole('group', {name: 'Attended review actions'})
  await page.getByLabel('Claimant Information / First Name', {exact: true}).fill('Synthetic edit')
  await expect(actions.getByRole('button', {name: 'Approve and continue'})).toBeDisabled()
  await actions.getByRole('button', {name: 'Cancel run'}).click()
  await expect(page.locator('html')).toHaveAttribute('data-review-answer', JSON.stringify({id: 'synthetic-review', approve: false}))
  await expect(actions).toHaveCount(0)
})
