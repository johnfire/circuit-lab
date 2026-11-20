import { languageCookie, readLanguageCookie, resolveLocale, supportedLocale } from './language-preference.js';

/** Only these formatting tags are understood; translation text never becomes arbitrary HTML. */
function renderMessage(element, text) {
  const fragment = document.createDocumentFragment();
  let parent = fragment;
  for (const token of text.split(/(<\/?(?:em|strong)>|<br\s*\/?>)/g)) {
    if (/^<(em|strong)>$/.test(token)) {
      const child = document.createElement(token.slice(1, -1));
      parent.append(child); parent = child;
    } else if (/^<\/(em|strong)>$/.test(token)) parent = parent.parentNode || fragment;
    else if (/^<br\s*\/?>$/.test(token)) parent.append(document.createElement('br'));
    else parent.append(document.createTextNode(token));
  }
  const decorations = [...element.children].filter(child => child.getAttribute('aria-hidden') === 'true');
  const leading = decorations.filter(child => child.classList.contains('status-dot'));
  const trailing = decorations.filter(child => !child.classList.contains('status-dot'));
  element.replaceChildren(...leading, fragment, ...trailing);
}

function applyLanguage(language, messages) {
  document.documentElement.lang = language;
  document.documentElement.dir = 'ltr';
  for (const element of document.querySelectorAll('[data-i18n]')) {
    const text = messages[element.dataset.i18n];
    if (typeof text === 'string') renderMessage(element, text);
  }
  for (const attribute of ['aria-label', 'content']) {
    for (const element of document.querySelectorAll('[data-i18n-' + attribute + ']')) {
      const text = messages[element.getAttribute('data-i18n-' + attribute)];
      if (typeof text === 'string') element.setAttribute(attribute, text);
    }
  }
  document.querySelector('#language').value = language;
  document.querySelector('#language').disabled = false;
  for (const link of document.querySelectorAll('a[href^="/oauth2/start"]')) {
    const destination = new URL(link.href);
    destination.searchParams.set('ui_locales', language);
    destination.searchParams.set('kc_locale', language);
    link.href = destination.pathname + destination.search;
  }
}

async function initializeLandingLanguage() {
  const languages = ['en', 'de'];
  const dictionaries = await Promise.all(languages.map(async language => {
    const response = await fetch('/locales/' + language + '/landing.json');
    if (!response.ok) throw new Error('Landing translations unavailable');
    return response.json();
  }));
  let preference = null;
  try { preference = readLanguageCookie(document.cookie); } catch { /* Storage may be blocked. */ }
  applyLanguage(resolveLocale(preference, navigator.languages), dictionaries[resolveLocale(preference, navigator.languages) === 'de' ? 1 : 0]);
  document.querySelector('#language').addEventListener('change', event => {
    const selected = supportedLocale(event.target.value);
    if (!selected) return;
    try { document.cookie = languageCookie(selected, location.protocol === 'https:'); } catch { /* In-memory choice still works. */ }
    applyLanguage(selected, dictionaries[selected === 'de' ? 1 : 0]);
  });
}

void initializeLandingLanguage().catch(() => {
  document.querySelector('#language').disabled = true;
});
