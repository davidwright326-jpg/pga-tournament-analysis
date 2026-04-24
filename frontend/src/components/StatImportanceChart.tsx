"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  TooltipProps,
} from "recharts";
import { StatWeight } from "@/lib/api";

interface Props {
  stats: StatWeight[];
}

interface ChartDatum {
  name: string;
  weight: number;
  explanation: string;
}

const COLORS = [
  "#166534",
  "#15803d",
  "#16a34a",
  "#22c55e",
  "#4ade80",
  "#86efac",
  "#a7f3d0",
  "#bbf7d0",
  "#d1fae5",
  "#dcfce7",
  "#ecfdf5",
  "#f0fdf4",
];

function CustomTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;

  const datum = payload[0].payload as ChartDatum;

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 max-w-xs">
      <p className="font-semibold text-gray-900 text-sm">{datum.name}</p>
      <p className="text-green-700 text-sm font-medium mt-1">
        Importance: {datum.weight}%
      </p>
      {datum.explanation && (
        <p className="text-gray-600 text-xs mt-1">{datum.explanation}</p>
      )}
    </div>
  );
}

export default function StatImportanceChart({ stats }: Props) {
  const data: ChartDatum[] = [...stats]
    .sort((a, b) => b.weight - a.weight)
    .map((s) => ({
      name: s.display_name,
      weight: Math.round(s.weight * 100),
      explanation: s.explanation,
    }));

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-6" role="region" aria-label="Stat importance chart">
      <h2 className="text-lg font-semibold mb-4">Key Stats for This Course</h2>
      <ResponsiveContainer width="100%" height={Math.max(350, data.length * 32)}>
        <BarChart data={data} layout="vertical" margin={{ left: 140, right: 20 }}>
          <XAxis
            type="number"
            domain={[0, "auto"]}
            tickFormatter={(v: number) => `${v}%`}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={130}
            tick={{ fontSize: 12 }}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(0,0,0,0.05)" }} />
          <Bar dataKey="weight" radius={[0, 4, 4, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
