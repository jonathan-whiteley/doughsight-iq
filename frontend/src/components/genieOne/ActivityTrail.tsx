import { useEffect, useState } from 'react';
import { CheckCircle2, ChevronRight, Database, FileSearch, Loader2, Search, Wrench } from 'lucide-react';
import { OneStep, OneTurn, StepKind } from '../../lib/genieOne';

const ICONS: Record<StepKind, typeof Search> = { search: Search, read: FileSearch, sql: Database, other: Wrench };

function StepRow({ step }: { step: OneStep }) {
  const Icon = ICONS[step.kind] ?? Wrench;
  return (
    <li className="text-xs flex items-start gap-2">
      <Icon className="w-3.5 h-3.5 mt-0.5 text-lc-orange shrink-0" />
      <div className="min-w-0 flex-1">
        <span className="text-text-primary">{step.label}</span>
        {step.result && <span className="text-text-tertiary"> · {step.result}</span>}
        {step.detail && (
          <details className="mt-1">
            <summary className="cursor-pointer text-text-tertiary">SQL</summary>
            <pre className="mt-1 text-[11px] font-mono whitespace-pre-wrap text-text-secondary bg-surface rounded-lg p-2 border border-gray-100">{step.detail}</pre>
          </details>
        )}
      </div>
    </li>
  );
}

/** Live trail of Genie One's tool calls: open while streaming, collapsed once the answer lands. */
export default function ActivityTrail({ turn }: { turn: OneTurn }) {
  const streaming = turn.status === 'streaming';
  const [open, setOpen] = useState(streaming);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!streaming) {
      setOpen(false);
      return;
    }
    setOpen(true);
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [streaming]);

  if (!streaming && turn.activity.length === 0) return null;
  const steps = turn.activity.filter(a => a.type === 'step').length;
  const secs = Math.max(0, Math.round((turn.elapsedMs ?? now - turn.startedAt) / 1000));

  return (
    <div className="rounded-xl border border-gray-100 bg-surface-secondary/60">
      <button onClick={() => setOpen(o => !o)} className="w-full flex items-center gap-2 px-4 py-2.5 text-xs font-medium text-text-secondary">
        {streaming ? <Loader2 className="w-3.5 h-3.5 animate-spin text-lc-orange" /> : <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />}
        {streaming ? 'Genie One is working' : 'Activity'} · {steps} {steps === 1 ? 'step' : 'steps'} · {secs}s
        <ChevronRight className={`w-3.5 h-3.5 ml-auto transition-transform ${open ? 'rotate-90' : ''}`} />
      </button>
      {open && (
        <ol className="px-4 pb-3 space-y-1.5">
          {turn.activity.map((a, i) =>
            a.type === 'thinking' ? (
              <li key={`t${i}`} className="text-xs text-text-tertiary italic pl-5">
                {a.text}
              </li>
            ) : (
              <StepRow key={a.step.id} step={a.step} />
            ),
          )}
        </ol>
      )}
    </div>
  );
}
