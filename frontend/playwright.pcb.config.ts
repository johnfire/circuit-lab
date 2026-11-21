import { defineConfig } from '@playwright/test';

if (!process.env.CIRCUIT_PCB_SOCKET) throw new Error('Provide the isolated PCB worker socket');
export default defineConfig({
  testDir: './tests', testMatch: '**/*.pcb.ts', workers: 1, timeout: 120000,
  use: { baseURL: 'http://127.0.0.1:8014', headless: true },
  webServer: { env: { ...process.env, CIRCUIT_PUBLIC_URL: '', CIRCUIT_DATABASE_URL: '', CIRCUIT_WORKER_SOCKET: '' },
    command: '../.venv/bin/uvicorn backend.application:app --app-dir .. --host 127.0.0.1 --port 8014',
    url: 'http://127.0.0.1:8014/api/health', reuseExistingServer: false, timeout: 30000 },
});
