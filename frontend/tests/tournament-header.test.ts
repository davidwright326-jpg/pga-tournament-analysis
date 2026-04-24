import { describe, it, expect } from "vitest";
import { formatDate, buildLocationString } from "@/components/TournamentHeader";

describe("formatDate", () => {
  it("formats a valid ISO date string", () => {
    const result = formatDate("2024-06-13");
    expect(result).toContain("Jun");
    expect(result).toContain("13");
    expect(result).toContain("2024");
  });

  it("returns the original string for invalid dates", () => {
    expect(formatDate("not-a-date")).toBe("not-a-date");
  });

  it("handles different months correctly", () => {
    const jan = formatDate("2024-01-05");
    expect(jan).toContain("Jan");
    expect(jan).toContain("5");

    const dec = formatDate("2024-12-25");
    expect(dec).toContain("Dec");
    expect(dec).toContain("25");
  });
});

describe("buildLocationString", () => {
  it("joins city and state", () => {
    expect(buildLocationString("Scottsdale", "AZ")).toBe("Scottsdale, AZ");
  });

  it("returns only city when state is null", () => {
    expect(buildLocationString("Dublin", null)).toBe("Dublin");
  });

  it("returns only state when city is null", () => {
    expect(buildLocationString(null, "GA")).toBe("GA");
  });

  it("returns empty string when both are null", () => {
    expect(buildLocationString(null, null)).toBe("");
  });
});
