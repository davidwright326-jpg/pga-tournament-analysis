"use client";

import { useEffect, useState, useMemo } from "react";
import { api, Tournament, HistoryEntry, PlayerRanking } from "@/lib/api";

const STAT_LABELS: Record<string, string> = {
  sg_total: "SG:Tot",
  sg_off_tee: "SG:OTT",
  sg_approach: "SG:App",
  sg_putting: "SG:Put",
  driving_distance: "DD",
  driving_accuracy: "DA%",
  gir: "GIR%",
  scrambling: "Scr%",
};

const DISPLAY_STATS = [
  "sg_total",
  "sg_off_tee",
  "sg_approach",
  "sg_putting",
  "driving_distance",
  "driving_accuracy",
  "gir",
  "scrambling",
];

function getRankColor(rank: number | null | undefined): string {
  if (rank == null) return "";
  if (rank <= 5) return "text-green-700 font-semibold";
  if (rank <= 15) return "text-green-600";
  if (rank <= 30) return "text-gray-700";
  return "text-gray-400";
}

/** Compute the average stat value across all history entries for a given stat key. */
function winnerAvg(history: HistoryEntry[], stat: string): number | null {
  const vals = history.map((h) => h.stats?.[stat]).filter((v): v is number => v != null);
  if (vals.length === 0) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

/** Return a delta color class: green for positive, red for negative. */
function deltaColor(delta: number | null): string {
  if (delta == null) return "";
  if (delta > 0) return "text-green-600";
  if (delta < 0) return "text-red-600";
  return "";
}

export default function HistoryPage() {
  const [tournament, setTournament] = useState<Tournament | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [rankings, setRankings] = useState<PlayerRanking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Comparison overlay state
  const [selectedPlayerId, setSelectedPlayerId] = useState<string>("");
  const [showComparison, setShowComparison] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getCurrentTournament();
      setTournament(res.tournament);
      if (res.tournament) {
        const [histRes, rankRes] = await Promise.all([
          api.getTournamentHistory(res.tournament.id),
          api.getPlayerRankings(res.tournament.id, 100),
        ]);
        setHistory(histRes.history);
        setRankings(rankRes.rankings);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load history data";
      setError(msg);
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  const selectedPlayer = useMemo(
    () => rankings.find((r) => r.player_id === selectedPlayerId) ?? null,
    [rankings, selectedPlayerId]
  );

  const winnerAverages = useMemo(() => {
    const avgs: Record<string, number | null> = {};
    for (const stat of DISPLAY_STATS) {
      avgs[stat] = winnerAvg(history, stat);
    }
    return avgs;
  }, [history]);

  if (loading) {
    return (
      <div className="text-center py-12 text-gray-500" role="status">
        Loading history…
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600 mb-2">Failed to load course history</p>
        <p className="text-sm text-gray-500">{error}</p>
        <button
          onClick={loadData}
          className="mt-4 px-4 py-2 bg-green-700 text-white rounded hover:bg-green-800 text-sm"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <>
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h1 className="text-2xl font-bold text-green-800">
          Course History{tournament ? `: ${tournament.course_name}` : ""}
        </h1>
        <p className="text-gray-500 mt-1">
          Past winners and their tournament-week stats (with field ranking)
        </p>
      </div>

      {/* Player Comparison Selector */}
      {rankings.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold mb-3">Player Comparison</h2>
          <p className="text-sm text-gray-500 mb-3">
            Select a player to overlay their current stats against the historical winner averages.
          </p>
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex flex-col">
              <label htmlFor="comparePlayer" className="text-xs text-gray-500 mb-1">
                Select Player
              </label>
              <select
                id="comparePlayer"
                value={selectedPlayerId}
                onChange={(e) => {
                  setSelectedPlayerId(e.target.value);
                  setShowComparison(!!e.target.value);
                }}
                className="border rounded px-3 py-2 text-sm min-w-[240px]"
              >
                <option value="">— Choose a player —</option>
                {rankings.map((r) => (
                  <option key={r.player_id} value={r.player_id}>
                    {r.player_name} (Fit: {r.composite_score.toFixed(3)})
                  </option>
                ))}
              </select>
            </div>
            {selectedPlayerId && (
              <button
                onClick={() => {
                  setSelectedPlayerId("");
                  setShowComparison(false);
                }}
                className="px-3 py-2 text-sm text-gray-600 border rounded hover:bg-gray-50"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      )}

      {/* Comparison Overlay */}
      {showComparison && selectedPlayer && (
        <div className="bg-white rounded-lg shadow p-6 mb-6 border-l-4 border-green-600">
          <h2 className="text-lg font-semibold mb-1">
            {selectedPlayer.player_name} vs. Historical Winners
          </h2>
          <p className="text-xs text-gray-400 mb-4">
            Comparing current stats against the average of past winners at this course.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" role="table">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-3 py-2 text-left">Stat</th>
                  <th className="px-3 py-2 text-right">Player</th>
                  <th className="px-3 py-2 text-right">Winner Avg</th>
                  <th className="px-3 py-2 text-right">Delta</th>
                </tr>
              </thead>
              <tbody>
                {DISPLAY_STATS.map((stat, i) => {
                  const playerVal = selectedPlayer.stats?.[stat] ?? null;
                  const avg = winnerAverages[stat];
                  const delta =
                    playerVal != null && avg != null ? playerVal - avg : null;
                  const highlighted = delta != null && Math.abs(delta) > 0.5;
                  const rowBg = highlighted
                    ? delta > 0
                      ? "bg-green-50"
                      : "bg-red-50"
                    : i % 2 === 0
                      ? "bg-white"
                      : "bg-gray-50";

                  return (
                    <tr key={stat} className={rowBg}>
                      <td className={`px-3 py-2 ${highlighted ? "font-semibold" : ""}`}>
                        {STAT_LABELS[stat] || stat}
                        {highlighted && (
                          <span
                            className={`ml-2 text-xs px-1.5 py-0.5 rounded ${
                              delta != null && delta > 0
                                ? "bg-green-200 text-green-800"
                                : "bg-red-200 text-red-800"
                            }`}
                          >
                            {delta != null && delta > 0 ? "Strength" : "Weakness"}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {playerVal != null ? playerVal.toFixed(2) : "—"}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {avg != null ? avg.toFixed(2) : "—"}
                      </td>
                      <td className={`px-3 py-2 text-right font-medium ${deltaColor(delta)}`}>
                        {delta != null
                          ? (delta > 0 ? "+" : "") + delta.toFixed(2)
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Past Winners Table */}
      <div className="bg-white rounded-lg shadow p-6 overflow-x-auto">
        <h2 className="text-lg font-semibold mb-4">Past Winners</h2>
        <table className="w-full text-sm" role="table">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-3 py-2 text-left">Year</th>
              <th className="px-3 py-2 text-left">Winner</th>
              <th className="px-3 py-2 text-right">Score</th>
              <th className="px-3 py-2 text-right">Total</th>
              {DISPLAY_STATS.map((s) => (
                <th key={s} className="px-3 py-2 text-center">
                  <div>{STAT_LABELS[s]}</div>
                  <div className="text-[10px] text-gray-400 font-normal">
                    Val / Rank
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {history.map((h, i) => (
              <tr
                key={h.season}
                className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}
              >
                <td className="px-3 py-2">{h.season}</td>
                <td className="px-3 py-2 font-medium">{h.player_name}</td>
                <td className="px-3 py-2 text-right">
                  {h.par_relative_score != null
                    ? (h.par_relative_score > 0 ? "+" : "") +
                      h.par_relative_score
                    : "—"}
                </td>
                <td className="px-3 py-2 text-right">
                  {h.total_score != null ? h.total_score : "—"}
                </td>
                {DISPLAY_STATS.map((s) => {
                  const val = h.stats?.[s];
                  const rank = h.stat_ranks?.[s];
                  return (
                    <td key={s} className="px-3 py-2 text-center">
                      <div>{val != null ? val.toFixed(2) : "—"}</div>
                      {rank != null && (
                        <div className={`text-[10px] ${getRankColor(rank)}`}>
                          #{rank}
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}

            {/* Winner Averages Row */}
            {history.length > 0 && (
              <tr className="bg-green-50 border-t-2 border-green-200 font-semibold">
                <td className="px-3 py-2" colSpan={2}>
                  Winner Average
                </td>
                <td className="px-3 py-2 text-right">—</td>
                <td className="px-3 py-2 text-right">—</td>
                {DISPLAY_STATS.map((s) => {
                  const avg = winnerAverages[s];
                  return (
                    <td key={s} className="px-3 py-2 text-center">
                      {avg != null ? avg.toFixed(2) : "—"}
                    </td>
                  );
                })}
              </tr>
            )}
          </tbody>
        </table>
        {history.length === 0 && (
          <p className="text-gray-400 text-center py-4">
            No historical data available for this course.
          </p>
        )}
      </div>
    </>
  );
}
