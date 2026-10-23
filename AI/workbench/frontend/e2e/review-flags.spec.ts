import {test, expect} from '@playwright/test'

for (const memoryOnly of [false, true]) {
  test(`${memoryOnly ? 'Final Code' : 'Reader'} flags field and collapsed group without blocking`, async ({page}) => {
    await page.goto('/?preview=1')
    await page.evaluate(async mode => {
      const url = '/src/lib/preview.ts'
      const {previewAPI} = await import(url) as typeof import('../src/lib/preview')
      const getState = previewAPI.get_state
      previewAPI.get_state = async () => ({...await getState(), memory_only: mode})
      const getDocument = previewAPI.get_document
      previewAPI.get_document = async id => ({...await getDocument(id), review_flags: [
        {field: 'Zip', provider_index: null, kind: 'disagreement', reason: 'Form text says: 2001-01-02', reader_value: '2001-01-02'},
        {field: 'Zip', provider_index: null, kind: 'format', reason: 'Not a valid ZIP'},
        {field: 'Provider Zip', provider_index: 0, kind: 'format', reason: 'Not a valid ZIP'},
      ]})
    }, memoryOnly)
    await page.getByRole('button', {name: 'Load examples'}).click()
    const claimant = page.getByRole('button', {name: /Claimant Information/})
    const provider = page.getByRole('button', {name: /Provider 1/})
    await page.getByRole('button', {name: 'Collapse all'}).click()
    await expect(claimant).toContainText('Review 2')
    await expect(provider).toContainText('Review 1')
    await claimant.click()
    await expect(page.getByText('Form text says: 2001-01-02')).toBeVisible()
    await expect(page.getByText('Not a valid ZIP').first()).toBeVisible()
    await expect(page.getByLabel('Claimant Information / Zip')).toHaveClass(/needs-confirmation/)
    await expect(page.locator('.validation-strip')).toBeVisible()
  })
}
