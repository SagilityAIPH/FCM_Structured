import { test, expect } from '@playwright/test'

for (const mode of ['text detail', 'soft render response']) {
  test(`no-preview state keeps field review usable: ${mode}`, async ({page}) => {
    await page.goto('/?preview=1')
    await page.evaluate(async (mode) => {
      // Reuse only the explicitly synthetic browser fixtures.
      const previewModule = '/src/lib/preview.ts' // Vite URL, not a filesystem import.
      const { previewAPI } = await import(previewModule) as typeof import('../src/lib/preview')
      const getDocument = previewAPI.get_document
      previewAPI.get_document = async (id: string) => {
        const doc = await getDocument(id)
        if (mode === 'text detail') {
          doc.is_pdf = false
          doc.preview_message = 'No preview — referral text captured from RRS'
        }
        return doc
      }
      previewAPI.render_page = async () => ({available: false, message: 'No preview — referral text captured from RRS'})
    }, mode)
    await page.getByRole('button', {name: 'Load examples'}).click()
    await page.getByRole('button', {name: 'PDF', exact: true}).click()
    await expect(page.getByText('No preview — referral text captured from RRS', {exact: true})).toBeVisible()
    await expect(page.getByText('Rendering page…')).toHaveCount(0)
    await expect(page.getByRole('alert')).toHaveCount(0)
    await page.getByRole('button', {name: 'Fields', exact: true}).click()
    const field = page.getByLabel('Claimant Information / First Name', {exact: true})
    await field.fill('Synthetic edited')
    await page.getByRole('button', {name: 'Save field changes (1)'}).click()
    await expect(field).toHaveValue('Synthetic edited')
    await expect(page.getByRole('button', {name: 'Save field changes', exact: true})).toBeDisabled()
  })
}
