import { useMemo, useState } from 'react';
import { BarChart3, Check, Code2, Copy, Table2 } from 'lucide-react';
import { Column } from '../../lib/types';
import ResultGrid from './ResultGrid';
import ResultChart, { buildChartSpec } from './ResultChart';

interface Props {
  columns: Column[];
  rows: Array<Array<string | null>>;
  rowCount: number;
  truncated?: boolean;
  /** rows is a preview of a larger result (Genie One caps previews) */
  preview?: boolean;
  sql?: string | null;
  sqlLabel?: string;
}

export default function QueryResult({ columns, rows, rowCount, truncated, preview, sql, sqlLabel = 'Generated SQL' }: Props) {
  const [view, setView] = useState<'table' | 'chart'>('table');
  const [copied, setCopied] = useState(false);
  const canChart = useMemo(() => buildChartSpec(columns, rows) !== null, [columns, rows]);
  const total = Math.max(rowCount, rows.length);
  const countLabel =
    preview && total > rows.length
      ? `Showing first ${rows.length.toLocaleString()} of ${total.toLocaleString()} rows`
      : `${total.toLocaleString()} ${total === 1 ? 'row' : 'rows'}${truncated ? ' (truncated)' : ''}`;

  const copySql = () => {
    if (!sql) return;
    navigator.clipboard.writeText(sql).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-text-tertiary">{countLabel}</span>
        {canChart && (
          <div className="flex items-center gap-1">
            <button title="Table" onClick={() => setView('table')} className="p-1.5 rounded-lg hover:bg-gray-100">
              <Table2 className={`w-4 h-4 ${view === 'table' ? 'text-lc-orange' : 'text-text-secondary'}`} />
            </button>
            <button title="Chart" onClick={() => setView('chart')} className="p-1.5 rounded-lg hover:bg-gray-100">
              <BarChart3 className={`w-4 h-4 ${view === 'chart' ? 'text-lc-orange' : 'text-text-secondary'}`} />
            </button>
          </div>
        )}
      </div>
      {view === 'chart' && canChart ? <ResultChart columns={columns} rows={rows} /> : <ResultGrid columns={columns} rows={rows} />}
      {sql && (
        <details className="rounded-xl border border-gray-100">
          <summary className="px-4 py-2.5 text-xs font-medium text-text-secondary cursor-pointer flex items-center gap-2">
            <Code2 className="w-3.5 h-3.5" />
            {sqlLabel}
            <button onClick={e => (e.preventDefault(), copySql())} className="ml-auto inline-flex items-center gap-1 text-text-tertiary hover:text-lc-orange">
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </summary>
          <pre className="px-4 pb-4 text-[11px] font-mono text-text-secondary overflow-x-auto whitespace-pre-wrap">{sql}</pre>
        </details>
      )}
    </div>
  );
}
