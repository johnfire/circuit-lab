import { useState } from 'react';
import { BOARDS, boardOf } from './board-library';
import type { BoardPin } from './board-library';
import type { Schematic } from './schematic-types';

const KIND_NAMES: Record<BoardPin['kind'], string> = {
  gpio: 'GPIO', input_only: 'Input only', power: 'Power', ground: 'Ground', special: 'Special',
};

function PinCell({ pin, used }: { pin: BoardPin; used: string | undefined }) {
  const details = [KIND_NAMES[pin.kind], ...pin.functions, pin.voltage ? pin.voltage + ' V' : '', pin.note].filter(Boolean).join(' · ');
  return <li className={'pinout-pin pin-' + pin.kind + (used ? ' pin-used' : '')} title={details}>
    <span className="pinout-number">{pin.id}</span>
    <span className="pinout-name">{pin.name}{used && <strong> · {used}</strong>}</span>
    {pin.functions.length > 0 && <span className="pinout-functions">{pin.functions.join(', ')}</span>}
  </li>;
}

export function BoardPinout({ schematic }: { schematic: Schematic }) {
  const [chosen, setChosen] = useState<string | null>(null);
  const circuitBoard = schematic.parts.find(part => part.board_pin)?.board_pin?.board;
  const board = boardOf(chosen ?? circuitBoard ?? 'raspberry_pi_4') ?? BOARDS[0];
  if (!board) return null;
  const usedBy = new Map(schematic.parts.filter(part => part.board_pin?.board === board.id)
    .map(part => [part.board_pin!.pin, part.id] as const));
  return <details className="editor-card"><summary>Board pinouts</summary>
    <label>Pinout board<select value={board.id} onChange={event => setChosen(event.target.value)}>
      {BOARDS.map(option => <option key={option.id} value={option.id}>{option.name}</option>)}</select></label>
    <p className="muted">{board.description}. {board.header}{board.columns === 2 ? ', drawn as it sits on the board' : ''}.
      {board.trust === 'draft' && ' Draft: check against the official pinout before wiring.'}</p>
    <ol className={'pinout-grid pinout-columns-' + board.columns} aria-label={board.name + ' header pins'}>
      {board.pins.map(pin => <PinCell key={pin.id} pin={pin} used={usedBy.get(pin.id)} />)}</ol>
    <p className="muted">Pin limits: {board.logic_voltage} V logic, {board.ratings.pin_current_max.value * 1000} mA per pin,
      at most {board.ratings.pin_voltage_max.value} V on any GPIO.</p>
  </details>;
}
