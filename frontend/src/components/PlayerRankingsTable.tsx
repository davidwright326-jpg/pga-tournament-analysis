"use client";

import { useState, useMemo } from "react";
import { PlayerRanking } from "@/lib/api";
import { sortByColumn, SortDirection } from "@/lib/sort";

interface Props {
  rankings: PlayerRanking[];
  keyStats?: { category: string; weight: number }[];
  tournamentId?: string;
}

export const STAT_LABELS: Record<string, string> = {
  sg_total: "SG:Tot",
  sg_off_tee: "SG:OTT",
  sg_approach: "SG:App",
  sg_around_green: "SG:AtG",
  sg_putting: "SG:Put",
  sg_tee_to_green: "SG:T2G",
  driving_distance: "DD",
  driving_accuracy: "DA%",
  gir: "GIR%",
  scrambling: "Scr%",
  birdie_avg: "Bird",
  scoring_avg: "Scoring",
};

/** Returns a Tailwind color class based on stat rank tier. */
export function getRankColor(rank: number | null | undefined): string {
  if (rank == null) return "";
  if (rank <= 10) return "text-green-700 font-semibold";
  if (rank <= 30) return "text-green-600";
  if (rank <= 75) return "text-gray-700";
  return "text-gray-400";
}

/**
 * Flatten a PlayerRanking into a flat Record so sortByColumn can access
 * both top-level fields and nested stat values by key.
 */
export function flattenRanking(r: PlayerRanking): Record<string, unknown> {
  return {
    rank: r.rank,
    player_name: r.player_name,
    player_id: r.player_id,
    composite_score: r.composite_score,
    world_ranking: r.world_ranking,
    fedex_ranking: r.fedex_ranking,
    ...(r.stats ?? {}),
  };
}

/**
 * Apply filters to a rankings list.
 * - maxWorldRank: only include players with world_ranking <= value
 * - statThresholds: only include players whose stat value >= threshold for each specified stat
 * - fieldOnly: when true, exclude players with world_ranking === null (not in field)
 */
export function applyFilters(
  rankings: PlayerRanking[],
  maxWorldRank: number | null,
  statThresholds: Record<string, number>,
  fieldOnly: boolean
): PlayerRanking[] {
  let result = rankings;

  if (fieldOnly) {
    result = result.filter((r) => r.world_ranking != null);
  }

  if (maxWorldRank != null && !isNaN(maxWorldRank)) {
    result = result.filter(
      (r) => r.world_ranking != null && r.world_ranking <= maxWorldRank
    );
  }

  for (const [stat, threshold] of Object.entries(statThresholds)) {
    if (isNaN(threshold)) continue;
    result = result.filter((r) => {
      const val = r.stats?.[stat];
      return val != null && val >= threshold;
    });
  }

  return result;
}

