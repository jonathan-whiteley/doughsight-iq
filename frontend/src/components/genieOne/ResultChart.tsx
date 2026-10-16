import { useMemo } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Column } from '../../lib/types';
import { ColumnKind, columnKind, formatValue, isNumericKind, prettyLabel } from '../../lib/format';
import { useTheme } from '../../theme/ThemeContext';

const COLORS_LIGHT = ['#FF6000', '#1A1A1A', '#FF8844', '#D64A00', '#9CA3AF', '#FFA066'];
const COLORS_HALLOWEEN = ['#FF6000', '#B57BFF', '#7CE38B', '#E8DCC8', '#FF9A4D', '#FF6000'];

interface Props {
  columns: Column[];
  rows: Array<Array<string | null>>;
}

export interface ChartSpec {
  data: Array<Record<string, string | number | null>>;
  series: string[];
  isLine: boolean;
  kind: ColumnKind;
  xKind: ColumnKind;
  label: string;
}

function toNumber(v: string | null | undefined): number | null {
  if (v === null || v === undefined || String(v).trim() === '') return null;
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}

/** Auto chart spec: first date column on X (line) or first text column (bar); first numeric column as the measure,
 *  split into series by one extra text column when present. Null when nothing can be charted. */
export function buildChartSpec(columns: Column[], rows: Array<Array<string | null>>): ChartSpec | null {
  const kinds = columns.map(c => columnKind(c.name, c.type));
  const dateI = kinds.findIndex(k => k === 'date');
  const textIs = kinds.map((k, i) => (k === 'text' ? i : -1)).filter(i => i >= 0);
  const numericIs = kinds.map((k, i) => (isNumericKind(k) && !/^(year|quarter)$/.test(columns[i].name) ? i : -1)).filter(i => i >= 0);
  // site_count is a poor default measure, but still chartable when it is the only numeric column
  const numI = numericIs.find(i => columns[i].name !== 'site_count') ?? numericIs[0] ?? -1;
  const xI = dateI >= 0 ? dateI : textIs[0];
  if (xI === undefined || xI < 0 || numI < 0 || rows.length === 0) return null;
  const seriesI = textIs.find(i => i !== xI);
  const keys = new Set<string>();
  const byX = new Map<string, Record<string, string | number | null>>();
  for (const r of rows.slice(0, 2000)) {
    const x = String(r[xI] ?? '');
    const s = seriesI !== undefined ? String(r[seriesI] ?? '') : prettyLabel(columns[numI].name);
    keys.add(s);
    if (!byX.has(x)) byX.set(x, { x });
    byX.get(x)![s] = toNumber(r[numI]);
  }
  const isLine = dateI >= 0;
  let data = [...byX.values()];
  if (isLine) data = data.sort((a, b) => String(a.x).localeCompare(String(b.x)));
  return { data, series: [...keys].slice(0, 6), isLine, kind: kinds[numI], xKind: kinds[xI], label: prettyLabel(columns[numI].name) };
}

export default function ResultChart({ columns, rows }: Props) {
  const spec = useMemo(() => buildChartSpec(columns, rows), [columns, rows]);
  const theme = useTheme();
  const COLORS = theme.isHalloween ? COLORS_HALLOWEEN : COLORS_LIGHT;

  if (!spec) return <p className="text-xs text-text-tertiary p-4">No chartable columns in this result.</p>;
  const fmt = (v: number) => formatValue(v, spec.kind);
  const tickFmt = (v: number) => {
    if (spec.kind === 'percent') return formatValue(v, 'percent');
    return new Intl.NumberFormat('en-US', {
      notation: 'compact',
      maximumFractionDigits: 1,
      ...(spec.kind === 'currency' ? { style: 'currency', currency: 'USD' } : {}),
    }).format(v);
  };
  const fmtX = (v: string) => formatValue(v, spec.xKind);
  const Chart = spec.isLine ? LineChart : BarChart;

  return (
    <div className="h-72 rounded-xl border border-gray-100 p-3">
      <ResponsiveContainer width="100%" height="100%">
        <Chart data={spec.data} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
          <CartesianGrid stroke={theme.chart.gridColor} vertical={false} />
          <XAxis dataKey="x" tickFormatter={fmtX} tick={{ fontSize: 11, fill: theme.chart.tickColor }} tickLine={false} axisLine={false} />
          <YAxis tickFormatter={tickFmt} tick={{ fontSize: 11, fill: theme.chart.tickColor }} tickLine={false} axisLine={false} width={64} />
          <Tooltip formatter={(v: number) => (v === null || v === undefined ? '' : fmt(v))} labelFormatter={fmtX} />
          {spec.series.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
          {spec.series.map((s, i) =>
            spec.isLine ? (
              <Line key={s} type="monotone" dataKey={s} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={false} />
            ) : (
              <Bar key={s} dataKey={s} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} />
            ),
          )}
        </Chart>
      </ResponsiveContainer>
    </div>
  );
}
