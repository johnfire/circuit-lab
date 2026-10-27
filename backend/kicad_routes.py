"""Browser API for PCB export: a validated circuit in, KiCad netlist and BOM out."""

from fastapi import APIRouter, HTTPException

from backend.kicad_export import export_kicad
from backend.model_primitives import StrictModel
from backend.schematic_models import SchematicRequest

router = APIRouter()


class KicadFiles(StrictModel):
    """The files to download and what the user still needs to do."""

    netlist: str
    bom_csv: str
    design_rules: str
    fab_guide: str
    warnings: list[str]


@router.post("/api/export/kicad", response_model=KicadFiles)
def export_for_pcb(submitted: SchematicRequest) -> KicadFiles:
    """No simulation runs; the circuit must just be completely and validly wired."""
    try:
        exported = export_kicad(submitted)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"Not ready for PCB export: {error}") from error
    return KicadFiles(netlist=exported.netlist, bom_csv=exported.bom_csv, design_rules=exported.design_rules,
                      fab_guide=exported.fab_guide, warnings=exported.warnings)
