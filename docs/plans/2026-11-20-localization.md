# Circuit Lab localization plan

Date: 2026-11-20. Status: investigation complete; implementation proposed.
Target: a verified German/English release before Monday morning, 2026-11-23,
Europe/Berlin. This document does not claim implementation or deployment.

## Confirmed behavior

- Translate all existing user-facing pages, including the public landing,
  examples, schematic editor, observation/AC views, projects/sharing, account
  screens, verification/reset emails, warnings, errors and readable downloads.
- A visible, keyboard-accessible selector at the top offers Deutsch and English,
  with a translated Language/Sprache label. Use language names rather than flags.
- Chris's clarification supersedes an unconditional German first visit:
  use the browser's ordered language preferences on first visit, match regional
  variants such as de-DE/en-GB to supported base languages, and fall back to German
  when none match. Remember an explicit manual choice ahead of browser detection.
- Switching language updates the current workbench without reloading, resetting
  a circuit, clearing results, changing sharing, or creating a circuit revision.
- Translate component types: resistor = Widerstand, capacitor = Kondensator,
  inductor = Spule. Keep Circuit Lab, manufacturer/model names, R1/C1/U1, pin/net
  IDs, mathematical symbols, SI unit symbols, footprints and protocol fields stable.
- User-authored project names, notes and AI-authored free text remain as written.
- French, Polish and Arabic are future translations. Establish the necessary
  structure now; do not show incomplete languages in the production selector.

## Findings from the repository and live site

| Surface | Evidence | Consequence |
| --- | --- | --- |
| Public landing | `frontend/public/landing.html`; live root and sign-in inspected on November 20 | Static English HTML, separate from React; text, metadata, SVG description and accessibility labels need translation. |
| Workbench | `frontend/src/main.tsx`, `circuit-workbench.tsx`, `analog-workbench.tsx` | React 19/TypeScript; no existing translation dependency or locale provider. Text is distributed through controls, hooks and presentation helpers. |
| Types and catalogues | `schematic-model.ts`, `block-library.ts`, `part-library.ts`, `circuits/*-index.json`, `backend/circuit_catalog.py` | Translate display metadata by stable IDs; do not rewrite canonical electrical data or generated indexes independently. |
| Checks/errors | `backend/verification_checks.py`, `schematic_routes.py`, `support_checks.py`, frontend API clients | English sentences originate on both sides. Translating JSX alone leaves mixed-language results. |
| Downloads | `backend/kicad_routes.py`, `bring_up_sheet.py`, `circuits/pcb/fab-guide.md` | The first-power-on checklist, PCB guide and export warnings need localized rendering. |
| Identity | `deploy/circuit-lab-realm.json`, `login-proxy.yaml`, `Keycloak.Dockerfile` | Keycloak 26.8.0 is pinned; realm localization is not configured in source. OAuth2 Proxy currently allows only `prompt` overrides. |
| Public delivery | `deploy/deploy_release.py:publish_landing`, Apache configurations | Receiver copies a fixed list of public assets; new landing translation assets need explicit publication, compatible CSP and rollback. |
| Identity delivery | `deploy/README.md`, `compose.identity.yaml` | Keycloak is a separate stack. Realm import only initializes a missing realm, so changing JSON alone cannot update an existing deployment. |
| Existing verification | Frontend unit/Playwright suites and private staging signup/mail gate | Preserve existing assertions; make locale assumptions explicit and add both-language coverage. |

The design documents describe external AI through MCP, sharing one structured
circuit model with the browser. Localization belongs around that model, not
inside it. Older status paragraphs conflict with later activation notes; they
are historical evidence, not proof of today's deployment state.

Local Git inspection: `main`, one local commit ahead of `origin/main`
(`84029aa`, private staging gate); unrelated untracked `circuit-lab-kicad-test/`.
No production revision, account-console contents or live email behavior was
verified during this read-only browser inspection.

## Proposed structure

### 1. Shared messages and language selection

Adopt i18next with react-i18next for the workbench. Use stable semantic keys,
typed access, whole-message interpolation and plural rules. Avoid English
sentences as identifiers, sentence fragments and per-component language branches.
Set supported languages and German fallback explicitly; audit and lock package
versions before adoption.

