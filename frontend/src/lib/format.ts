/** Formatting helpers: Genie returns every value as a string, so format by column name. */

export type ColumnKind = 'currency' | 'percent' | 'index' | 'integer' | 'decimal' | 'date' | 'text';

const NUMERIC_TYPES = ['INT', 'LONG', 'BIGINT', 'SHORT', 'DOUBLE', 'FLOAT', 'DECIMAL'];

export function columnKind(name: string, type = ''): ColumnKind {
  const n = name.toLowerCase();
  const t = type.toUpperCase();
  if (/^(year|quarter|fiscal_year)$/.test(n)) return 'text';
  if (t === 'BOOLEAN') return 'text';
  if (t === 'DATE' || t === 'TIMESTAMP' || /(^|_)(date|week|month|week_start|booking_week)($|_)/.test(n)) return 'date';
  if (/(^|_)(rgi|mpi|ari)(_|$)/.test(n)) return 'index';
  if (/(occupancy|occ$|_pct|pct_|percent|share)/.test(n)) return 'percent';
  if (/(revpar|adr|revenue|rate)/.test(n)) return 'currency';
  if (/change/.test(n)) return 'percent';
  if (NUMERIC_TYPES.some(x => t.startsWith(x))) {
    return t.startsWith('INT') || t.startsWith('LONG') || t.startsWith('BIGINT') || t.startsWith('SHORT') ? 'integer' : 'decimal';
  }
  return 'text';
}

export function isNumericKind(k: ColumnKind) {
  return k !== 'text' && k !== 'date';
}

export function formatValue(v: unknown, kind: ColumnKind): string {
  if (v === null || v === undefined || v === '') return '';
  const s = String(v);
  if (!isNumericKind(kind)) {
    if (s === 'true') return 'Yes';
    if (s === 'false') return 'No';
    if (kind === 'date' && /^\d{4}-\d{2}-\d{2}/.test(s)) return formatDate(s.slice(0, 10));
    return s;
  }
  const x = Number(s);
  if (!Number.isFinite(x)) return s;
  switch (kind) {
    case 'currency':
      return x.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: Math.abs(x) >= 100000 ? 0 : 2 });
    case 'percent':
      return `${(Math.abs(x) <= 1.5 ? x * 100 : x).toFixed(1)}%`;
    case 'index':
      return x.toFixed(1);
    case 'integer':
      return Math.round(x).toLocaleString('en-US');
    default:
      return Math.abs(x) >= 1000 ? x.toLocaleString('en-US', { maximumFractionDigits: 0 }) : x.toLocaleString('en-US', { maximumFractionDigits: 2 });
  }
}

/** Parse YYYY-MM-DD as a local calendar date (new Date('2026-10-04') would shift by timezone). */
export function parseLocalDate(s: string): Date {
  const [y, m, d] = s.slice(0, 10).split('-').map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

export function formatDate(s: string, withYear = true): string {
  const d = parseLocalDate(s);
  return d.toLocaleDateString('en-US', withYear ? { month: 'short', day: 'numeric', year: 'numeric' } : { month: 'short', day: 'numeric' });
}

export function compactNumber(n: number | null | undefined): string {
  if (n === null || n === undefined) return 'n/a';
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return String(n);
}

export function formatBytes(b: number | null | undefined): string {
  if (b === null || b === undefined) return 'n/a';
  if (b >= 1e9) return `${(b / 1e9).toFixed(1)} GB`;
  if (b >= 1e6) return `${(b / 1e6).toFixed(1)} MB`;
  return `${(b / 1e3).toFixed(0)} KB`;
}

export function prettyLabel(col: string): string {
  const special: Record<string, string> = { revpar: 'RevPAR', adr: 'ADR', rgi: 'RGI', mpi: 'MPI', ari: 'ARI', comp_revpar: 'Comp RevPAR', comp_adr: 'Comp ADR', site_id: 'Site', yoy_change: 'YoY change' };
  if (special[col]) return special[col];
  return col.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()).replace('Revpar', 'RevPAR').replace('Adr', 'ADR');
}
