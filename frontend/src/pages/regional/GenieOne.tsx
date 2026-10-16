import { useEffect, useRef, useState } from 'react';
import { Globe, ShieldCheck } from 'lucide-react';
import { useGenieOne } from '../../lib/genieOne';
import GenieOneTurn from '../../components/genieOne/GenieOneTurn';
import Composer from '../../components/genieOne/Composer';

// Starters name the configured catalog.schema so Genie One searches the right data.
const samples = (fq: string) => [
  `Which 5 stores wasted the most dough balls last month in ${fq}?`,
  `How do order counts change on Tigers, Red Wings, Pistons and Lions game days vs other days in ${fq}?`,
  `Which stores had the most rush-hour dough stockouts in the last 30 days in ${fq}, and what drove them?`,
];

export default function GenieOne() {
  const one = useGenieOne();
  const [draft, setDraft] = useState('');
  const [schemaFqn, setSchemaFqn] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch('/api/genie-one/config').then(r => r.json()).then(c => setSchemaFqn(c.schema_fqn)).catch(() => setSchemaFqn(null));
  }, []);

  const lastTurn = one.turns[one.turns.length - 1];
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [one.turns.length, lastTurn?.status, lastTurn?.activity.length, lastTurn?.answer]);

  const send = (q: string) => {
    const text = q.trim();
    if (!text || one.busy) return;
    setDraft('');
    one.ask(text);
  };

  return (
    <div className="max-w-4xl mx-auto flex flex-col min-h-[calc(100vh-7rem)]">
      <div className="flex-1 space-y-6 pb-6">
        {!one.turns.length && (
          <div className="bg-surface rounded-2xl border border-gray-100 shadow-soft p-8">
            <div className="w-12 h-12 rounded-2xl lc-gradient flex items-center justify-center mb-4">
              <Globe className="w-6 h-6 text-white" />
            </div>
            <h2 className="text-lg font-semibold">Ask Genie One</h2>
            <p className="text-sm text-text-secondary mt-1">Genie One searches everything you can access in Unity Catalog. No agent to pick.</p>
            <p className="text-xs text-text-tertiary mt-2 mb-5 inline-flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5" />
              Runs as you: answers respect your Unity Catalog permissions.
            </p>
            <div className="flex flex-col gap-2">
              {schemaFqn && samples(schemaFqn).map(q => (
                <button key={q} onClick={() => send(q)} className="text-left text-sm px-4 py-3 rounded-xl border border-gray-200 hover:border-lc-orange hover:text-lc-orange">
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {one.turns.map(t => (
          <GenieOneTurn key={t.id} turn={t} busy={one.busy} onRetry={() => one.retry(t.id)} />
        ))}
        <div ref={bottom} />
      </div>
      <div className="sticky bottom-4">
        <Composer
          value={draft}
          onChange={setDraft}
          onSend={() => send(draft)}
          onReset={one.turns.length && !one.busy ? one.reset : undefined}
          placeholder={one.turns.length ? 'Ask Genie One a follow-up…' : 'Ask Genie One anything about your data…'}
          disabled={one.busy}
        />
      </div>
    </div>
  );
}
