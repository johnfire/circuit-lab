import { defineConfig } from '@playwright/test';

/** Separate real-database suite; its pytest fixture supplies an isolated PostgreSQL instance. */
export default defineConfig({
  testDir: './tests', testMatch: '**/*.projects.ts', workers: 1,
  use: { baseURL: 'http://127.0.0.1:8013', headless: true },
  webServer: {
    command: '../.venv/bin/uvicorn backend.application:app --app-dir .. --host 127.0.0.1 --port 8013',
    url: 'http://127.0.0.1:8013/api/health', reuseExistingServer: false, timeout: 30000,
  },
});
