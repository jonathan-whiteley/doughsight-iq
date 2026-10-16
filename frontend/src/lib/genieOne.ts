/** Genie One thread: streams normalized onechat events from /api/genie-one/ask (SSE over POST). */
import { useCallback, useRef, useState } from 'react';
import { Column } from './types';

export type StepKind = 'search' | 'read' | 'sql' | 'other';

export interface OneStep {
  id: string;
  kind: StepKind;
  label: string;
  detail?: string | null;
  result?: string;
}

export type Activity = { type: 'step'; step: OneStep } | { type: 'thinking'; text: string };

export interface OneQuery {
  id: string;
  sql?: string | null;
  columns: Column[];
  rows: Array<Array<string | null>>;
  total_row_count: number;
}

export type AnswerSegment = { type: 'markdown'; text: string } | { type: 'query'; id: string; markdown: string };

export interface OneError {
  kind: 'auth' | 'disabled' | 'upstream' | 'network';
  message: string;
}

export interface OneTurn {
  id: string;
  question: string;
  status: 'streaming' | 'done' | 'error';
  startedAt: number;
  elapsedMs?: number;
  activity: Activity[];
  queries: Record<string, OneQuery>;
  answer?: AnswerSegment[];
  error?: OneError;
}

type OneEvent =
  | { type: 'meta'; conversation_id: string }
  | { type: 'step'; id: string; kind: StepKind; label: string; detail?: string | null }
  | { type: 'step_result'; id: string; summary: string }
  | { type: 'thinking'; text: string }
  | ({ type: 'query'; call_id?: string } & OneQuery)
  | { type: 'answer'; segments: AnswerSegment[] }
  | { type: 'error'; kind: OneError['kind']; message: string }
  | { type: 'done' };

export function applyEvent(t: OneTurn, ev: OneEvent): OneTurn {
  switch (ev.type) {
    case 'step':
      return { ...t, activity: [...t.activity, { type: 'step', step: { id: ev.id, kind: ev.kind, label: ev.label, detail: ev.detail } }] };
    case 'step_result':
      return { ...t, activity: t.activity.map(a => (a.type === 'step' && a.step.id === ev.id ? { ...a, step: { ...a.step, result: ev.summary } } : a)) };
    case 'thinking':
      return { ...t, activity: [...t.activity, { type: 'thinking', text: ev.text }] };
    case 'query': {
      const { id, sql, columns, rows, total_row_count } = ev;
      return { ...t, queries: { ...t.queries, [id]: { id, sql, columns, rows, total_row_count } } };
    }
    case 'answer':
      return { ...t, answer: ev.segments };
    case 'error':
      // keep the first (most informative) error if the turn already has one
      return t.error ? t : { ...t, status: 'error', error: { kind: ev.kind, message: ev.message } };
    default:
      return t;
  }
}

const RETRY_DELAY_MS = 25_000;

async function streamGenieOne(question: string, conversationId: string | undefined, onEvent: (ev: OneEvent) => void) {
  const res = await fetch('/api/genie-one/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, conversation_id: conversationId }),
  });
  if (!res.ok || !res.body) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  const handleChunk = (chunk: string) => {
    for (const line of chunk.split('\n')) {
      if (!line.startsWith('data:')) continue;
      try {
        onEvent(JSON.parse(line.slice(5)));
      } catch {
        /* skip malformed event */
      }
    }
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    buf = buf.replace(/\r\n/g, '\n');
    let i: number;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      handleChunk(buf.slice(0, i));
      buf = buf.slice(i + 2);
    }
  }
  buf = (buf + decoder.decode()).replace(/\r\n/g, '\n');
  if (buf.trim()) handleChunk(buf);
}

function freshTurn(id: string, question: string): OneTurn {
  return { id, question, status: 'streaming', startedAt: Date.now(), activity: [], queries: {} };
}

export function useGenieOne() {
  const [turns, setTurns] = useState<OneTurn[]>([]);
  const conversation = useRef<string | undefined>(undefined);

  const patch = useCallback((id: string, fn: (t: OneTurn) => OneTurn) => {
    setTurns(prev => prev.map(t => (t.id === id ? fn(t) : t)));
  }, []);

  const run = useCallback(
    async (id: string, question: string): Promise<OneError | null> => {
      const startedAt = Date.now();
      let finished = false;
      let failed: OneError | null = null;
      const fail = (error: OneError) => {
        failed = failed ?? error;
        patch(id, t => (t.status === 'error' ? t : { ...t, status: 'error', error, elapsedMs: Date.now() - startedAt }));
      };
      try {
        await streamGenieOne(question, conversation.current, ev => {
          if (ev.type === 'meta') {
            conversation.current = ev.conversation_id;
            return;
          }
          if (ev.type === 'done') {
            finished = true;
            patch(id, t => {
              if (t.status === 'error') return { ...t, elapsedMs: Date.now() - startedAt };
              if (!t.answer) return { ...t, status: 'error', error: { kind: 'upstream', message: 'Genie One finished without an answer' }, elapsedMs: Date.now() - startedAt };
              return { ...t, status: 'done', elapsedMs: Date.now() - startedAt };
            });
            return;
          }
          if (ev.type === 'error') failed = failed ?? { kind: ev.kind, message: ev.message };
          patch(id, t => (ev.type === 'error' ? { ...applyEvent(t, ev), elapsedMs: Date.now() - startedAt } : applyEvent(t, ev)));
        });
        if (!finished) fail({ kind: 'network', message: 'Connection lost before Genie One finished' });
      } catch (e) {
        fail({ kind: 'network', message: e instanceof Error ? e.message : String(e) });
      }
      return failed;
    },
    [patch],
  );

  const ask = useCallback(
    (question: string) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setTurns(prev => [...prev, freshTurn(id, question)]);
      run(id, question);
    },
    [run],
  );

  const retry = useCallback(
    (id: string) => {
      const turn = turns.find(t => t.id === id);
      if (!turn) return;
      const wasNetwork = turn.error?.kind === 'network';
      patch(id, () => freshTurn(id, turn.question));
      // One automatic re-attempt, only when the failure being retried was a dropped connection or the retried
      // run hit a transient "internal error". A conversation whose previous run was cut off stays busy upstream
      // for a while, so wait before trying again (the turn keeps showing as working). Deterministic errors do not retry.
      run(id, turn.question).then(async err => {
        if (!err || err.kind !== 'upstream') return;
        if (!wasNetwork && !/internal error/i.test(err.message)) return;
        patch(id, () => freshTurn(id, turn.question));
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY_MS));
        run(id, turn.question);
      });
    },
    [turns, patch, run],
  );

  const reset = useCallback(() => {
    conversation.current = undefined;
    setTurns([]);
  }, []);

  return { turns, busy: turns.some(t => t.status === 'streaming'), ask, retry, reset };
}
