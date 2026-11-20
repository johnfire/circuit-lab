import type { Locale } from './locale-preference.ts';

let pendingSave: Promise<void> = Promise.resolve();

/** Serialize rapid changes so a slower earlier request cannot overwrite the latest choice. */
export function saveAccountLanguage(language: Locale): Promise<void> {
  pendingSave = pendingSave.catch(() => undefined).then(async () => {
    const response = await fetch('/api/account/language', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ language }), signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) throw new Error('Account language synchronization failed');
  });
  return pendingSave;
}
