# KiCad board-generation proof (not product code)

This is an isolated proof of the highest-risk part of the PCB review plan. It
uses the real LM7805 component/net mapping from Circuit Lab, pinned KiCad 9.0.2
and KiCad's footprint libraries to create an unrouted board. It reopens the
saved file through KiCad's PCB API, verifies every expected pad/net association,
and runs actual KiCad DRC and SVG layer export. It does not constitute the
requested application workflow or certify the placement for manufacture.

From the repository root:

```sh
docker build -t circuit-pcb-proof:9.0.2 experiments/pcb-proof
mkdir -p /tmp/circuit-pcb-proof-output/layers
cp experiments/pcb-proof/{prove.py,verify.py,components.json} /tmp/circuit-pcb-proof-output/
docker run --rm --network none -v /tmp/circuit-pcb-proof-output:/work circuit-pcb-proof:9.0.2 sh -c \
  '/usr/bin/python3 /work/prove.py && kicad-cli pcb drc --format json -o /work/drc.json /work/generated.kicad_pcb && /usr/bin/python3 /work/verify.py && kicad-cli pcb export svg --mode-multi --layers F.Cu,F.Silkscreen,Edge.Cuts -o /work/layers/ /work/generated.kicad_pcb'
```

The 90 × 45 mm rectangle is an explicitly defined proof fixture, not an automatic
board-size decision. The exact packages are pinned to Debian trixie versions;
the Docker image's Debian base is pinned by digest. Output belongs to the caller
and is not accepted as input by the production app.
