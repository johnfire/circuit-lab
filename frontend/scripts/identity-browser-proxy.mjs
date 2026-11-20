import https from 'node:https';
import http from 'node:http';
import { readFile, mkdtemp } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const origin = 'https://127.0.0.1:8447';
const certificates = await mkdtemp(join(tmpdir(), 'circuit-identity-tls-'));
execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
  '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1',
  '-keyout', join(certificates, 'key.pem'), '-out', join(certificates, 'cert.pem')], { stdio: 'ignore' });
const publicFiles = new Set(['landing.html', 'theme.css', 'landing.css', 'favicon.svg',
  'landing-language.js', 'language-preference.js', 'landing-analytics.js']);

async function publicAsset(pathname) {
  const filename = pathname === '/' ? 'landing.html' : pathname.slice(1);
  if (publicFiles.has(filename)) return { body: await readFile('public/' + filename), filename };
  if (/^\/locales\/(en|de)\/(landing|identity)\.json$/.test(pathname))
    return { body: await readFile('..' + pathname), filename };
  return null;
}

function proxyToLoopback(request, response, pathname) {
  const mail = pathname.startsWith('/_stage/mail/');
  const port = mail ? 8056 : pathname.startsWith('/.well-known/') ? 8102 : pathname.startsWith('/auth/') ? 8104 : 8103;
  const path = mail ? request.url.replace('/_stage/mail/', '/') : request.url;
  const upstream = http.request({ hostname: '127.0.0.1', port, path, method: request.method,
    headers: { ...request.headers, host: '127.0.0.1:' + port,
      'x-forwarded-proto': 'https', 'x-forwarded-host': '127.0.0.1:8447' } }, forwarded => {
    const location = forwarded.headers.location;
    if (location && new URL(location, origin).origin !== origin) {
      forwarded.resume(); response.writeHead(502); response.end('External redirect rejected by isolated test proxy'); return;
    }
    response.writeHead(forwarded.statusCode || 502, forwarded.headers);
    forwarded.pipe(response);
  });
  upstream.on('error', () => { response.writeHead(502); response.end('Loopback test service unavailable'); });
  request.pipe(upstream);
}

const server = https.createServer({ key: await readFile(join(certificates, 'key.pem')),
  cert: await readFile(join(certificates, 'cert.pem')) }, async (request, response) => {
  try {
    const pathname = new URL(request.url, origin).pathname;
    if (/^\/auth\/(admin|realms\/master)(\/|$)/.test(pathname)) {
      response.writeHead(403); response.end('Administrative identity routes are private'); return;
    }
    const asset = await publicAsset(pathname);
    if (!asset) return proxyToLoopback(request, response, pathname);
    const extension = asset.filename.split('.').at(-1);
    const contentTypes = { js: 'text/javascript', css: 'text/css', html: 'text/html', json: 'application/json', svg: 'image/svg+xml' };
    response.writeHead(200, { 'Content-Type': contentTypes[extension] || 'text/plain' });
    response.end(asset.body);
  } catch { response.writeHead(500); response.end('Isolated test asset unavailable'); }
});
server.listen(8447, '127.0.0.1', () => process.stdout.write('Loopback identity browser proxy ready\n'));
