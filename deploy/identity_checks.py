"""Exercise real local-only OIDC services with disposable synthetic accounts."""

import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from http.client import HTTPMessage
from http.cookies import SimpleCookie
from pathlib import Path

PUBLIC = 'https://circuit-lab.christopherrehm.de'
IDENTITY = 'http://127.0.0.1:8104'
PROXY = 'http://127.0.0.1:8103'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Inspect each redirect rather than accidentally accessing production."""

    def redirect_request(self, *arguments: object, **keywords: object) -> None:
        return None


class LoginForm(HTMLParser):
    """Find only the native login form action, without browser scripting."""

    def __init__(self) -> None:
        super().__init__()
        self.action = ''

    def handle_starttag(self, tag: str, attributes: list[tuple[str, str | None]]) -> None:
        values = dict(attributes)
        if tag == 'form' and values.get('id') == 'kc-form-login':
            self.action = values.get('action') or ''


def request(url: str, data: bytes | None = None,
            headers: dict[str, str] | None = None,
            method: str | None = None) -> tuple[int, HTTPMessage, bytes]:
    """Never follow a URL onto the real service during integration testing."""
    if not url.startswith((IDENTITY + '/', PROXY + '/')):
        raise ValueError('Identity tests must remain on loopback')
    submitted = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    opener = urllib.request.build_opener(NoRedirect())
    try:
        response = opener.open(submitted, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, response.read()


def cookies(headers: HTTPMessage) -> str:
    """Forward secure test cookies explicitly over isolated loopback HTTP."""
    parsed = SimpleCookie()
    for value in headers.get_all('Set-Cookie', []):
        parsed.load(value)
    return '; '.join(name + '=' + value.value for name, value in parsed.items())


def admin_headers() -> dict[str, str]:
    """Use only deliberately public fixtures, never production credentials."""
    settings = dict(line.split('=', 1) for line in
                    Path('deploy/identity-test.env').read_text().splitlines()
                    if line and not line.startswith('#'))
    form = urllib.parse.urlencode({
        'client_id': 'admin-cli', 'grant_type': 'password',
        'username': 'circuit-bootstrap', 'password': settings['CIRCUIT_IDENTITY_ADMIN_PASSWORD']})
    status, _, body = request(IDENTITY + '/auth/realms/master/protocol/openid-connect/token',
                              form.encode(), {'Content-Type': 'application/x-www-form-urlencoded'})
    assert status == 200, 'Test administrator token unavailable'
    return {'Authorization': 'Bearer ' + json.loads(body)['access_token'],
            'Content-Type': 'application/json', 'X-Forwarded-Proto': 'https'}


def login(email: str, password: str) -> str:
    """Complete authorization code, PKCE, nonce, and secure-cookie exchange."""
    status, start_headers, _ = request(PROXY + '/oauth2/start?rd=%2Fworkbench')
    assert status == 302
    authorization = start_headers['Location']
    assert 'code_challenge_method=S256' in authorization and 'nonce=' in authorization
    status, form_headers, page = request(authorization.replace(PUBLIC, IDENTITY),
                                       headers={'X-Forwarded-Proto': 'https'})
    assert status == 200
    form = LoginForm()
    form.feed(page.decode())
    assert form.action, 'Native login form missing'
    submitted = urllib.parse.urlencode({'username': email, 'password': password})
    status, authenticated, _ = request(form.action.replace(PUBLIC, IDENTITY), submitted.encode(), {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Forwarded-Proto': 'https', 'Cookie': cookies(form_headers)})
    assert status == 302, 'Verified test login did not complete: ' + str(status)
    callback = authenticated['Location'].replace(PUBLIC, PROXY)
    assert '/oauth2/callback?' in callback and 'code=' in callback
    status, token_headers, _ = request(callback, headers={
        'X-Forwarded-Proto': 'https', 'Cookie': cookies(start_headers)})
    assert status == 302, 'Gateway rejected authorization response'
    session = cookies(token_headers)
    assert '__Host-circuit-lab' in session, 'Secure account session missing'
    return session


def main() -> None:
    """Create and remove only our synthetic local integration account."""
    headers = admin_headers()
    base = IDENTITY + '/auth/admin/realms/circuit-lab'
    status, _, body = request(base, headers=headers)
    assert status == 200
    realm = json.loads(body)
    assert realm['registrationAllowed'] and realm['verifyEmail'] and realm['resetPasswordAllowed']
    check_registration()
    email = 'integration-' + secrets.token_hex(6) + '@example.invalid'
    password = secrets.token_urlsafe(24)
    user = {'username': email, 'email': email, 'emailVerified': True, 'enabled': True,
            'firstName': 'Integration', 'lastName': 'Fixture',
            'credentials': [{'type': 'password', 'value': password, 'temporary': False}]}
    status, created, _ = request(base + '/users', json.dumps(user).encode(), headers)
    assert status == 201
    user_url = IDENTITY + urllib.parse.urlsplit(created['Location']).path
    try:
        session = login(email, password)
        status, _, body = request(PROXY + '/workbench', headers={'Cookie': session,
                               'X-Forwarded-Proto': 'https',
                               'X-Circuit-Actor': 'forged-other-account'})
        assert status == 200, ('Authenticated workbench unavailable: ' + str(status)
                               + ' ' + body.decode()[:160])
        check_own_export(session, user_url.rsplit('/', 1)[1])
        check_revoked_session(session, user_url, headers)
        print('Real OIDC exchange, protected workbench, and identity-bound export passed')
    finally:
        status, _, _ = request(user_url, headers=admin_headers(), method='DELETE')
        assert status == 204


def check_registration() -> None:
    """Public signup is reachable, but forged identity cannot open the workbench."""
    status, _, _ = request(PROXY + '/workbench', headers={'X-Circuit-Actor': 'forged'})
    assert status == 302
    status, headers, _ = request(PROXY + '/oauth2/start?rd=%2Fworkbench&prompt=create')
    assert status == 302 and 'prompt=create' in headers['Location']
    status, _, body = request(headers['Location'].replace(PUBLIC, IDENTITY),
                             headers={'X-Forwarded-Proto': 'https'})
    assert status == 200 and b'id="kc-register-form"' in body and b'name="email"' in body


def check_revoked_session(session: str, user_url: str, headers: dict[str, str]) -> None:
    """The next one-minute token refresh must reject a revoked identity session."""
    status, _, _ = request(user_url + '/logout', b'', headers)
    assert status == 204
    print('Checking revoked session after the configured one-minute refresh', flush=True)
    time.sleep(65)
    status, _, _ = request(PROXY + '/workbench', headers={
        'Cookie': session, 'X-Forwarded-Proto': 'https'})
    assert status in {302, 401, 403}, 'Revoked identity session retained workbench access'


def check_own_export(session: str, subject: str) -> None:
    """Verify gateway overwrites forged identity and exports only the owner."""
    headers = {'Cookie': session, 'X-Forwarded-Proto': 'https',
               'X-Circuit-Actor': 'forged-other-account',
               'X-Circuit-Access-Token': 'forged-access-token',
               'X-Circuit-Proxy-Token': 'forged-proxy-token'}
    status, _, report = request(PROXY + '/api/circuits/voltage_divider/simulate',
                                b'{}', dict(headers, **{'Content-Type': 'application/json'}))
    assert status == 200
    assert json.loads(report)['status'] == 'passed'
    status, _, exported = request(PROXY + '/api/account/export', headers=headers)
    assert status == 200, 'Identity-bound data export failed'
    account = json.loads(exported)
    assert account['profile']['sub'] == subject
    assert account['simulation_events']
    assert all(event['actor'] == 'user:' + subject for event in account['simulation_events'])


if __name__ == '__main__':
    main()
