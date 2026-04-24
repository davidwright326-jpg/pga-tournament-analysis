"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { api, PlayerProfile } from "@/lib/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from "recharts";

/** Color for highlighted stats with positive delta */
const HIGHLIGHT_POS = "#16a34a";
/** Color for highlighted stats with negative delta */
const HIGHLIGHT_NEG = "#dc2626";
/** Default player bar color */
const PLAYER_COLOR = "#15803d";
/** Winner avg bar color */
const WINNER_COLOR = "#6b7280";

export default function PlayerDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const playerId = params.id as string;
  const tournamentId = searchParams.get("tournament_id") || "";

  const [profile, setProfile] = useState<PlayerProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (playerId && tournamentId) {
      setLoading(true);
      setError(null);
      api
        .getPlayerProfile(playerId, tournamentId)
        .then(setProfile)
        .catch((err) => {
          setError(err instanceof Error ? err.message : "Failed to load profile");
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [playerId, tournamentId]);

  if (loading) {
    return (
      <div className="text-center py-12 text-gray-500" role="status" aria-label="Loading player profile">
        Loading player profile…
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600 mb-2">Failed to load player profile</p>
        <p className="text-sm text-gray-500">{error}</p>
        <a href={tournamentId ? `/?tournament_id=${tournamentId}` : "/"} className="text-green-700 hover:underline text-sm mt-4 inline-block">
          ← Back to Dashboard
        </a>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="text-center py-12 text-gray-500">
        Player not found.
        <a href="/" className="text-green-700 hover:underline text-sm ml-2">
          ← Back to Dashboard
        </a>
      </div>
    );
  }

  // Build chart data from comparison entries that have both values
  const chartData = profile.comparison
    .filter((c) => c.player_value != null && c.winner_avg != null)
    .map((c) => ({
      name: c.display_name,
      Player: Number(c.player_value!.toFixed(3)),
      "Winner Avg": Number(c.winner_avg!.toFixed(3)),
      delta: c.delta,
      highlighted: c.highlighted,
    }));

  return (
    <>
      {/* Back link */}
      <a
        href={tournamentId ? `/?tournament_id=${tournamentId}` : "/"}
        className="text-green-700 hover:underline text-sm mb-4 inline-block"
      >
        ← Back to Dashboard
      </a>

      {/* Player info card */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h1 className="text-2xl font-bold text-green-800">{profile.player_name}</h1>
        <div className="flex flex-wrap gap-6 mt-3 text-sm text-gray-600">
          <div className="flex flex-col">
            <span className="text-xs text-gray-400 uppercase tracking-wide">Fit Score</span>
            <span className="text-lg font-bold text-green-800">{profile.composite_score.toFixed(3)}</span>
          </div>
          {profile.world_ranking != null && (
            <div className="flex flex-col">
              <span className="text-xs text-gray-400 uppercase tracking-wide">World Ranking</span>
              <span className="text-lg font-semibold">#{profile.world_ranking}</span>
            </div>
          )}
          {profile.fedex_ranking != null && (
            <div className="flex flex-col">
              <span className="text-xs text-gray-400 uppercase tracking-wide">FedEx Ranking</span>
              <span className="text-lg font-semibold">#{profile.fedex_ranking}</span>
            </div>
          )}
        </div>
      </div>

      {/* Stat comparison bar chart */}
      {chartData.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Stat Comparison Chart</h2>
          <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 40)}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 20, top: 5, bottom: 5 }}>
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value: number, name: string) => [value.toFixed(3), name]}
                contentStyle={{ fontSize: 12 }}
              />
              <Legend />
              <Bar dataKey="Player" fill={PLAYER_COLOR} barSize={14}>
                {chartData.map((entry, idx) => (
                  <Cell
                    key={`player-${idx}`}
                    fill={
                      entry.highlighted
                        ? entry.delta != null && entry.delta > 0
                          ? HIGHLIGHT_POS
                          : HIGHLIGHT_NEG
                        : PLAYER_COLOR
                    }
                  />
                ))}
              </Bar>
              <Bar dataKey="Winner Avg" fill={WINNER_COLOR} barSize={14} />
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-gray-400 mt-2">
            Highlighted bars indicate stats where the player significantly exceeds (green) or falls short (red) of the historical winner average.
          </p>
        </div>
      )}

      {/* Stat comparison table */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Stat Comparison vs. Historical Winners</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" role="table">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-3 py-2 text-left">Stat</th>
                <th className="px-3 py-2 text-right">Player</th>
                <th className="px-3 py-2 text-right">Winner Avg</th>
                <th className="px-3 py-2 text-right">Delta</th>
                <th className="px-3 py-2 text-right">Weight</th>
              </tr>
            </thead>
            <tbody>
              {profile.comparison.map((c, i) => {
                const rowBg = c.highlighted
                  ? c.delta != null && c.delta > 0
                    ? "bg-green-50"
                    : "bg-red-50"
                  : i % 2 === 0
                    ? "bg-white"
                    : "bg-gray-50";

                return (
                  <tr key={c.category} className={rowBg}>
                    <td className={`px-3 py-2 ${c.highlighted ? "font-semibold" : ""}`}>
                      {c.display_name}
                      {c.highlighted && (
                        <span
                          className={`ml-2 text-xs px-1.5 py-0.5 rounded ${
                            c.delta != null && c.delta > 0
                              ? "bg-green-200 text-green-800"
                              : "bg-red-200 text-red-800"
                          }`}
                        >
                          {c.delta != null && c.delta > 0 ? "Strength" : "Weakness"}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">{c.player_value?.toFixed(3) ?? "—"}</td>
                    <td className="px-3 py-2 text-right">{c.winner_avg?.toFixed(3) ?? "—"}</td>
                    <td
                      className={`px-3 py-2 text-right font-medium ${
                        c.delta != null && c.delta > 0
                          ? "text-green-600"
                          : c.delta != null && c.delta < 0
                            ? "text-red-600"
                            : ""
                      }`}
                    >
                      {c.delta != null ? (c.delta > 0 ? "+" : "") + c.delta.toFixed(3) : "—"}
                    </td>
                    <td className="px-3 py-2 text-right">{(c.weight * 100).toFixed(1)}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
