/** Share the native identity selector's choice with the landing page and workbench. */
void import('/language-preference.js').then(({ supportedLocale, readLanguageCookie, languageCookie }) => {
  function remember(language) {
    if (language) {
      try { document.cookie = languageCookie(language, location.protocol === 'https:'); }
      catch { /* Native identity localization continues without browser storage. */ }
    }
  }

  function synchronizeIdentityLanguage() {
    const destination = new URL(location.href);
    let preference = null;
    try { preference = readLanguageCookie(document.cookie); } catch { /* Storage is optional. */ }
    const requested = supportedLocale(destination.searchParams.get('kc_locale')) || preference;
    const current = supportedLocale(document.documentElement.lang.split('-')[0]);
    const nativeChoice = [...document.querySelectorAll('a[href]')].find(link =>
      new URL(link.href).searchParams.get('kc_locale') === requested);
    if (requested && nativeChoice && destination.pathname.endsWith('/openid-connect/auth')) {
      location.replace(nativeChoice.href);
      return;
    }
    if (requested && requested !== current && !destination.searchParams.has('kc_locale')) {
      destination.searchParams.set('kc_locale', requested);
      destination.searchParams.set('ui_locales', requested);
      location.replace(destination);
      return;
    }
    remember(current);
    if (document.body.dataset.pageId === 'account') void fetch('/locales/' + (current || 'en') + '/identity.json')
      .then(response => response.ok ? response.json() : null).then(messages => {
        if (!messages || typeof messages.title !== 'string' || typeof messages.loading !== 'string') return;
        document.title = messages.title;
        const loading = document.querySelector('#loading-text');
        if (loading) loading.textContent = messages.loading;
        document.querySelector('meta[name=description]')?.setAttribute('content', messages.description);
        const spinner = document.querySelector('.keycloak__loading-container [role=progressbar]');
        spinner?.setAttribute('aria-label', messages.contents);
        spinner?.setAttribute('aria-valuetext', messages.loading);
      }).catch(() => undefined);
    new MutationObserver(() => remember(supportedLocale(document.documentElement.lang.split('-')[0])))
      .observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
  }

  document.addEventListener('click', event => {
    if (!(event.target instanceof Element)) return;
    const link = event.target.closest('a[href]');
    if (link) remember(supportedLocale(new URL(link.href).searchParams.get('kc_locale')));
  });
  document.addEventListener('change', event => {
    if (!(event.target instanceof HTMLInputElement) && !(event.target instanceof HTMLSelectElement)) return;
    if (['locale', 'attributes.locale'].includes(event.target.name) || event.target.id === 'locale')
      remember(supportedLocale(event.target.value));
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', synchronizeIdentityLanguage);
  else synchronizeIdentityLanguage();
}).catch(() => { /* Losing the display-preference bridge must not break sign-in. */ });
