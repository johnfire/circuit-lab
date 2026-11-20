"""Translations change presentation, never simulation evidence or machine formats."""

import json
import re
from pathlib import Path

from backend.bring_up_sheet import bring_up_sheet
from backend.localization import CATALOGUES, LocalizedString, render_message, text
from backend.schematic_engine import simulate_schematic
from backend.schematic_models import SchematicRequest
from backend.simulation_models import Check, SimulationResponse
from backend.verification_checks import evaluate_intent


def test_all_message_keys_and_placeholders_match():
    assert CATALOGUES["en"].keys() == CATALOGUES["de"].keys()
    for key, english in CATALOGUES["en"].items():
        assert CATALOGUES["de"][key].strip(), key
        assert sorted(re.findall(r"\{\{(\w+)\}\}", english)) == sorted(
            re.findall(r"\{\{(\w+)\}\}", CATALOGUES["de"][key])), key


def test_public_catalogues_and_shipped_library_text_have_both_languages():
    for name in ("landing", "identity"):
        english = json.loads(Path(f"locales/en/{name}.json").read_text())
        german = json.loads(Path(f"locales/de/{name}.json").read_text())
        assert english.keys() == german.keys()
        assert all(isinstance(value, str) and value.strip() for value in german.values())
    for kind in ("parts", "boards", "blocks"):
        for entry in json.loads(Path(f"circuits/{kind}-index.json").read_text()):
            prefix = f"catalogue.{kind}.{entry['id']}"
            fields = ["description"] + (["name", "notes"] if kind == "blocks" else [])
            for field in fields:
                assert prefix + "." + field in CATALOGUES["de"]
            for collection, field in (("pins", "note"), ("footprints", "note")):
                for member in entry.get(collection, []):
                    if member.get(field):
                        assert f"{prefix}.{collection}.{member['id']}.{field}" in CATALOGUES["de"]
            for index, expectation in enumerate(entry.get("expectations", [])):
                assert f"{prefix}.expectations.{index}" in CATALOGUES["de"]


def test_fallback_and_nested_interpolation_preserve_the_value():
    notice = text("shared-circuit.unsent_edits_remain_local", reason=text("shared-circuit.connection_unavailable"))
    assert render_message(notice.reference, "de") == "Nicht gesendete Änderungen bleiben lokal. Verbindung nicht verfügbar."
    assert render_message(notice.reference, "ar") == str(notice)


def test_check_retains_english_fields_and_structured_localization():
    check = evaluate_intent("voltage_divider", {"R1": 10000, "R2": 6800},
                            {"v_out.csv": [(0, 2.0238095238095237)]}, 0.15)[0]
    assert check.name == "Divider matches theory" and check.passed
    assert check.name_message is not None
    assert render_message(check.name_message, "de") == "Spannungsteiler entspricht der Theorie"
    assert check.detail_message is not None
    assert "2.0238" in render_message(check.detail_message, "de")
    assert Check.model_validate(check.model_dump()) == check


def test_warning_metadata_survives_serialization_without_replacing_english():
    warning = text("common.language")
    assert isinstance(warning, LocalizedString)
    report = SimulationResponse(circuit_id="test", correlation_id="id", status="passed", parameters={},
                                signals=[], checks=[], warnings=[warning], netlist="", duration_ms=0)
    assert report.warnings == ["Language"]
    assert report.warning_messages[0] is not None
    assert render_message(report.warning_messages[0], "de") == "Sprache"
    assert SimulationResponse.model_validate_json(report.model_dump_json()) == report


def test_readable_checklist_translates_without_changing_evidence(analog_request: SchematicRequest):
    report = simulate_schematic(analog_request, "locale-evidence")
    original = report.model_dump_json()
    german = bring_up_sheet(analog_request, report, "de")
    assert german.startswith("# Checkliste zur Inbetriebnahme")
    assert "locale-evidence" in german and "| Netz | Messpunkt | Erwartung |" in german
    english = bring_up_sheet(analog_request, report)
    references = re.findall(r"\b[RCLVJU][0-9]+\b", english)
    assert references and re.findall(r"\b[RCLVJU][0-9]+\b", german) == references
    assert "## 2. Erstes Einschalten mit Strombegrenzung" in german
    assert report.model_dump_json() == original


def test_pcb_download_locale_changes_only_human_readable_guide():
    from fastapi.testclient import TestClient

    from backend.application import app
    from backend.block_library import BLOCKS
    circuit = BLOCKS["lm7805_5v_supply"].circuit.model_dump()
    with TestClient(app, base_url="http://localhost") as client:
        english = client.post("/api/export/kicad?language=en", json=circuit)
        german = client.post("/api/export/kicad?language=de", json=circuit)
        assert client.post("/api/export/kicad?language=ar", json=circuit).status_code == 422
    assert english.status_code == german.status_code == 200
    for field in ("netlist", "bom_csv", "design_rules", "warnings", "warning_messages"):
        assert english.json()[field] == german.json()[field], field
    assert german.json()["fab_guide"].startswith("# Von Circuit Lab zur JLCPCB-Platine")
    assert english.json()["fab_guide"] != german.json()["fab_guide"]