Keep version-controlled UTF-8 JSON catalogues under `locales/de/` and
`locales/en/`, grouped by purpose: common, landing, workbench, observation,
projects, catalogue, diagnostics and documents. Frontend and Python readers
consume the same app-owned messages instead of maintaining duplicate translations.
Keep Keycloak's own account/email bundles native to Keycloak.

A single locale resolver defines manual preference > browser preferences > de.
Store the manual preference in a bounded, same-origin language cookie, with a
memory fallback when storage is blocked. Reject unsupported values. On HTTPS,
use Secure and SameSite=Lax, Path=/, and no parent-domain cookie. This is a
display preference, separate from authentication. Pass the resolved locale
explicitly where an identity redirect or document render needs it.

Update document language, title, description, screen-reader labels, placeholders,
tooltips and status text as well as visible prose. Use a locale registry with
direction metadata and CSS logical properties. Keep schematic coordinates,
waveforms, numeric expressions and identifiers left-to-right with bidi isolation;
adding Arabic must not mirror circuit geometry or reverse a current arrow.

### 2. Public landing and React integration

Keep a complete German static landing as the no-JavaScript fallback. Generate its
translated text from the landing catalogue at build time, and ship a small local
external script for browser detection and switching, using the shared locale
rules. Bundle only the public messages it needs. Keep translations text-safe;
translate structured rich content with approved markup rather than arbitrary HTML.
Do not expose protected application assets just to translate the public page.

Wrap React in one translation provider. Extract labels and explanations from all
panels and hooks, including loading/error boundaries, empty states, confirmations,
download buttons, probe names and unavailable/stale/failed explanations. Resolve
display text at render time so existing results change language immediately.

Translate shipped example titles, descriptions, block instructions/expectations,
part descriptions, trust badges, terminal descriptions and footprint notes through
their stable catalogue IDs. Manufacturer names and model identifiers stay intact.
Add coverage checks against catalogue IDs so new entries cannot silently miss a
translation. Keep any generated index changes in their normal generation path.

### 3. Diagnostics, numeric formatting and readable documents

Introduce stable message codes plus typed interpolation parameters for app-owned
checks, warnings and validation failures. Preserve measured numbers, pass/fail,
correlation IDs and existing response fields while adding presentation metadata.
Translate known schema errors by error type and field, never by matching English
sentences. Unexpected failures get a localized actionable summary and correlation
reference; retain technical details for diagnostics. Raw ngspice output stays raw.

Keep stored simulation reports and MCP machine contracts language-neutral. Existing
persisted reports need a compatibility path: prefer structured fields and stable
IDs already present, and handle legacy text explicitly without changing evidence.
Classify that legacy surface during implementation before claiming full coverage.

Add a bounded locale option outside the electrical graph for document export.
The server renders the PCB guide, first-power-on checklist, headings, warnings and
descriptive prose in the requested language. Use the same structured diagnostic
facts for browser and document rendering. Keep JSON keys, netlist syntax, JLCPCB
BOM column names, units and KiCad rule syntax compatible with their consumers.
An optional MCP document locale may be additive; existing clients retain their
current default and schemas unless they request a translated readable artifact.

Use locale-aware formatting for displayed measurements/dates, preserving
engineering prefixes, significant digits and unit semantics. Keep numeric HTML
input values and serialized JSON/SPICE numbers canonical; verify decimal entry in
German and English browsers rather than passing localized strings to Number().

### 4. Accounts and mail

Enable realm internationalization for de/en, with de as the realm fallback, using
Keycloak's shipped translations first. Supply small versioned theme overrides
only where Circuit Lab wording or locale synchronization requires them.

Allow only de/en `ui_locales` through OAuth2 Proxy and propagate the app selection
to sign-in, registration, account and logout/return flows. Verify direct entry to
`/workbench`, expired sessions, existing SSO sessions and direct account links.
Do not assume a query parameter alone wins: Keycloak has its own remembered and
profile preferences. Test precedence on the pinned image, synchronize the chosen
locale with the account preference used for subsequent email, and ensure returning
from an account-page language switch updates the application consistently.

