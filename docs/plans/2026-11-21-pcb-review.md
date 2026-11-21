# PCB review inside Circuit Lab

Date: 2026-11-21. Initial viewer implemented locally; see `docs/pcb-review.md` for verified behavior and outstanding work. Not deployed.
Chris wants one seamless system, starting with viewing and inspecting boards. The
first release should support both importing a finished KiCad board and producing
a preliminary board from the current Circuit Lab circuit. Board placement and
routing editing can follow; it is not part of the first viewer.

## Existing boundary

`backend/kicad_export.py` translates the electrical circuit to a KiCad netlist,
BOM and warnings; it does not create a physical board. `circuits/pcb/fab-guide.md`
instructs the person to import that netlist in KiCad, draw/select an outline,
place footprints, route tracks and run DRC. The local `circuit-lab-kicad-test/`
contains netlists but no finished `.kicad_pcb` fixture. `kicad-cli` is not
installed on this workstation (as checked during discovery).

KiCad's CLI can export board layers to SVG and run PCB design-rule checks with
JSON output. The board is the physical source of truth; a netlist cannot encode
where parts or tracks actually sit. KiCad 9/10's stable IPC API requires a running
GUI; do not assume it is a headless board-generation service. Investigate a
version-pinned, isolated KiCad worker and demonstrate generation of a real board
before promising a particular generation mechanism or interactive router.

## First release: two ways into one review screen

1. **Import board:** upload a `.kicad_pcb`, optionally the matching `.kicad_pro`
   and `.kicad_dru` settings. Display real board outline, copper, tracks, pads,
   vias, holes, footprints and silkscreen with layer toggles, top/bottom view,
   pan/zoom and clickable part identifiers. DRC results show errors, warnings,
   unconnected nets, check configuration and whether matching settings were
   supplied. No DRC report or incomplete settings must not read as a clean bill
   of health. Cross-reference the uploaded board against the current circuit,
   presenting matched, missing, extra and changed items with caveats; a visual
   match alone does not prove electrical equivalence.
2. **Generate preliminary board:** start from the existing exporter and physical
   footprint mappings, produce a real KiCad board with an explicit outline and
   deterministic initial placement, and show its unrouted connections. Clearly
   call it *unrouted / not ready for fabrication*. Generated placement is an
   editable starting point for KiCad, not a claim that routing or DRC is complete.
   Do not invent a closed board outline or dimensions without explicit inputs or
   an identified template. Preserve Pi HAT header position and template geometry
   where a verified template is selected.

Both entry points use one review screen, support German and English, and preserve
KiCad board download for round-trip. Never overwrite the source file or a saved
circuit on upload or failed rendering. A board belongs to an explicit account and
circuit revision; use hashes to flag stale schematic/board evidence. First prove
round-trip association on a real fixture before deciding the persistence schema.

## Implementation sequence and acceptance

1. Create or acquire a small real KiCad 9/10 board fixture with a closed outline,
   two copper layers, real routed and unrouted nets, through-hole/SMD pads, a via,
   silkscreen and deliberately reproducible rule violation. Run import, SVG/DRC
   and re-open in actual KiCad. Measure worker image size, memory and execution
   time. Compare CLI output with KiCad's own editor view; do not use screenshots
   or a mock as proof of physical geometry correctness.
2. Prototype deterministic circuit-to-board conversion for the existing 7805
   block with pinned KiCad and footprint libraries. Verify pad/net identity,
   assigned footprints, outline input, saved board, unmapped/unsupported parts,
   and explicit unconnected state against KiCad's editor and DRC. The known
   relay coil export gap needs resolution before using the relay block as proof.
   If the selected KiCad interface cannot reliably create the board headlessly,
   report that gate and choose a validated alternative; do not fake a routed PCB.
3. Add an isolated board-processing worker (bounded input, time/memory/output,
   no network, restricted filesystem and concurrency). Do not load arbitrary
   board-supplied 3D model paths, external files, plugins or scripts. Change
   Apache's current 8192-byte limit only on a narrowly scoped authenticated PCB
   endpoint, with an explicit size limit at every layer. Render untrusted output
   safely, not as active inline SVG. Preserve existing simulator isolation.
4. Add the review UI and project association. Verify layer alignment, units,
   orientation, zoom, keyboard access, mobile behavior and both languages;
   preserve generated or imported board data unchanged. Distinguish imported,
   generated-unrouted, stale, DRC-unavailable, warnings and failed states.
5. Exercise import and generation on real KiCad, actual PostgreSQL ownership and
   isolated worker, then the browser, private staging and existing release gate.
   Test malformed/oversized files, missing libraries/settings, worker failure,
   cross-account isolation, mismatch, all required electrical nets and no data
   loss. Run appropriate dependency scans and document operating cost.

A 2D layer viewer is the first review surface. A 3D presentation can follow
when reliable board/model assets and a safe renderer are demonstrated. Later
interactive placement and routing is a separate major editor feature, including
undo, connectivity, clearance checks and KiCad round-trip—not implied by the
first preview.

## References

- KiCad 9 CLI PCB SVG and DRC: https://docs.kicad.org/9.0/en/cli/cli.pdf
- KiCad 9 PCB editor/netlist workflow: https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html
- KiCad IPC API limitations: https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/
- Existing standalone Python bindings: https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/
