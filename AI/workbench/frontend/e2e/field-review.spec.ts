import {test, expect} from '@playwright/test'

const scratch = 'C:/Users/Administrator/AppData/Local/hermes/profiles/omniroute/cache/scratch/referrals-json'

test('Final Code empty copy and compact attention-first groups retain drafts', async ({page}) => {
  await page.setViewportSize({width: 480, height: 650})
  await page.goto('/?preview=1')
  await page.evaluate(async () => {
    const url = '/src/lib/preview.ts'
    const {previewAPI} = await import(url) as typeof import('../src/lib/preview')
    const getState = previewAPI.get_state
    previewAPI.get_state = async () => ({...await getState(), memory_only: true,
      referral_notice: 'Saved Referrals\\2030-01-02_030405_Example-Synthetic.json'})
    const getDocument = previewAPI.get_document
    previewAPI.get_document = async id => {
      const doc = await getDocument(id)
      if (id === 'example-2') {
        doc.sent_characters = doc.total_characters
        doc.validation!.provider_missing_fields = [['City']]
        doc.validation!.confirmation_required = ['Provider 1 / Appointment is in the past']
        doc.validation!.appointments = [{provider_index: 1, appointment_date: 'Synthetic appointment date', reasons: ['Appointment is in the past'], can_confirm: true, confirmed: false}]
      }
      return doc
    }
  })
  await expect(page.getByText('Waiting for RRS capture', {exact: true})).toBeVisible()
  await expect(page.getByText('Select Start to capture referral text from RRS for review.')).toBeVisible()
  await expect(page.locator('.save-row')).toContainText('Awaiting RRS capture')
  await expect(page.getByRole('status').filter({hasText: 'Saved Referrals\\2030-01-02_030405_Example-Synthetic.json'})).toBeVisible()
  await expect(page.getByText('Import a document.')).toHaveCount(0)
  await page.evaluate(async () => {
    const url = '/src/lib/preview.ts'
    const {previewAPI} = await import(url) as typeof import('../src/lib/preview')
    const getState = previewAPI.get_state
    previewAPI.get_state = async () => ({...await getState(), memory_only: false})
  })
  await page.getByRole('button', {name: 'Load examples'}).click()
  await page.getByLabel('Current document').selectOption('example-2')
  await page.evaluate(async () => {
    const url = '/src/lib/preview.ts'
    const {previewAPI} = await import(url) as typeof import('../src/lib/preview')
    const getState = previewAPI.get_state
    previewAPI.get_state = async () => ({...await getState(), memory_only: true})
  })
  await expect(page.getByRole('heading', {name: 'Referral Intake'})).toBeVisible()
  const claimant = page.locator('.field-section').filter({has: page.getByRole('button', {name: /Claimant Information/})})
  const claim = page.getByRole('button', {name: /Claim Information/})
  const provider = page.getByRole('button', {name: /Provider 1/})
  await expect(claim).toHaveAttribute('aria-expanded', 'false')
  await expect(claimant.getByRole('button', {name: /Claimant Information/})).toContainText('Missing 1')
  await expect(provider).toContainText('Needs confirmation 1')
  await expect(page.locator('.validation-strip')).toContainText('1 missing required · 1 appointment check needs confirmation')
  await expect(page.getByLabel('Claimant Information / Customer Name')).toHaveClass(/has-gap/)
  await expect(page.getByLabel('Provider 1 / City')).toHaveClass(/has-gap/)
  await expect(page.getByLabel('Provider 1 / Appointment Date')).toHaveClass(/needs-confirmation/)
  await expect(page.getByText('Appointment needs confirmation', {exact: true})).toBeVisible()
  await expect(page.getByText(/Only 0 of/)).toHaveCount(0)
  await expect(page.locator('.save-row')).toContainText('Review fields before approving')
  await page.getByLabel('Claimant Information / Customer Name').scrollIntoViewIfNeeded()
  await page.screenshot({path: `${scratch}/fc-ui-attention-open.png`})
  const customer = page.getByLabel('Claimant Information / Customer Name')
  await customer.fill('Synthetic correction')
  await claimant.getByRole('button', {name: /Claimant Information/}).focus()
  await page.keyboard.press('Enter')
  await expect(claimant.getByRole('button', {name: /Claimant Information/})).toHaveAttribute('aria-expanded', 'false')
  await expect(customer).toBeHidden()
  await expect(page.getByRole('button', {name: 'Save field changes (1)'})).toBeEnabled()
  await expect(page.locator('html')).toHaveAttribute('data-unsaved', 'true')
  await page.screenshot({path: `${scratch}/fc-ui-attention-collapsed.png`})
  await page.getByRole('button', {name: 'Collapse all'}).click()
  await expect(provider).toHaveAttribute('aria-expanded', 'false')
  await expect(provider).toContainText('Needs confirmation 1')
  await expect(claimant.getByRole('button', {name: /Claimant Information/})).toContainText('Missing 1')
  await page.getByRole('button', {name: 'Expand all'}).click()
  await expect(customer).toHaveValue('Synthetic correction')
  await expect(claim).toHaveAttribute('aria-expanded', 'true')
  await page.screenshot({path: `${scratch}/fc-ui-groups-expanded.png`})
  await page.getByRole('button', {name: 'Save field changes (1)'}).click()
  await expect(page.locator('.save-row')).toContainText('Review fields before approving')
  await expect(page.getByText('NEXT STEP: Passed', {exact: true})).toBeVisible()
  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('button', {name: 'Confirm this appointment'}).click()
  await expect(page.getByRole('status').filter({hasText: 'Appointment confirmed for this run.'})).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})

test('Reader retains import and Excel copy, genuine truncation warning', async ({page}) => {
  await page.goto('/?preview=1')
  await expect(page.getByText('Ready when you are')).toBeVisible()
  await expect(page.getByText('Import a document. Extraction, address checks, and daily Excel output run automatically.')).toBeVisible()
  await page.evaluate(async () => {
    const url = '/src/lib/preview.ts'
    const {previewAPI} = await import(url) as typeof import('../src/lib/preview')
    const original = previewAPI.get_document
    previewAPI.get_document = async id => ({...await original(id), sent_characters: 100, total_characters: 8042})
  })
  await page.getByRole('button', {name: 'Load examples'}).click()
  await expect(page.getByText(/Only 100 of 8,042 characters were sent to Bedrock/)).toBeVisible()
  await expect(page.getByText(/Increase the document limit in Settings/)).toBeVisible()
  await expect(page.locator('.save-row')).toContainText('Saved to daily Excel')
})