Cover login, registration, required password update, email verification, forgotten
password, reset completion, settings/security, TOTP and delete-account confirmation.
Verify email subjects plus HTML and plain-text bodies through staging Mailpit,
including reset requested from a fresh browser after a language preference change.

Apply existing-realm changes through a small idempotent migration after a private
identity backup, preserving accounts, clients, roles, SMTP and security settings.
Record prior locale/theme settings for rollback. Apply and test it on staging
first; include the separate identity/proxy release steps in the delivery runbook.

## Build order and Monday delivery

1. First resolve the highest-risk seam: on disposable identity/staging, prove
   app choice -> OAuth2 Proxy -> Keycloak -> email -> return to app in both
   languages, including an existing account whose saved locale differs.
2. Add catalogues, resolver, provider and top selector; translate and test the
   landing plus workbench shell. Add key/placeholder completeness checks to CI.
3. Translate all editor, library, observation, result and sharing surfaces;
   introduce structured diagnostics and translate readable downloads.
4. Run the existing checks and both-language acceptance flows locally and on
   private staging. Review desktop/mobile screenshots and all translated texts.
5. Commit on main. Wait for Chris's explicit push instruction. After an authorized
   push, require passing CI and the staged-image promotion gate, plus verified
   identity migration; then smoke-test the public production domain in both
   languages. Do not claim a local commit is the Monday live release.

This is a cross-cutting change, not a front-page-only edit. The largest unknowns
are identity preference synchronization, historical diagnostic text and catalogue
prose coverage. The target is plausible but is not a tested delivery estimate;
resolve the identity seam first and report any scope or timing risk promptly.
Do not quietly reduce the agreed account/email/document scope to meet the date.

## Acceptance and regression gates

- Fresh de-DE browser sees German; en-GB sees English; unmatched languages fall
  back to German; ordered language preferences and invalid stored values work.
- Manual choice overrides browser preferences and survives navigation, reload,
  login, logout and direct workbench/account access. Blocked storage is graceful.
- Switching with an unsaved circuit and current transient/AC results changes all
  display text without changing the graph, values, revision, probes or results.
- All shipped catalogue entries, known errors, warnings and pass/fail/unavailable
  states have German and English messages, including accessibility-only text.
- Both languages complete signup/verification, sign-in, reset and account/security
  flows; Mailpit proves subjects and both message bodies use the intended locale.
- Readable downloads match the selection; existing circuit JSON, netlist, BOM and
  KiCad consumers remain compatible. Simulation outcomes/numbers remain identical.
- Unit/integration tests cover resolution, key/placeholder parity, structured
  messages, formatting and document output. Mutate resolver/fallback rules to
  confirm the tests detect broken precedence. Parameterize browser flows across
  de/en without deleting, skipping or weakening existing assertions.
- Run frontend lint, types/build, unit/browser/project suites; backend Ruff,
  mypy and pytest; real identity, database and solver regressions; dependency
  audits; then staging release tests in both languages.
- Review German wrapping on desktop and 390px mobile, keyboard/axe checks,
  translated SVG/ARIA descriptions, initial render, no-JS landing and blocked
  analytics behavior. Exercise an RTL test locale without advertising Arabic as
  shipped, checking isolated technical content and unchanged schematic geometry.
- Verify public landing translation assets, protected workbench routing, CSP,
  identity settings, rollback instructions and the exact deployed revision.

## References checked for this proposal

- [i18next configuration](https://www.i18next.com/overview/configuration-options)
- [react-i18next integration](https://react.i18next.com/latest/using-with-hooks)
- [Keycloak localization](https://www.keycloak.org/ui-customization/localization)
- [Keycloak language selection](https://www.keycloak.org/docs/latest/server_admin/#_user_locale_selection)
- [OAuth2 Proxy configuration reference](https://oauth2-proxy.github.io/oauth2-proxy/next/configuration/alpha-config/)

Upstream documentation establishes the supported approach; the exact pinned
Keycloak/OAuth2 Proxy interaction still needs the integration checks above.
