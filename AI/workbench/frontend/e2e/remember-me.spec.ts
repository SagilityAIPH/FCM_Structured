import {test, expect} from '@playwright/test'

test('Bedrock opt-in starts unchecked and saved key/model are restored visibly and forgotten', async ({page}) => {
  await page.setViewportSize({width: 480, height: 600})
  await page.goto('/?preview=1')
  await page.getByRole('button', {name: 'Settings', exact: true}).click()
  const remember = page.getByRole('checkbox', {name: 'Remember on this computer (Bedrock)'})
  await expect(remember).not.toBeChecked()
  const key = page.getByRole('textbox', {name: 'Bedrock API key'})
  const model = page.getByRole('textbox', {name: 'Model ID'})
  await expect(key).toHaveAttribute('type', 'password')
  await key.fill('obviously-fake-test-key')
  await model.fill('obviously-fake-restored-model')
  await remember.check()
  await page.getByRole('button', {name: 'Save settings'}).click()
  const forget = page.getByRole('button', {name: 'Forget saved Bedrock key and model'})
  await expect(forget).toBeVisible()
  await expect(remember).not.toBeChecked()
  await expect(model).toHaveValue('obviously-fake-restored-model')
  await expect(page.locator('body')).not.toContainText('obviously-fake-test-key')
  // Simulate reopening Settings against the restored bridge state.
  await page.getByRole('button', {name: 'Settings', exact: true}).click()
  await page.getByRole('button', {name: 'Settings', exact: true}).click()
  await expect(page.getByRole('textbox', {name: 'Model ID'})).toHaveValue('obviously-fake-restored-model')
  await expect(page.getByRole('checkbox', {name: 'Remember on this computer (Bedrock)'})).not.toBeChecked()
  await expect(page.getByRole('button', {name: 'Forget saved Bedrock key and model'})).toBeVisible()
  await page.getByRole('button', {name: 'Forget saved Bedrock key and model'}).click()
  await expect(page.getByRole('button', {name: 'Forget saved Bedrock key and model'})).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})

test('restored model and pending check are visible without exposing the key', async ({page}) => {
  await page.setViewportSize({width: 480, height: 600})
  await page.goto('/?preview=1')
  await page.evaluate(async () => {
    const url = '/src/lib/preview.ts'
    const {previewAPI} = await import(url) as typeof import('../src/lib/preview')
    const getState = previewAPI.get_state
    const restored = {...(await getState()).settings, model: 'obviously-fake-restored-model'}
    previewAPI.get_state = async () => ({...await getState(), key_remembered: true,
      remembered_model_needs_test: true, settings: restored})
  })
  await page.getByRole('button', {name: 'Settings', exact: true}).click()
  await expect(page.getByRole('textbox', {name: 'Model ID'})).toHaveValue('obviously-fake-restored-model')
  await expect(page.getByText('Restored model needs a connection check', {exact: false})).toBeVisible()
  await expect(page.getByRole('textbox', {name: 'Bedrock API key'})).toHaveValue('')
  await expect(page.getByRole('checkbox', {name: 'Remember on this computer (Bedrock)'})).not.toBeChecked()
  await expect(page.getByRole('button', {name: 'Forget saved Bedrock key and model'})).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})

test('CMS opt-in starts unchecked and saved-sign-in control forgets', async ({page}) => {
  await page.setViewportSize({width: 480, height: 600})
  await page.goto('/?preview=1')
  await page.evaluate(async () => {
    const url = '/src/lib/preview.ts'
    const {previewAPI} = await import(url) as typeof import('../src/lib/preview')
    const getState = previewAPI.get_state
    let remembered = false
    let answered = false
    previewAPI.get_state = async () => ({...await getState(), memory_only: true, cms_remembered: remembered,
      pending_prompt: answered ? null : {id: 'fake', kind: 'credentials', title: 'CMS sign-in required', message: 'Enter credentials.'}})
    previewAPI.answer_prompt = async (_id, answer) => {
      if (answer && typeof answer === 'object') remembered = answer.remember
      answered = true
      return true
    }
    previewAPI.forget_credential = async name => { if (name === 'cms') remembered = false; return true }
  })
  const banner = page.getByRole('status', {name: 'Action required', exact: true})
  const remember = banner.getByRole('checkbox', {name: 'Remember on this computer (CMS)'})
  await expect(remember).not.toBeChecked()
  await banner.getByRole('textbox', {name: 'CMS username'}).fill('obviously-fake-user')
  await banner.getByRole('textbox', {name: 'CMS password'}).fill('obviously-fake-password')
  await remember.check()
  await banner.getByRole('button', {name: 'Continue to CMS'}).click()
  const forget = page.getByRole('button', {name: 'Forget saved CMS sign-in'})
  await expect(forget).toBeVisible()
  await expect(page.locator('body')).not.toContainText('obviously-fake-password')
  await forget.click()
  await expect(forget).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})
