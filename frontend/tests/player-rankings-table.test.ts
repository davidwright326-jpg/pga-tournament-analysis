import { describe, it, expect } from "vitest";
import {
  STAT_LABELS,
  getRankColor,
  flattenRanking,
  applyFilters,
} from "@/components/PlayerRankingsTable";
import { PlayerRanking } from "@/lib/api";

function makePlayer(overrides: Partial<PlayerRanking> = {}): PlayerRanking {
  return {
    rank: 1,
    player_id: "p1",
    player_name: "Test Player",
    composite_score: 1.5,
    world_ranking: 10,
    fedex_ranking: 5,
    stats: { sg_total: 1.2, sg_putting: 0.5 },
    stat_ranks: { sg_total: 3, sg_putting: 20 },
    ...overrides,
  };
}

describe("STAT_LABELS", () => {
  it("contains all 12 stat categories", () => {
    expect(Object.keys(STAT_LABELS)).toHaveLength(12);
    expect(STAT_LABELS).toHaveProperty("sg_total");
    expect(STAT_LABELS).toHaveProperty("scoring_avg");
  });
});

describe("getRankColor", () => {
  it("returns empty string for null", () => {
    expect(getRankColor(null)).toBe("");
    expect(getRankColor(undefined)).toBe("");
  });

  it("returns green-700 for top 10", () => {
    expect(getRankColor(1)).toContain("green-700");
    expect(getRankColor(10)).toContain("green-700");
  });

  it("returns green-600 for ranks 11-30", () => {
    expect(getRankColor(11)).toContain("green-600");
    expect(getRankColor(30)).toContain("green-600");
  });

  it("returns gray-700 for ranks 31-75", () => {
    expect(getRankColor(31)).toContain("gray-700");
    expect(getRankColor(75)).toContain("gray-700");
  });

  it("returns gray-400 for ranks above 75", () => {
    expect(getRankColor(76)).toContain("gray-400");
  });
});

describe("flattenRanking", () => {
  it("merges top-level fields and stats into a flat record", () => {
    const p = makePlayer({ stats: { sg_total: 2.0, gir: 68.5 } });
    const flat = flattenRanking(p);
    expect(flat.rank).toBe(1);
    expect(flat.player_name).toBe("Test Player");
    expect(flat.composite_score).toBe(1.5);
    expect(flat.sg_total).toBe(2.0);
    expect(flat.gir).toBe(68.5);
  });

  it("handles empty stats", () => {
    const p = makePlayer({ stats: {} });
    const flat = flattenRanking(p);
    expect(flat.rank).toBe(1);
    expect(flat.sg_total).toBeUndefined();
  });
});

describe("applyFilters", () => {
  const players = [
    makePlayer({ player_id: "a", world_ranking: 5, stats: { sg_total: 2.0 } }),
    makePlayer({ player_id: "b", world_ranking: 50, stats: { sg_total: 0.5 } }),
    makePlayer({ player_id: "c", world_ranking: null, stats: { sg_total: 1.0 } }),
  ];

  it("returns all players when no filters applied", () => {
    const result = applyFilters(players, null, {}, false);
    expect(result).toHaveLength(3);
  });

  it("filters by max world rank", () => {
    const result = applyFilters(players, 10, {}, false);
    expect(result).toHaveLength(1);
    expect(result[0].player_id).toBe("a");
  });

  it("filters by stat threshold", () => {
    const result = applyFilters(players, null, { sg_total: 1.0 }, false);
    expect(result).toHaveLength(2);
    expect(result.map((r) => r.player_id)).toEqual(["a", "c"]);
  });

  it("filters by field membership (non-null world_ranking)", () => {
    const result = applyFilters(players, null, {}, true);
    expect(result).toHaveLength(2);
    expect(result.every((r) => r.world_ranking != null)).toBe(true);
  });

  it("combines multiple filters", () => {
    const result = applyFilters(players, 50, { sg_total: 1.5 }, true);
    expect(result).toHaveLength(1);
    expect(result[0].player_id).toBe("a");
  });

  it("returns empty array when no players match", () => {
    const result = applyFilters(players, 1, {}, false);
    expect(result).toHaveLength(0);
  });
});
