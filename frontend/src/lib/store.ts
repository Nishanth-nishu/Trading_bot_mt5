import { create } from "zustand";

// The twelve dashboard pages from the spec. `phase` is when a page that is
// not built yet is scheduled; the UI says so instead of showing empty shells.
export const PAGES = [
  { id: "overview", label: "Overview", phase: null },
  { id: "data", label: "Historical Data", phase: null },
  { id: "strategies", label: "Strategy Library", phase: 3 },
  { id: "research", label: "Research Lab", phase: 8 },
  { id: "portfolio", label: "Portfolio Manager", phase: 7 },
  { id: "regimes", label: "Market Regimes", phase: 4 },
  { id: "backtesting", label: "Backtesting Lab", phase: 5 },
  { id: "comparison", label: "Strategy Comparison", phase: 6 },
  { id: "charts", label: "Charts", phase: 8 },
  { id: "demo", label: "Demo Trading", phase: 9 },
  { id: "history", label: "Trade History", phase: 5 },
  { id: "experiments", label: "Experiment History", phase: 6 },
  { id: "settings", label: "Settings & Risk", phase: null },
] as const;

export type PageId = (typeof PAGES)[number]["id"];

interface UiState {
  page: PageId;
  setPage: (page: PageId) => void;
}

export const useUi = create<UiState>((set) => ({
  page: "overview",
  setPage: (page) => set({ page }),
}));
