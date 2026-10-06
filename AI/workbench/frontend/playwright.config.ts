import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e', timeout: 30000, use: {baseURL: 'http://127.0.0.1:5179', viewport: {width: 464, height: 861}, channel: 'msedge'},
  webServer: {command: 'npm run dev -- --port 5179 --strictPort', url: 'http://127.0.0.1:5179', reuseExistingServer: false},
  outputDir: '../test-results',
})
