import { useEffect, useRef } from "react";
import type { Nucleus, SelectionModifiers } from "../types";

interface Props {
  nuclei: Nucleus[];
  selected: number[];
  onSelect: (id: number, modifiers: SelectionModifiers) => void;
  onSelectAll: (ids: number[]) => void;
}

export function NucleiTable({ nuclei, selected, onSelect, onSelectAll }: Props) {
  const selectAllRef = useRef<HTMLInputElement>(null);
  const allSelected = nuclei.length > 0 && nuclei.every((nucleus) => selected.includes(nucleus.nucleus_id));
  const someSelected = nuclei.some((nucleus) => selected.includes(nucleus.nucleus_id));

  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = someSelected && !allSelected;
  }, [allSelected, someSelected]);

  const visibleIds = nuclei.map((nucleus) => nucleus.nucleus_id);

  return <div className="table-wrap"><table>
    <thead><tr>
      <th className="selection-cell"><input
        ref={selectAllRef}
        type="checkbox"
        checked={allSelected}
        onChange={() => onSelectAll(visibleIds)}
        aria-label="Selecionar todos os núcleos visíveis"
      /></th>
      <th>ID</th><th>Estado</th><th>Área px</th><th>Proteína média</th><th>Circularidade</th>
    </tr></thead>
    <tbody>{nuclei.map((nucleus) => {
      const isSelected = selected.includes(nucleus.nucleus_id);
      return <tr
        key={nucleus.nucleus_id}
        className={isSelected ? "selected-row" : ""}
        onClick={(event) => onSelect(nucleus.nucleus_id, {
          additive: event.ctrlKey || event.metaKey,
          range: event.shiftKey,
        })}
        aria-selected={isSelected}
      >
        <td className="selection-cell" onClick={(event) => event.stopPropagation()}>
          <input
            type="checkbox"
            checked={isSelected}
            onChange={() => onSelect(nucleus.nucleus_id, { additive: true, range: false })}
            aria-label={`Selecionar núcleo ${nucleus.nucleus_id}`}
          />
        </td>
        <td>#{nucleus.nucleus_id}</td>
        <td><span className={`state state-${nucleus.state}`}>{nucleus.state}</span></td>
        <td>{nucleus.area_px}</td>
        <td>{nucleus.protein_mean?.toFixed(2) ?? "—"}</td>
        <td>{nucleus.circularity?.toFixed(3) ?? "—"}</td>
      </tr>;
    })}</tbody>
  </table></div>;
}
