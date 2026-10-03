"""Analytics stays on the public landing, behind a narrow explicit policy."""

from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ScriptParser(HTMLParser):
    """Read script configuration without relying on HTML whitespace."""

    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == 'script':
            self.scripts.append(dict(attrs))


def test_landing_tracker_is_deferred_and_privacy_configured() -> None:
    parser = ScriptParser()
    parser.feed((ROOT / 'frontend/public/landing.html').read_text())
    assert parser.scripts[0]['src'] == '/landing-analytics.js'
    tracker = parser.scripts[1]
    assert tracker['src'] == 'https://stats.christopherrehm.de/script.js'
    assert tracker['data-website-id'] == 'c85d3632-ce92-4753-9505-5be8c9ca13c4'
    assert tracker['data-domains'] == 'circuit-lab.christopherrehm.de'
    assert tracker['data-before-send'] == 'filterCircuitLabPageview'
    assert all('defer' in script for script in parser.scripts)
    for setting in ('do-not-track', 'exclude-search', 'exclude-hash'):
        assert tracker[f'data-{setting}'] == 'true'
    assert all(setting not in tracker for setting in ('data-performance', 'data-heatmap',
                                                     'data-replay'))


def test_workbench_has_no_analytics_script() -> None:
    markup = (ROOT / 'frontend/index.html').read_text()
    assert 'umami' not in markup.lower()
    assert 'landing-analytics' not in markup


def test_landing_has_visible_analytics_disclosure() -> None:
    markup = (ROOT / 'frontend/public/landing.html').read_text()
    assert 'without analytics' in markup
    assert 'Account IDs and URL query strings are not sent' in markup


def test_csp_allows_only_explicit_analytics_endpoints_without_inline_code() -> None:
    template = (ROOT / 'deploy/apache-oidc.conf.template').read_text()
    assert "script-src 'self' https://stats.christopherrehm.de/script.js;" in template
    assert "connect-src 'self' https://stats.christopherrehm.de/api/send;" in template
    assert 'unsafe-inline' not in template
    assert 'unsafe-eval' not in template
    assert '*.christopherrehm.de' not in template
