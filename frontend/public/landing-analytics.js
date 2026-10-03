/** Only anonymous landing-page views may reach the analytics collector. */
window.filterCircuitLabPageview = (eventType, payload) => {
  if (eventType !== 'event' || !payload || payload.name || payload.id
      || typeof payload.url !== 'string') {
    return false;
  }
  try {
    const visit = new URL(payload.url, window.location.origin);
    if (visit.origin !== 'https://circuit-lab.christopherrehm.de'
        || !['/', '/landing.html'].includes(visit.pathname)) {
      return false;
    }
    let referrerOrigin = '';
    if (payload.referrer) {
      const referrer = new URL(payload.referrer, visit.origin);
      if (['http:', 'https:'].includes(referrer.protocol) && referrer.origin !== visit.origin) {
        referrerOrigin = referrer.origin;
      }
    }
    return {
      website: 'c85d3632-ce92-4753-9505-5be8c9ca13c4',
      hostname: visit.hostname,
      language: payload.language,
      screen: payload.screen,
      title: 'Circuit Lab',
      url: visit.origin + '/',
      referrer: referrerOrigin,
    };
  } catch {
    return false;
  }
};
