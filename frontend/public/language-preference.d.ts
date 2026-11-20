export type Locale = 'de' | 'en';
export const LANGUAGES: Record<Locale, { name: string; direction: 'ltr' }>;
export const LANGUAGE_COOKIE: string;
export function supportedLocale(candidate: unknown): Locale | null;
export function resolveLocale(preference: unknown, browserLanguages: readonly string[]): Locale;
export function readLanguageCookie(cookies: string): Locale | null;
export function languageCookie(language: Locale, secure: boolean): string;
