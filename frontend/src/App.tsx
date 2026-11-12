import { Panel } from "./components/ui";
import { PAGES, useUi } from "./lib/store";
import { Data } from "./pages/Data";
import { Overview } from "./pages/Overview";
import { Settings } from "./pages/Settings";

export function App() {
  const { page, setPage } = useUi();
  const current = PAGES.find((p) => p.id === page)!;

  return (
    <div className="flex min-h-screen flex-col">
      <div className="border-b border-warn/30 bg-warn/10 px-4 py-1.5 text-center text-xs text-warn">
        Demo accounts only. This application has no real-money execution.
      </div>
      <div className="flex flex-1 flex-col md:flex-row">
        <nav className="border-b border-line bg-panel md:w-56 md:border-b-0 md:border-r">
          <div className="px-4 py-4 text-sm font-semibold tracking-wide">TradeLab MT5</div>
          <ul className="flex gap-1 overflow-x-auto px-2 pb-2 md:block md:space-y-0.5">
            {PAGES.map((p) => (
              <li key={p.id}>
                <button
                  onClick={() => setPage(p.id)}
                  className={`w-full whitespace-nowrap rounded px-3 py-1.5 text-left text-sm ${
                    p.id === page ? "bg-line text-text" : p.phase ? "text-muted/60 hover:text-muted" : "text-muted hover:text-text"
                  }`}
                >
                  {p.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <main className="flex-1 p-4 md:p-6">
          <h1 className="mb-4 text-lg font-semibold">{current.label}</h1>
          {page === "overview" && <Overview />}
          {page === "data" && <Data />}
          {page === "settings" && <Settings />}
          {current.phase && (
            <Panel title="Not built yet">
              <p className="text-sm text-muted">
                This page is scheduled for Phase {current.phase} of the roadmap. Nothing is hidden behind it.
              </p>
            </Panel>
          )}
        </main>
      </div>
    </div>
  );
}
