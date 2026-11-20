export const LANGUAGES = { de: { name: 'Deutsch', direction: 'ltr' }, en: { name: 'English', direction: 'ltr' } };
export const LANGUAGE_COOKIE = 'circuit-language';

export function supportedLocale(candidate) {
  return candidate === 'de' || candidate === 'en' ? candidate : null;
}

export function resolveLocale(preference, browserLanguages) {
  const explicit = supportedLocale(preference);
  if (explicit) return explicit;
  for (const language of browserLanguages) {
    const supported = supportedLocale(language.toLowerCase().split('-')[0]);
    if (supported) return supported;
  }
  return 'en';
}

export function readLanguageCookie(cookies) {
  const entry = cookies.split(';').map(cookie => cookie.trim()).find(cookie => cookie.startsWith(LANGUAGE_COOKIE + '='));
  return supportedLocale(entry?.slice(LANGUAGE_COOKIE.length + 1));
}

export function languageCookie(language, secure) {
  return `${LANGUAGE_COOKIE}=${language}; Path=/; Max-Age=31536000; SameSite=Lax${secure ? '; Secure' : ''}`;
}
