# German and English localization

Implemented locally on 2026-11-20. This document describes source behavior; it
is not evidence of a pushed revision, passing GitHub run or live deployment.

## Language behavior

A manual choice wins over the browser's ordered language preferences. Regional
variants such as de-DE and en-GB match their base language. If no supported
language matches, use English. Without JavaScript the public page stays English.
The top selector uses native language names, an accessible label, and a host-only
SameSite=Lax cookie (Secure over HTTPS). Blocked cookies still permit switching
on the current page, but cannot remember a preference across navigation.

The React provider changes presentation without remounting the editor, rerunning
simulations, altering local drafts or creating server revisions. Numeric input
and electrical serialization remain canonical; displayed measurements and dates
use the selected locale. Circuit IDs, pin/net names, models, manufacturer names,
unit symbols, BOM columns, netlists, JSON formats and user/AI-authored text remain
unchanged. Historical reports without message references retain their original
text rather than rewriting simulation evidence.

## Translation sources

- `locales/{en,de}/messages.json`: shared app, catalogue, diagnostics and checklist
  messages. Frontend keys are typed from English. Both catalogues must have the
  same keys and interpolation arguments.
- `locales/{en,de}/landing.json`: only public landing text and metadata.
- `locales/{en,de}/identity.json`: account shell title/loading text; native login,
  account and email translations are inherited from the pinned Keycloak image.
- `circuits/pcb/fab-guide.de.md`: German readable PCB guide. English guide and all
  machine-readable export files remain canonical.

Use stable keys and whole messages with named `{{arguments}}`. Do not translate
CSS classes, DOM IDs, protocol values or electrical expressions. Display-only
catalogue getters read messages by stable library ID; generated indexes are not
edited or duplicated. Stored checks and warnings keep their original English
fields and add structured message references, which render in either language.
Unexpected service failures have a localized summary and preserve technical
response details. External/authored content is not machine-translated at runtime.

The shared resolver is `frontend/public/language-preference.js`; the landing,
React app and identity bridge use it. The identity proxy accepts only de/en
locale hints. The app synchronizes the chosen language through the authenticated
person's Keycloak account API, preserving all other profile fields and custom
attributes. Updates are serialized, subject-bound and audited with correlation
IDs. A failed account update leaves the browser usable and shows a notice about
email-language persistence.

## Adding another language

Add complete catalogues, readable documents, registry/direction metadata and
resource imports before enabling its selector option. Extend the bounded backend
locale options, identity realm locales, proxy hint allowlist and public publisher
allowlist together. Supply Keycloak bundles if that language is not built in.
Update key/placeholder/catalogue completeness checks and run native mail tests.
For Arabic use `rtl` for the document while retaining LTR/bidi isolation on
schematics, plots, netlists and identifiers. Circuit geometry must not change.
French, Polish and Arabic are not advertised as shipped translations yet.

## Verification

Run the normal lint/type/build, unit, Python, database and browser suites. New
checks cover browser/manual precedence, English fallback, catalogue parity,
structured diagnostic serialization, numeric formatting, readable exports,
unchanged circuit data, blocked storage and technical-attribute invariants.
`npm run test:locale-mutations --prefix frontend` must detect broken precedence, ordering, fallback,
allowed languages and secure-cookie flags.

The native browser fixture is HTTPS on **127.0.0.1:8447 only**. It uses fake
credentials, separate local Docker projects, PostgreSQL and Mailpit; upstream
redirects outside that loopback origin are rejected. No production account or
outbound email service is involved. Start the usual application/identity test
containers, then configure the native fixture:

```bash
docker compose -p circuit-lab-ci --env-file deploy/identity-test.env --env-file deploy/identity-language-test.env -f compose.yaml -f compose.projects.yaml up -d --build --wait
docker compose -p circuit-lab-identity-ci --env-file deploy/identity-test.env --env-file deploy/identity-language-test.env -f compose.identity.yaml -f compose.staging-identity.yaml up -d --build --wait
python3 -m deploy.prepare_identity_language_tests
npm run test:identity-languages --prefix frontend
```

The suite completes signup, verification mail, workbench language changes,
persisted account preference, settings and reset completion in both languages.
It asserts mail subjects, plain text and HTML. The same suite exercises the
bilingual staging release flow: protected routes, simulation, private save and
account export. CI retains failure traces. Native platform translations remain
owned by Keycloak and are checked on the exact pinned version.

## Local verification record — 2026-11-20 to 2026-11-21

- Python: 475 tests passed; 86.77% coverage, including real PostgreSQL/browser
  collaboration and ngspice checks. Ruff and mypy passed (83 source files).
- Frontend: 42 unit tests and 27 browser tests passed, including desktop/mobile
  axe checks. Production build and lint passed. Final mobile layout guard is
  included in the localization acceptance tests; all four acceptance tests passed
  again after the header adjustment.
- Native account/release fixture: four flows passed across German and English,
  using real Keycloak, PostgreSQL, OAuth2 Proxy, Mailpit and restricted workers.
  Final account metadata, mail and reset checks passed again on November 21.
- Five resolver mutations were killed: manual precedence, browser ordering,
  English fallback, supported languages and Secure cookie handling.
- Python runtime audit: no known vulnerabilities. npm: no high/critical findings;
  nine moderate development-tool findings remain. Build warns about the single
  bundle size; catalogues ship with the app so switching needs no network request.
- German/English desktop and German 390px mobile screenshots were inspected;
  translated labels wrap and circuit symbols retain their technical identity.

GitHub CI, VPS identity migration, live staging and production checks remain
release-time gates. No push or deployment was performed for this implementation.
