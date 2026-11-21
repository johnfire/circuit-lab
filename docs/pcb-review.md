# PCB review (local implementation)

Circuit Lab can generate a preliminary `.kicad_pcb` from its current circuit or
import a KiCad board, and use a separate, no-network KiCad 9.0.2 worker to run
DRC and render front, back and outline views. The review screen includes zoom,
component reference/position lists, track/via and unconnected counts, DRC
findings, and the original KiCad file download. Imported file bytes are not
changed. German and English controls are available. The current circuit is not
changed when a review succeeds or fails.

Generated boards are unrouted placement drafts: dimensions must be entered and
KiCad may report overlapping or out-of-bounds footprints. Check every finding,
pad map and datasheet before use. Pi 4/5 HAT generation is deliberately refused
until the official template geometry can be preserved. Circuit Lab does not yet
route tracks or edit component positions in the browser.

An imported board is reviewed using KiCad default rules: the matching KiCad
project and custom `.kicad_dru` rules are not yet accepted. It is not yet
compared automatically with the current circuit. Project-specific rule checks,
schematic/board equivalence, power, manufacturer suitability and physical
fit therefore require separate review. The browser currently holds this review
in memory; it is not saved with a project revision, and a reload clears it.
Existing circuit-export warnings appear in their original language.

## Operation and deployment

The worker uses a separate image, Unix socket, read-only root filesystem,
unprivileged user, no capabilities, restricted temporary storage, limited CPU,
memory and processes, and no network. Uploads are bounded to 1 MiB and are
processed only by this worker. KiCad SVG output is converted to PNG inside the
worker, so untrusted board graphics are never served as executable inline SVG.

The release receiver must be updated before delivery so that it records and
compares the PCB worker image alongside the API and simulator images. The
staging and production Apache vhosts need the narrowly scoped `/api/pcb/review`
request limit in their templates; install and validate those changes through the
normal backed-up administrator procedure before an authorized push. Production
promotion must still use the exact staged images. Verify service health and real
board generation/import in private staging before promotion. The KiCad image is
approximately 1.4 GB locally; check VPS disk and memory before releasing.

For local development build/start the PCB worker and point `CIRCUIT_PCB_SOCKET`
at its Unix socket. `npm run test:pcb --prefix frontend` requires that worker and
runs real generation, download, re-import and a partially routed KiCad fixture.
CI runs it in an isolated no-network container. `uv run pytest` and the standard
frontend suites remain separate. Do not use fixture credentials on the VPS.

## Next work

- Add project-specific rule files and report exactly which settings were used.
- Compare board nets, footprints and pads against a specific circuit revision;
  save the board privately with that revision and show stale/mismatch states.
- Test more routed and multi-layer boards, complex outlines, holes and KiCad
  versions, and improve individual layer toggles and component highlighting.
- Add Pi HAT template support, then explore placement/routing editing and 3D.
