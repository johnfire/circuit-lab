"""Load development boards and describe them for the browser and AI clients."""

from pathlib import Path

from backend.board_models import Board, allowed_modes

BOARDS_ROOT = Path(__file__).resolve().parent.parent / "circuits" / "boards"
BOARDS_INDEX_PATH = Path(__file__).resolve().parent.parent / "circuits" / "boards-index.json"


def load_boards(root: Path = BOARDS_ROOT) -> dict[str, Board]:
    """Load every board file, requiring its folder name to match its id."""
    boards: dict[str, Board] = {}
    for path in sorted(root.glob("*/board.json")):
        try:
            board = Board.model_validate_json(path.read_text())
        except ValueError as error:
            raise ValueError(f"Invalid board file {path.relative_to(root)}: {error}") from error
        if path.parent.name != board.id:
            raise ValueError(f"{path} must live in a folder named {board.id}")
        boards[board.id] = board
    return boards


BOARDS = load_boards()


def board_summary(board: Board) -> dict[str, object]:
    """Everything a pinout view or an AI client needs, including each pin's allowed modes."""
    return {"id": board.id, "name": board.name, "description": board.description,
            "header": board.header, "columns": board.columns, "trust": board.trust.level,
            "documentation": board.documentation,
            "logic_voltage": board.electrical.logic_voltage,
            "ratings": {name: {"value": rating.value, "unit": rating.unit}
                        for name, rating in board.electrical.ratings.items()},
            "pins": [{"id": pin.id, "name": pin.name, "kind": pin.kind, "gpio": pin.gpio,
                      "functions": pin.functions, "voltage": pin.voltage,
                      "current_max": pin.current_max.value if pin.current_max else None,
                      "fixed_pull_up": pin.fixed_pull_up, "note": pin.note,
                      "modes": sorted(allowed_modes(pin))} for pin in board.pins]}


def board_summaries() -> list[dict[str, object]]:
    """Every board, by name."""
    return [board_summary(board) for board in sorted(BOARDS.values(), key=lambda board: board.name)]
