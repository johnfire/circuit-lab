import { defineConfig } from '@playwright/test';

process.env.CIRCUIT_EXPECTED_BUILD ||= 'local';

/** Only the disposable loopback identity/API/Mailpit stack, never production. */
export default defineConfig({
  testDir: './tests', testMatch: ['**/*.identity.ts', '**/*.staging.ts'], workers: 1, timeout: 120000,
  outputDir: 'test-results/identity', use: { baseURL: 'https://127.0.0.1:8447', actionTimeout: 10000, navigationTimeout: 20000, ignoreHTTPSErrors: true },
  webServer: { command: 'node scripts/identity-browser-proxy.mjs', url: 'https://127.0.0.1:8447',
    ignoreHTTPSErrors: true, reuseExistingServer: false },
});
