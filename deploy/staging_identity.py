"""Configure reviewed OAuth clients inside the staging-only Keycloak realm."""

import json
import urllib.parse
import urllib.request
from typing import Any, cast

from deploy.identity_checks import NoRedirect
from deploy.mcp_identity_configuration import oauth_additions


class RealmAdmin:
    def __init__(self, endpoint: str, password: str) -> None:
        if endpoint not in {'http://127.0.0.1:8114', 'http://127.0.0.1:8104'}:
            raise ValueError('Use a fixed Circuit Lab loopback identity port')
        self.endpoint = endpoint
        self.opener = urllib.request.build_opener(NoRedirect())
        form = urllib.parse.urlencode({'client_id': 'admin-cli', 'grant_type': 'password',
                                       'username': 'circuit-bootstrap', 'password': password})
        request = urllib.request.Request(
            endpoint + '/auth/realms/master/protocol/openid-connect/token', form.encode(),
            {'Content-Type': 'application/x-www-form-urlencoded'})
        with self.opener.open(request, timeout=15) as response:
            self.token = str(json.load(response)['access_token'])

    def request(self, path: str, body: object = None, method: str = 'GET') -> Any:
        request = urllib.request.Request(
            self.endpoint + '/auth/admin/realms/circuit-lab' + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'},
            method=method)
        with self.opener.open(request, timeout=15) as response:
            payload = response.read()
        return json.loads(payload) if payload else None

    def find_client(self, client: str) -> str | None:
        clients = self.request('/clients?' + urllib.parse.urlencode({'clientId': client}))
        return str(clients[0]['id']) if clients else None

    def require_client(self, client: str) -> str:
        identifier = self.find_client(client)
        if not identifier:
            raise ValueError(f'Staging Keycloak client is missing: {client}')
        return identifier

    def ensure_client(self, definition: dict[str, object]) -> str:
        client = str(definition['clientId'])
        existing = self.find_client(client)
        if existing:
            return existing
        self.request('/clients', definition, 'POST')
        return self.require_client(client)


def configure_scopes(admin: RealmAdmin, scopes: list[dict[str, object]]) -> dict[str, str]:
    existing = {scope['name']: scope['id'] for scope in admin.request('/client-scopes')}
    for scope in scopes:
        if scope['name'] not in existing:
            admin.request('/client-scopes', scope, 'POST')
    return {scope['name']: scope['id'] for scope in admin.request('/client-scopes')}


def configure_resource_roles(admin: RealmAdmin, resource: str) -> None:
    management = admin.require_client('realm-management')
    client_path = '/clients/' + resource
    account = admin.request(client_path + '/service-account-user')['id']
    roles = [admin.request('/clients/' + management + '/roles/' + role)
             for role in ('view-users', 'view-events')]
    admin.request('/users/' + account + '/role-mappings/clients/' + management, roles, 'POST')
    admin.request(client_path + '/scope-mappings/clients/' + management, roles, 'POST')


def configure_workbench(admin: RealmAdmin, scope_ids: dict[str, str],
                        additions: dict[str, object]) -> None:
    web_client = '/clients/' + admin.require_client('circuit-lab-web')
    current = {mapper['name'] for mapper in admin.request(web_client + '/protocol-mappers/models')}
    for mapper in cast(list[dict[str, object]], additions['protocolMappers']):
        if mapper['name'] not in current:
            admin.request(web_client + '/protocol-mappers/models', mapper, 'POST')
    for scope in cast(list[str], additions['addDefaultClientScopes']):
        admin.request(web_client + '/default-client-scopes/' + scope_ids[scope], method='PUT')


def configure_identity(endpoint: str, origin: str, password: str, resource_secret: str,
                       client: str) -> None:
    admin = RealmAdmin(endpoint, password)
    additions = oauth_additions(origin, 'http://127.0.0.1:8124/callback', client)
    scope_ids = configure_scopes(admin, cast(list[dict[str, object]], additions['clientScopes']))
    reviewed, resource = cast(list[dict[str, object]], additions['clients'])
    resource['secret'] = resource_secret
    configure_resource_roles(admin, admin.ensure_client(resource))
    admin.ensure_client(reviewed)
    web_additions = cast(dict[str, dict[str, object]], additions['existingClientAdditions'])
    configure_workbench(admin, scope_ids, web_additions['circuit-lab-web'])
    print('Isolated staging OAuth and lifecycle checks configured', flush=True)
