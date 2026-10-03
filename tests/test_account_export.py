"""Account data export never leaks another identity or their simulation journal."""

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.account_export import own_audit_events, own_profile
from backend.application import app
from deploy.prepare_identity import quote_environment


def test_audit_export_filters_other_accounts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audit = tmp_path / 'audit.jsonl'
    audit.write_text('\n'.join(json.dumps(event) for event in [
        {'actor': 'user:alice', 'outcome': 'passed'}, {'actor': 'user:bob', 'outcome': 'failed'}]))
    monkeypatch.setenv('CIRCUIT_AUDIT_PATH', str(audit))
    assert own_audit_events('user:alice') == [{'actor': 'user:alice', 'outcome': 'passed'}]
    assert own_audit_events('user:nobody') == []


def test_empty_audit_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('CIRCUIT_AUDIT_PATH', str(tmp_path / 'missing'))
    assert own_audit_events('user:alice') == []


@pytest.mark.parametrize('profile', [{'sub': 'bob'}, [], {'sub': 'alice', 'email': 'alice@example.invalid'}])
def test_profile_subject_is_bound_to_gateway(profile: object, monkeypatch: pytest.MonkeyPatch) -> None:
    from starlette.requests import Request
    monkeypatch.setenv('CIRCUIT_PUBLIC_URL', 'https://circuit-lab.christopherrehm.de')
    request = Request({'type': 'http', 'headers': [(b'x-circuit-access-token', b'test-only-token')]})
    request.state.actor = 'user:alice'
    with patch('backend.account_export.urllib.request.urlopen',
               return_value=io.BytesIO(json.dumps(profile).encode())):
        if isinstance(profile, dict) and profile.get('sub') == 'alice':
            assert own_profile(request) == profile
        else:
            with pytest.raises(ValueError):
                own_profile(request)


def test_workbench_route_is_protected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv('CIRCUIT_PUBLIC_URL', 'https://circuit-lab.christopherrehm.de')
    monkeypatch.setenv('CIRCUIT_PROXY_TOKEN', 'test-only-account-token-1234567890123456')
    (tmp_path / 'index.html').write_text('<title>Circuit Lab</title>')
    monkeypatch.setattr('backend.application.frontend_path', tmp_path)
    client = TestClient(app, base_url='http://localhost')
    assert client.get('/workbench').status_code == 403
    response = client.get('/workbench', headers={
        'X-Circuit-Proxy-Token': 'test-only-account-token-1234567890123456',
        'X-Circuit-Actor': 'alice'})
    assert response.status_code == 200
    assert 'Circuit Lab' in response.text


def test_account_download_requires_gateway_and_own_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('CIRCUIT_PUBLIC_URL', 'https://circuit-lab.christopherrehm.de')
    monkeypatch.setenv('CIRCUIT_PROXY_TOKEN', 'test-only-account-token-1234567890123456')
    client = TestClient(app, base_url='http://localhost')
    assert client.get('/api/account/export').status_code == 403
    headers = {'X-Circuit-Proxy-Token': 'test-only-account-token-1234567890123456',
               'X-Circuit-Actor': 'alice', 'X-Circuit-Access-Token': 'test-token'}
    with patch('backend.account_export.own_profile', return_value={'sub': 'alice'}):
        response = client.get('/api/account/export', headers=headers)
    assert response.status_code == 200
    assert response.json()['profile'] == {'sub': 'alice'}
    assert 'attachment' in response.headers['Content-Disposition']
    with patch('backend.account_export.own_profile', side_effect=ValueError('identity mismatch')):
        assert client.get('/api/account/export', headers=headers).status_code == 503
    assert client.get('/api/health').status_code == 200


@pytest.mark.parametrize('credential', ['hello$world', "single'quote", r'back\slash', ''])
def test_environment_quotes_are_literal(credential: str) -> None:
    quoted = quote_environment(credential)
    assert quoted.startswith("'") and quoted.endswith("'")
    assert '$' not in credential or '$' in quoted


def test_multiline_environment_credentials_are_rejected() -> None:
    with pytest.raises(ValueError):
        quote_environment('one\nTWO=bad')
