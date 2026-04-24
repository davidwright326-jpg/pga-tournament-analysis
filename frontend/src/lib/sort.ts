/**
 * Generic sorting utility for the player rankings table.
 * Supports sorting by any column with type-aware comparison.
 */
export type SortDirection = "asc" | "desc";

export interface SortConfig {
  column: string;
  direction: SortDirection;
}

/**
 * Sort an array of objects by a given column key.
 * Produces a valid total order and is idempotent.
 */
export function sortByColumn<T extends Record<string, unknown>>(
  data: T[],
  column: string,
  direction: SortDirection = "desc"
): T[] {
  const sorted = [...data].sort((a, b) => {
    const aVal = a[column];
    const bVal = b[column];

    // Handle nulls — push to end
    if (aVal == null && bVal == null) return 0;
    if (aVal == null) return 1;
    if (bVal == null) return -1;

    let cmp = 0;
    if (typeof aVal === "number" && typeof bVal === "number") {
      cmp = aVal - bVal;
    } else if (typeof aVal === "string" && typeof bVal === "string") {
      cmp = aVal.localeCompare(bVal);
    } else {
      cmp = String(aVal).localeCompare(String(bVal));
    }

    return direction === "asc" ? cmp : -cmp;
  });

  return sorted;
}