export default function PlayerRankingsTable({
  rankings,
  keyStats,
  tournamentId,
}: Props) {
  const [sortCol, setSortCol] = useState("composite_score");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");
  const [maxWorldRank, setMaxWorldRank] = useState("");
  const [fieldOnly, setFieldOnly] = useState(false);
  const [statFilterKey, setStatFilterKey] = useState("");
  const [statFilterValue, setStatFilterValue] = useState("");

  const topStats = useMemo(
    () => (keyStats || []).slice(0, 6).map((s) => s.category),
    [keyStats]
  );

  const handleSort = (col: string) => {
    if (col === sortCol) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortCol(col);
      setSortDir("desc");
    }
  };

  // Build stat thresholds from the single stat filter control
  const statThresholds = useMemo(() => {
    const t: Record<string, number> = {};
    if (statFilterKey && statFilterValue) {
      const v = parseFloat(statFilterValue);
      if (!isNaN(v)) t[statFilterKey] = v;
    }
    return t;
  }, [statFilterKey, statFilterValue]);

  const filtered = useMemo(
    () =>
      applyFilters(
        rankings,
        maxWorldRank ? parseInt(maxWorldRank) : null,
        statThresholds,
        fieldOnly
      ),
    [rankings, maxWorldRank, statThresholds, fieldOnly]
  );

  const sorted = useMemo(() => {
    const flat = filtered.map(flattenRanking);
    const sortedFlat = sortByColumn(flat, sortCol, sortDir);
    // Map back to PlayerRanking objects by player_id order
    const idOrder = sortedFlat.map((f) => f.player_id as string);
    const byId = new Map(filtered.map((r) => [r.player_id, r]));
    return idOrder.map((id) => byId.get(id)!);
  }, [filtered, sortCol, sortDir]);

  const arrow = (col: string) =>
    sortCol === col ? (sortDir === "asc" ? " ↑" : " ↓") : "";

  const allStatKeys = Object.keys(STAT_LABELS);

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-6">
      {/* Filter controls */}
      <div className="flex flex-wrap justify-between items-end gap-4 mb-4">
        <h2 className="text-lg font-semibold">Player Rankings</h2>
        <div className="flex flex-wrap gap-4 items-end text-sm">
          {/* Max world rank filter */}
          <div className="flex flex-col">
            <label htmlFor="maxWorldRank" className="text-xs text-gray-500 mb-1">
              Max World Rank
            </label>
            <input
              id="maxWorldRank"
              type="number"
              value={maxWorldRank}
              onChange={(e) => setMaxWorldRank(e.target.value)}
              className="border rounded px-2 py-1 w-20"
              placeholder="All"
              min={1}
            />
          </div>

          {/* Stat threshold filter */}
          <div className="flex flex-col">
            <label htmlFor="statFilterKey" className="text-xs text-gray-500 mb-1">
              Stat Threshold
            </label>
            <div className="flex gap-1">
              <select
                id="statFilterKey"
                value={statFilterKey}
                onChange={(e) => setStatFilterKey(e.target.value)}
                className="border rounded px-2 py-1 text-sm"
              >
                <option value="">None</option>
                {allStatKeys.map((k) => (
                  <option key={k} value={k}>
                    {STAT_LABELS[k]}
                  </option>
                ))}
              </select>
              <input
                id="statFilterValue"
                type="number"
                step="any"
                value={statFilterValue}
                onChange={(e) => setStatFilterValue(e.target.value)}
                className="border rounded px-2 py-1 w-20"
                placeholder="Min"
                disabled={!statFilterKey}
              />
            </div>
          </div>

          {/* Field membership filter */}
          <div className="flex items-center gap-1 pb-1">
            <input
              id="fieldOnly"
              type="checkbox"
              checked={fieldOnly}
              onChange={(e) => setFieldOnly(e.target.checked)}
              className="rounded"
            />
            <label htmlFor="fieldOnly" className="text-xs text-gray-500">
              Field only
            </label>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm" role="table">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th
                className="px-2 py-2 text-left text-xs cursor-pointer select-none hover:bg-gray-100"
                onClick={() => handleSort("rank")}
              >
                #{arrow("rank")}
              </th>
              <th
                className="px-2 py-2 text-left text-xs cursor-pointer select-none hover:bg-gray-100"
                onClick={() => handleSort("player_name")}
              >
                Player{arrow("player_name")}
              </th>
              <th
                className="px-2 py-2 text-left text-xs cursor-pointer select-none hover:bg-gray-100"
                onClick={() => handleSort("world_ranking")}
              >
                OWGR{arrow("world_ranking")}
              </th>
              <th
                className="px-2 py-2 text-left text-xs cursor-pointer select-none hover:bg-gray-100"
                onClick={() => handleSort("composite_score")}
              >
                Fit Score{arrow("composite_score")}
              </th>
              {topStats.map((cat) => (
                <th
                  key={cat}
                  className={`px-2 py-2 text-center text-xs cursor-pointer select-none hover:bg-gray-100 ${
                    sortCol === cat ? "bg-green-50" : ""
                  }`}
                  onClick={() => handleSort(cat)}
                >
                  <div>
                    {STAT_LABELS[cat] || cat}
                    {arrow(cat)}
                  </div>
                  <div className="text-[10px] text-gray-400 font-normal">
                    Val / Rank
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((p, i) => (
              <tr
                key={p.player_id}
                className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}
              >
                <td className="px-2 py-2">{i + 1}</td>
                <td className="px-2 py-2">
                  <a
                    href={`/player/${p.player_id}${
                      tournamentId ? `?tournament_id=${tournamentId}` : ""
                    }`}
                    className="text-green-700 hover:underline"
                  >
                    {p.player_name}
                  </a>
                </td>
                <td className="px-2 py-2">{p.world_ranking ?? "-"}</td>
                <td className="px-2 py-2 font-semibold">
                  {p.composite_score.toFixed(3)}
                </td>
                {topStats.map((cat) => {
                  const val = p.stats?.[cat];
                  const rank = p.stat_ranks?.[cat];
                  return (
                    <td
                      key={cat}
                      className={`px-2 py-2 text-center ${
                        sortCol === cat ? "bg-green-50" : ""
                      }`}
                    >
                      <div>{val != null ? val.toFixed(2) : "-"}</div>
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
          </tbody>
        </table>
      </div>
      {sorted.length === 0 && (
        <p className="text-gray-400 text-center py-4">
          No players match the current filters.
        </p>
      )}
    </div>
  );
}
