"""Run inside the API container: verify hosted boundaries and all real recipes."""

import json
import os
import urllib.error
import urllib.request

from deploy.analog_container_checks import check_analog


def call(path: str, body: bytes | None = None, trusted: bool = True) -> object:
    """Exercise HTTP across the API-to-worker boundary, with traced AI identity."""
    headers = {'Content-Type': 'application/json'}
    if trusted:
        headers.update({'X-Circuit-Proxy-Token': os.environ['CIRCUIT_PROXY_TOKEN'],
                        'X-Circuit-Actor': 'ai-agent:container-tests'})
    request = urllib.request.Request('http://127.0.0.1:8000' + path, body, headers)
    with urllib.request.urlopen(request, timeout=25) as response:
        assert response.headers['X-Correlation-ID']
        return json.load(response)


def main() -> None:
    """Fail for proxy bypass, broken XSPICE, missing waveforms, or filesystem writes."""
    try:
        call('/api/circuits', trusted=False)
    except urllib.error.HTTPError as error:
        assert error.code == 403
    else:
        raise AssertionError('Hosted API accepted proxy bypass')
    catalog = call('/api/circuits')
    assert isinstance(catalog, list) and len(catalog) == 9
    for circuit in catalog:
        report = call('/api/circuits/' + circuit['id'] + '/simulate', b'{}')
        assert isinstance(report, dict) and report['signals'] and report['status'] == 'passed'
        print(circuit['id'] + ': passed')
    check_analog(call)
    try:
        with open('/app/container-write-probe', 'w'):
            pass
    except OSError:
        pass
    else:
        raise AssertionError('Application filesystem is writable')


if __name__ == '__main__':
    main()
