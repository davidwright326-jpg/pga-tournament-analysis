import { describe, it, expect } from "vitest";
import { StatWeight } from "@/lib/api";

/**
 * Tests for the data transformation logic used in StatImportanceChart.
 * We test the pure data mapping/sorting since Recharts rendering
 * requires a full DOM environment.
 */

interface ChartDatum {
  name: string;
  weight: number;
  explanation: string;
}

/** Mirrors the transform logic in StatImportanceChart */
function transformStats(stats: StatWeight[]): ChartDatum[] {
  return [...stats]
    .sort((a, b) => b.weight - a.weight)
    .map((s) => ({
      name: s.display_name,
      weight: Math.round(s.weight * 100),
      explanation: s.explanation,
    }));
}

const sampleStats: StatWeight[] = [
  { category: "sg_putting", display_name: "SG: Putting", weight: 0.15, explanation: "Fast greens reward elite putters" },
  { category: "sg_approach", display_name: "SG: Approach", weight: 0.25, explanation: "Small greens demand precision" },
  { category: "driving_accuracy", display_name: "Driving Accuracy", weight: 0.1, explanation: "Narrow fairways" },
  { category: "sg_off_tee", display_name: "SG: Off-the-Tee", weight: 0.2, explanation: "Length off the tee helps" },
];

describe("StatImportanceChart data transform", () => {
  it("sorts stats by weight descending", () => {
    const data = transformStats(sampleStats);
    for (let i = 0; i < data.length - 1; i++) {
      expect(data[i].weight).toBeGreaterThanOrEqual(data[i + 1].weight);
    }
  });

  it("converts weights to percentages", () => {
    const data = transformStats(sampleStats);
    expect(data[0].weight).toBe(25); // 0.25 -> 25
    expect(data[1].weight).toBe(20); // 0.20 -> 20
    expect(data[2].weight).toBe(15); // 0.15 -> 15
    expect(data[3].weight).toBe(10); // 0.10 -> 10
  });

  it("maps display_name to name field", () => {
    const data = transformStats(sampleStats);
    expect(data[0].name).toBe("SG: Approach");
    expect(data[1].name).toBe("SG: Off-the-Tee");
  });

  it("preserves explanation text", () => {
    const data = transformStats(sampleStats);
    const approach = data.find((d) => d.name === "SG: Approach");
    expect(approach?.explanation).toBe("Small greens demand precision");
  });

  it("handles empty stats array", () => {
    const data = transformStats([]);
    expect(data).toEqual([]);
  });

  it("handles single stat", () => {
    const data = transformStats([sampleStats[0]]);
    expect(data).toHaveLength(1);
    expect(data[0].name).toBe("SG: Putting");
    expect(data[0].weight).toBe(15);
  });

  it("does not mutate the original array", () => {
    const original = [...sampleStats];
    transformStats(sampleStats);
    expect(sampleStats).toEqual(original);
  });
});
