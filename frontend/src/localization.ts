import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';
import english from '../../locales/en/messages.json' with { type: 'json' };
import german from '../../locales/de/messages.json' with { type: 'json' };
import { languageCookie, LANGUAGES, readLanguageCookie, resolveLocale, type Locale } from './locale-preference.ts';

function initialLocale(): Locale {
  if (typeof document === 'undefined') return 'en';
  try { return resolveLocale(readLanguageCookie(document.cookie), navigator.languages); }
  catch { return resolveLocale(null, navigator.languages); }
}

export const localization = i18next.createInstance();
void localization.use(initReactI18next).init({
  lng: initialLocale(), fallbackLng: 'en', supportedLngs: Object.keys(LANGUAGES),
  resources: { en: { translation: english }, de: { translation: german } },
  keySeparator: false, initAsync: false, interpolation: { escapeValue: false },
});

export type MessageKey = keyof typeof english;
export function translate(key: MessageKey, values: Record<string, string | number> = {}): string {
  return localization.t(key, values);
}

export function activeLocale(): Locale { return localization.resolvedLanguage === 'de' ? 'de' : 'en'; }

export function translatedLabels<Kind extends string>(labels: Record<Kind, MessageKey | string>): Record<Kind, string> {
  return Object.defineProperties({ ...labels }, Object.fromEntries(
    Object.entries(labels).map(([kind, key]) => [kind, {
      enumerable: true, get: () => localization.exists(String(key)) ? localization.t(String(key)) : String(key),
    }]),
  ));
}

export function updateDocumentLanguage(): void {
  document.documentElement.lang = activeLocale();
  document.documentElement.dir = LANGUAGES[activeLocale()].direction;
  document.title = translate('common.workbench_title');
  document.querySelector('meta[name=description]')?.setAttribute('content', translate('common.workbench_description'));
}

export function selectLanguage(language: Locale): void {
  try { document.cookie = languageCookie(language, window.location.protocol === 'https:'); }
  catch { /* The in-memory preference still works when browser storage is blocked. */ }
  void localization.changeLanguage(language);
  updateDocumentLanguage();
}
