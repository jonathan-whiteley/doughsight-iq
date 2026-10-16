import { useMemo, useState } from 'react';
import { ArrowDown, ArrowUp } from 'lucide-react';
import { Column } from '../../lib/types';
import { columnKind, formatValue, isNumericKind, prettyLabel } from '../../lib/format';

interface Props {
  columns: Column[];
  rows: Array<Array<string | null>>;
  pageSize?: number;
}

export default function ResultGrid({ columns, rows, pageSize = 25 }: Props) {
  const [sort, setSort] = useState<{ i: number; dir: 1 | -1 } | null>(null);
  const [shown, setShown] = useState(pageSize);
  const kinds = useMemo(() => columns.map(c => columnKind(c.name, c.type)), [columns]);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const num = isNumericKind(kinds[sort.i]);
    return [...rows].sort((a, b) => {
      const x = a[sort.i], y = b[sort.i];
      if (x === y) return 0;
      if (x === null) return 1;
      if (y === null) return -1;
      return (num ? Number(x) - Number(y) : String(x).localeCompare(String(y))) * sort.dir;
    });
  }, [rows, sort, kinds]);

  const toggle = (i: number) => setSort(s => (s && s.i === i ? (s.dir === 1 ? { i, dir: -1 } : null) : { i, dir: 1 }));

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-100">
      <table className="w-full text-sm">
        <thead className="bg-surface-secondary text-text-secondary text-xs sticky top-0">
          <tr>
            {columns.map((c, i) => (
              <th
                key={c.name}
                onClick={() => toggle(i)}
                className={`px-3 py-2 font-medium whitespace-nowrap cursor-pointer select-none hover:text-text-primary ${isNumericKind(kinds[i]) ? 'text-right' : 'text-left'}`}
              >
                <span className="inline-flex items-center gap-1">
                  {prettyLabel(c.name)}
                  {sort?.i === i && (sort.dir === 1 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {sorted.slice(0, shown).map((r, j) => (
            <tr key={j} className="hover:bg-surface-secondary/60">
              {r.map((v, k) => (
                <td key={k} className={`px-3 py-2 whitespace-nowrap ${isNumericKind(kinds[k]) ? 'text-right tabular-nums' : ''} ${columns[k].name === 'confirmation_number' ? 'font-mono text-[12px]' : ''}`}>
                  {v === null || v === '' ? <span className="text-text-tertiary">n/a</span> : formatValue(v, kinds[k])}
                </td>
              ))}
            </tr>
          ))}
          {sorted.length > shown && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-2 text-xs text-text-tertiary">
                Showing {shown} of {sorted.length.toLocaleString()} rows ·{' '}
                <button className="text-lc-orange hover:underline" onClick={() => setShown(s => s + 100)}>
                  show more
                </button>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
