import { expect, test } from "vitest";
import { formatIst, formatUtc } from "./time";

test("formats one instant in UTC and IST with zone labels", () => {
  const iso = "2026-11-12T20:15:30Z";
  expect(formatUtc(iso)).toBe("12 Nov 2026, 20:15:30 UTC");
  expect(formatIst(iso)).toBe("13 Nov 2026, 01:45:30 IST");
});
