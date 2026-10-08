import { defineConfig } from '@playwright/test'
export default defineConfig({testDir:'./e2e',timeout:30000,
  use:{baseURL:'http://127.0.0.1:5182',viewport:{width:480,height:900},channel:'msedge'},
  webServer:{command:'npm run dev -- --port 5182 --strictPort',url:'http://127.0.0.1:5182',reuseExistingServer:false},
  outputDir:'../test-results'})
