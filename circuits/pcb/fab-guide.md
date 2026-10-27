# From Circuit Lab to a JLCPCB board

Bare boards, through-hole parts you solder yourself. Menu names are from KiCad 9 and JLCPCB's KiCad 9
guide; KiCad 10 should match, but say if a menu has moved.

You downloaded three files: `circuit-lab.net` (parts and connections), `circuit-lab-bom.csv`
(parts list) and `circuit-lab-jlcpcb-rules.txt` (design rules).

## 1. Start the KiCad project

- **Raspberry Pi circuits:** *File → New Project from Template → RaspberryPi-HAT* (or *RaspberryPi-uHAT*
  for a small board). It already has the official HAT outline, four M2.5 mounting holes and the 40-pin
  socket `J1` in the right place. Circuit Lab always names the Pi header `J1` so it lands on that socket.
- **Everything else:** *File → New Project*. In the PCB editor draw the outline on the **Edge.Cuts**
  layer (a rectangle is fine; 100 × 100 mm or smaller is JLC's cheapest size) and add four
  `MountingHole:MountingHole_3.2mm_M3` footprints in the corners.

## 2. Load the design rules

*File → Board Setup → Design Rules → Custom Rules*: paste the whole rules file, click **Check Rule
Syntax**, then OK. The rules hold you to JLCPCB's standard 2-layer limits with some margin.

While in Board Setup, under **Net Classes** set the Default class to 0.25 mm track and 0.2 mm
clearance. Add a **Power** class at 0.5 mm (about 1 A on 1 oz copper) for supply, ground and coil
nets, and 1.0 mm for anything above 2 A.

## 3. Import the netlist

PCB editor: *File → Import → Netlist…*, pick `circuit-lab.net`.

- **Link footprints using: Reference designators.** This keeps the template's `J1` in place.
- Leave **Delete footprints with no symbols** unchecked, or the mounting holes disappear.
- Click **Update PCB**. Every part arrives in a pile, joined by thin "ratsnest" lines showing what
  must connect.

## 4. Place and route

1. Drag parts onto the board. Put each regulator's and op-amp's capacitors right at its pins (the
   export lists which ones). Keep the regulator's input, output and ground loop small.
2. Route tracks (**X**). Use the Power class for supply and coil currents.
3. Fill the back copper with a ground zone: *Place → Zone* on **B.Cu**, net **GND**, around the board.
   Press **B** to refill zones after changes.
4. Add a text label (≥ 1.0 mm high) with the board name and date.

## 5. Check

- *Inspect → Design Rules Checker*: run it until it shows **0 errors**. Read the warnings too.
- *View → 3D Viewer*: every part on the right side, nothing overlapping.
- **Print 1:1 on paper** and press the real parts' legs through it. This catches a wrong footprint or
  pin order before you pay for it. Do it for every *draft* part the export warned about.

## 6. Make the Gerbers (JLCPCB's KiCad 9 settings)

*File → Plot*:

- Layers: **F.Cu, B.Cu, F.Silkscreen, B.Silkscreen, F.Mask, B.Mask, Edge.Cuts**
  (F.Paste/B.Paste only for a stencil or assembly).
- Format **Gerber**; check zone fills before plotting; drill marks **None**; scale 1:1; plot mode
  filled; **Use Protel filename extensions**; **Use extended X2 format**; **Include netlist
  attributes**; coordinate format **4.6, unit mm**.
- Output to a folder with a plain name (no spaces), then **Plot**.

Then **Generate Drill Files…** in the same dialog: **Excellon**, alternate drill mode for oval holes,
origin **Absolute**, units **Millimeters**, zeros **Decimal format**, PTH and NPTH in **separate**
files, same folder. Click **Generate**.

## 7. Order

1. Zip the folder (all `.g*` files plus both `.drl` files; English filenames).
2. On jlcpcb.com upload the zip. The defaults suit a first board: 2 layers, 1.6 mm FR-4,
   HASL (lead-free if you prefer), quantity 5.
3. Check JLC's Gerber viewer: outline closed, holes where expected, text readable.
4. Order. JLC's assembly service needs LCSC part numbers and a placement file, which Circuit Lab
   doesn't produce yet: solder the parts yourself from the BOM.

## Sources

- JLCPCB capabilities: <https://jlcpcb.com/capabilities/pcb-capabilities> (checked 2026-10-22)
- JLCPCB KiCad 9 Gerber guide: <https://jlcpcb.com/help/article/how-to-generate-gerber-and-drill-files-in-kicad-9>
- KiCad templates: <https://gitlab.com/kicad/libraries/kicad-templates> (RaspberryPi-HAT)
