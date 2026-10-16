import { AlertTriangle, Globe, RotateCcw } from 'lucide-react';
import { OneTurn } from '../../lib/genieOne';
import ActivityTrail from './ActivityTrail';
import Markdown from './Markdown';
import QueryResult from './QueryResult';

const ERROR_TITLES: Record<string, string> = {
  auth: 'Genie One needs user authorization for this app',
  disabled: 'Genie One is not enabled in this workspace',
  upstream: 'Genie One could not answer this',
  network: 'Connection lost',
};

export default function GenieOneTurn({ turn, busy, onRetry }: { turn: OneTurn; busy: boolean; onRetry: () => void }) {
  const canRetry = turn.error && (turn.error.kind === 'network' || turn.error.kind === 'upstream');
  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-lc-orange text-white px-4 py-2.5 text-sm">{turn.question}</div>
      </div>
      <div className="bg-surface rounded-2xl border border-gray-100 shadow-soft p-5 space-y-4">
        <div className="flex items-center gap-2 text-xs font-medium text-lc-orange">
          <Globe className="w-3.5 h-3.5" />
          Genie One
        </div>
        <ActivityTrail turn={turn} />
        {turn.answer?.map((s, i) => {
          if (s.type === 'markdown') return <Markdown key={i} text={s.text} />;
          const q = turn.queries[s.id];
          return q ? (
            <QueryResult key={i} columns={q.columns} rows={q.rows} rowCount={q.total_row_count} preview sql={q.sql} sqlLabel="SQL run by Genie One" />
          ) : (
            <Markdown key={i} text={s.markdown} />
          );
        })}
        {turn.status === 'error' && turn.error && (
          <div className="flex items-start gap-3 rounded-xl bg-red-50 border border-red-100 p-4 text-sm text-red-700">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="font-medium">{ERROR_TITLES[turn.error.kind]}</p>
              <p className="mt-1">{turn.error.message}</p>
            </div>
            {canRetry && (
              <button disabled={busy} onClick={onRetry} className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-xl border border-red-200 hover:bg-red-100 disabled:opacity-50">
                <RotateCcw className="w-3.5 h-3.5" />
                Retry
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
