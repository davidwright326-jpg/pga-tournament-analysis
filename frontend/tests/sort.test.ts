/**
 * P8: Sort stability property test.
 * Sorting by any column must produce a valid total order and be idempotent.
 * **Validates: Requirements 4.3**
 */
import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { sortByColumn, SortDirection } from "../src/lib/sort";

const playerArb = fc.record({
  rank: fc.integer({ min: 1, max: 200 }),
  player_name: fc.string({ minLength: 1, maxLength: 20 }),
  composite_score: fc.double({ min: -10, max: 10, noNaN: true }),
  world_ranking: fc.oneof(fc.constant(null), fc.integer({ min: 1, max: 500 })),
});

const rankingsArb = fc.array(playerArb, { minLength: 1, maxLength: 50 });

const columnArb = fc.constantFrom("rank", "player_name", "composite_score", "world_ranking");
const directionArb = fc.constantFrom<SortDirection>("asc", "desc");

describe("P8: Sort stability", () => {
  it("sorting produces a valid total order for the sorted column", () => {
    fc.assert(
      fc.property(rankingsArb, columnArb, directionArb, (rankings, column, direction) => {
        const sorted = sortByColumn(rankings as Record<string, unknown>[], column, direction);

        // Verify order
        for (let i = 0; i < sorted.length - 1; i++) {
          const a = sorted[i][column];
          const b = sorted[i + 1][column];

          // Nulls go to end
          if (a == null) continue;
          if (b == null) continue;

          if (typeof a === "number" && typeof b === "number") {
            if (direction === "desc") {
              expect(a).toBeGreaterThanOrEqual(b);
            } else {
              expect(a).toBeLessThanOrEqual(b);
            }
          } else {
            const cmp = String(a).localeCompare(String(b));
            if (direction === "desc") {
              expect(cmp).toBeGreaterThanOrEqual(0);
            } else {
              expect(cmp).toBeLessThanOrEqual(0);
            }
          }
        }
      }),
      { numRuns: 100 }
    );
  });

  it("sorting is idempotent - sorting twice gives same result", () => {
    fc.assert(
      fc.property(rankingsArb, columnArb, directionArb, (rankings, column, direction) => {
        const sortedOnce = sortByColumn(rankings as Record<string, unknown>[], column, direction);
        const sortedTwice = sortByColumn(sortedOnce, column, direction);

        expect(sortedTwice).toEqual(sortedOnce);
      }),
      { numRuns: 100 }
    );
  });

  it("sorted result has same length as input", () => {
    fc.assert(
      fc.property(rankingsArb, columnArb, directionArb, (rankings, column, direction) => {
        const sorted = sortByColumn(rankings as Record<string, unknown>[], column, direction);
        expect(sorted.length).toBe(rankings.length);
      }),
      { numRuns: 50 }
    );
  });
});
