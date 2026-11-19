import { defineConfig } from '@playwright/test';
import { homedir } from 'node:os';
import { join } from 'node:path';

const origin = 'https://staging.circuit-lab.christopherrehm.de';
const certificates = join(process.env.XDG_DATA_HOME || join(homedir(), '.local', 'share'),
  'circuit-lab', 'staging-tls');
const { STAGING_TLS_CERT, STAGING_TLS_KEY, STAGING_TLS_CERT_PATH, STAGING_TLS_KEY_PATH } = process.env;

if (Boolean(STAGING_TLS_CERT) !== Boolean(STAGING_TLS_KEY)) {
  throw new Error('Supply both staging TLS credentials');
}
const authentication = STAGING_TLS_CERT && STAGING_TLS_KEY ? {
  cert: Buffer.from(STAGING_TLS_CERT),
  key: Buffer.from(STAGING_TLS_KEY),
} : {
  certPath: STAGING_TLS_CERT_PATH || join(certificates, 'agent.pem'),
  keyPath: STAGING_TLS_KEY_PATH || join(certificates, 'agent.key'),
};

export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.staging.ts',
  outputDir: 'test-results/staging',
  workers: 1,
  timeout: 120_000,
  use: {
    baseURL: origin,
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
    clientCertificates: [{ origin, ...authentication }],
  },
});
