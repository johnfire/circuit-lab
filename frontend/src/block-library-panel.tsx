import { message, failureMessage, LocalizedFailure } from './display-message.ts';
import { translate } from './localization.ts';
import { BLOCKS, CATEGORY_NAMES, freeSpot, mergeBlock } from './block-library';
import type { CircuitBlock } from './block-library';
import type { EditorState } from './use-schematic-editor';

function BlockEntry({ block, editor }: { block: CircuitBlock; editor: EditorState }) {
  const insert = () => {
    try {
      const spot = freeSpot(editor.schematic, block);
      if (!spot) throw new LocalizedFailure("block.too_large", { name: block.name });
      if (spot.overlaps && !window.confirm(translate('block.confirm_overlap', { name: block.name, count: spot.overlaps }))) return;
      editor.commit(mergeBlock(editor.schematic, block, spot.column, spot.row), 'block.insert:' + block.id);
      editor.setSelected(null); editor.setWireStart(null);
    } catch (error) { editor.setError(error instanceof Error ? failureMessage(error) : message("block-library-panel.the_block_could_not_be")); }
  };
  const open = () => {
    if (!window.confirm(translate('block.confirm_replace', { name: block.name }))) return;
    editor.commit(block.circuit, 'block.open:' + block.id); editor.setSelected(null); editor.setWireStart(null);
  };
  return <li className="block-entry">
    <h3>{block.name}</h3><p>{block.description}</p>
    <details><summary>{translate("block-library-panel.what_it_should_do")}</summary><ul>{block.expectations.map(expectation =>
      <li key={expectation.signal + expectation.statistic}>{expectation.meaning}</li>)}</ul><p className="muted">{block.notes}</p></details>
    <div className="button-row"><button disabled={editor.running} onClick={insert} aria-label={translate("block-library-panel.insert") + block.name}>{translate("block-library-panel.insert_2")}</button>
      <button disabled={editor.running} onClick={open} aria-label={translate("block-library-panel.open") + block.name}>{translate("block-library-panel.open_2")}</button></div>
  </li>;
}

export function BlockLibraryPanel({ editor }: { editor: EditorState }) {
  const categories = [...new Set(BLOCKS.map(block => block.category))];
  return <details className="editor-card"><summary>{translate("block-library-panel.circuit_library")}{BLOCKS.length})</summary>
    <p className="muted">{translate("block-library-panel.readymade_building_blocks_each_simulated")}</p>
    {categories.map(category => <section key={category} aria-label={CATEGORY_NAMES[category] + translate("block-library-panel.blocks")}>
      <h3 className="block-category">{CATEGORY_NAMES[category]}</h3>
      <ul className="block-list">{BLOCKS.filter(block => block.category === category).map(block =>
        <BlockEntry key={block.id} block={block} editor={editor} />)}</ul></section>)}
  </details>;
}
