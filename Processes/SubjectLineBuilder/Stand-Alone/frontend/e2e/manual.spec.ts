import {test,expect} from '@playwright/test'
import {execFileSync} from 'node:child_process'
import path from 'node:path'

test('Excel rows load into editable fields without starting automation',async({page})=>{
  await page.addInitScript(()=>{
    const state={status:'idle',stage:'Ready',progress:0,prompt:'',error:'',busy:false,elapsed:0,review_id:0}
    ;(window as any).pywebview={api:{initialize:async()=>({schema:[{title:'Claim',fields:[{key:'claimNumber',label:'Claim number',required:true,date:false}]}],defaults:{claimNumber:''},state}),
      get_state:async()=>state,
      open_excel:async()=>({ok:true,filename:'Input.xlsx',rows:[{row:2,label:'Row 2 | First'},{row:3,label:'Row 3 | Second'}]}),
      select_excel_row:async(row:number)=>({ok:true,data:{claimNumber:row===2?'000123':'000456'},warning:'Required: Employer / customer'}),
      save_excel_template:async()=>({ok:true}),
      start:async()=>{throw new Error('Import must never start automation')}}}
  })
  await page.goto('/')
  await page.getByRole('button',{name:'Open Excel',exact:true}).click()
  await expect(page.getByLabel('Claim number')).toHaveValue('')
  await page.getByRole('button',{name:'Load row',exact:true}).click()
  await expect(page.getByLabel('Claim number')).toHaveValue('000123')
  await expect(page.getByText('Row 2 loaded.',{exact:false})).toContainText('Required: Employer / customer')
  await page.getByLabel('Claim number').fill('EDITED')
  await page.getByLabel('Referral row').selectOption('3')
  await expect(page.getByLabel('Claim number')).toHaveValue('EDITED')
  await page.getByRole('button',{name:'Load row',exact:true}).click()
  await expect(page.getByLabel('Claim number')).toHaveValue('000456')
  await page.getByRole('button',{name:'Save template',exact:true}).click()
  await expect(page.getByText('Template saved.',{exact:false})).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('full manual form fits the narrow workbench and keeps actions visible',async({page})=>{
  const fixture=JSON.parse(execFileSync(path.resolve('../../../../.venv-bedrock/Scripts/python.exe'),['-c',
    "import sys,json; sys.path.insert(0,'../../Deploy-Ready'); from manual_flow import schema,defaults; print(json.dumps({'schema':schema(),'defaults':defaults()}))"],{encoding:'utf8'}))
  await page.addInitScript((fixture)=>{
    const state={status:'idle',stage:'Enter the referral details',progress:0,prompt:'',error:'',busy:false,elapsed:0,review_id:0}
    ;(window as any).pywebview={api:{initialize:async()=>({...fixture,state}),get_state:async()=>state}}
  },fixture)
  await page.goto('/')
  await expect(page.locator('.field-section')).toHaveCount(5)
  await expect(page.locator('input[name=providerZip]')).toHaveCount(1)
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(480)
  await page.getByRole('button',{name:'Help',exact:true}).click()
  await expect(page.getByRole('heading',{name:'How to use'})).toBeVisible()
  await expect(page.getByRole('button',{name:'Start builder'})).toBeInViewport()
  await page.getByRole('button',{name:'Fields',exact:true}).click()
  await expect.poll(()=>page.locator('.form-scroll').evaluate(el=>el.scrollTop)).toBe(0)
  await page.screenshot({path:'../test-results/subject-line-builder-form.png'})
})
test('manual edits survive appended panels and Create requires review',async({page})=>{
  await page.addInitScript(()=>{
    const state={status:'idle',stage:'Ready',progress:0,prompt:'',error:'',busy:false,elapsed:0,review_id:0}
    ;(window as any).pywebview={api:{initialize:async()=>({schema:[{title:'Customer and claim',fields:[{key:'claimNumber',label:'Claim number',required:true,date:false}]}],defaults:{claimNumber:''},state}),
      get_state:async()=>state,start:async(data:any)=>{if(!data.claimNumber)return{ok:false,error:'Required: Claim number'};Object.assign(state,{busy:true,status:'review',progress:85,prompt:'Review RRS then Create',review_id:1});return{ok:true}},
      proceed:async()=>{Object.assign(state,{busy:false,status:'completed',progress:100,prompt:''});return{ok:true}},stop:async()=>({ok:true})}}
  })
  await page.goto('/')
  await page.getByRole('button',{name:'Start builder'}).click()
  await expect(page.getByRole('alert')).toContainText('Required: Claim number')
  await page.getByLabel('Claim number').fill('SYNTHETIC-001')
  await page.getByRole('button',{name:'Help',exact:true}).click()
  await expect(page.getByRole('heading',{name:'How to use'})).toBeVisible()
  await page.getByRole('button',{name:'Fields',exact:true}).click()
  await expect(page.getByLabel('Claim number')).toHaveValue('SYNTHETIC-001')
  await expect(page.getByRole('button',{name:'Create in RRS'})).toHaveCount(0)
  await page.getByRole('button',{name:'Start builder'}).click()
  await expect(page.getByRole('button',{name:'Create in RRS'})).toBeVisible()
  await expect(page.getByLabel('Claim number')).toBeDisabled()
  await page.screenshot({path:'../test-results/subject-line-builder.png',fullPage:true})
  await page.getByRole('button',{name:'Create in RRS'}).click()
  await expect(page.getByText('Subject line created. The RRS window remains available.')).toBeVisible()
  await expect(page.getByRole('progressbar')).toHaveAttribute('value','100')
})
