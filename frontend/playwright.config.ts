import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',
  use: { baseURL: 'http://127.0.0.1:8011', headless: true },
  webServer: {
    command: '../.venv/bin/uvicorn backend.application:app --app-dir .. --host 127.0.0.1 --port 8011',
    url: 'http://127.0.0.1:8011/api/health',
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
});
