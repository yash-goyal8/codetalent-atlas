import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// RTL auto-cleanup relies on a global afterEach; vitest globals are off,
// so register it explicitly.
afterEach(() => {
  cleanup();
});
