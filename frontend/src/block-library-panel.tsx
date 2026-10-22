import { BLOCKS, CATEGORY_NAMES, freeSpot, mergeBlock } from './block-library';
import type { CircuitBlock } from './block-library';
import type { EditorState } from './use-schematic-editor';

function BlockEntry({ block, editor }: { block: CircuitBlock; editor: EditorState }) {
  const insert = () => {
    try {
      const spot = freeSpot(editor.schematic, block);
      if (!spot) throw new Error(block.name + ' is larger than the grid allows.');
      if (spot.overlaps && !window.confirm('There is no clear space for "' + block.name + '". Insert it anyway, overlapping '
        + spot.overlaps + ' of your parts? You can drag them apart afterwards, or use Open instead.')) return;
      editor.commit(mergeBlock(editor.schematic, block, spot.column, spot.row), 'block.insert:' + block.id);
      editor.setSelected(null); editor.setWireStart(null);
    } catch (error) { editor.setError(error instanceof Error ? error.message : 'The block could not be inserted.'); }
  };
  const open = () => {
    if (!window.confirm('Replace the current circuit with "' + block.name + '"? Export first if you want to keep it.')) return;
    editor.commit(block.circuit, 'block.open:' + block.id); editor.setSelected(null); editor.setWireStart(null);
  };
  return <li className="block-entry">
    <h3>{block.name}</h3><p>{block.description}</p>
    <details><summary>What it should do</summary><ul>{block.expectations.map(expectation =>
      <li key={expectation.signal + expectation.statistic}>{expectation.meaning}</li>)}</ul><p className="muted">{block.notes}</p></details>
    <div className="button-row"><button disabled={editor.running} onClick={insert} aria-label={'Insert ' + block.name}>Insert</button>
      <button disabled={editor.running} onClick={open} aria-label={'Open ' + block.name}>Open</button></div>
  </li>;
}

export function BlockLibraryPanel({ editor }: { editor: EditorState }) {
  const categories = [...new Set(BLOCKS.map(block => block.category))];
  return <details className="editor-card"><summary>Circuit library ({BLOCKS.length})</summary>
    <p className="muted">Ready-made building blocks, each simulated in CI to check it does what it says and stays within every
      part's ratings. Insert adds one beside your circuit; Open replaces your circuit with it.</p>
    {categories.map(category => <section key={category} aria-label={CATEGORY_NAMES[category] + ' blocks'}>
      <h3 className="block-category">{CATEGORY_NAMES[category]}</h3>
      <ul className="block-list">{BLOCKS.filter(block => block.category === category).map(block =>
        <BlockEntry key={block.id} block={block} editor={editor} />)}</ul></section>)}
  </details>;
}
