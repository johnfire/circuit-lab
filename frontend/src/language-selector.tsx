import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import { saveAccountLanguage } from './account-language.ts';
import { activeLocale, selectLanguage } from './localization.ts';
import { LANGUAGES, supportedLocale } from './locale-preference';

export function LanguageSelector({ hosted }: { hosted: boolean }) {
  const { t, i18n } = useTranslation();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    if (hosted) void saveAccountLanguage(activeLocale()).then(() => {
      if (active) setFailed(false);
    }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [hosted, i18n.resolvedLanguage]);
  return <div className="language-choice"><label className="language-selector">{t('common.language')}
    <select value={activeLocale()} onChange={event => {
      const selected = supportedLocale(event.target.value);
      if (selected) selectLanguage(selected);
    }}>{Object.entries(LANGUAGES).map(([code, language]) =>
      <option key={code} value={code} lang={code}>{language.name}</option>)}</select>
  </label>{failed && <span role="status" className="language-notice">{t('common.account_language_unavailable')}</span>}</div>;
}
