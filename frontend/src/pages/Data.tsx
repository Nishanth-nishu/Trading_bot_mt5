import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, Panel } from "../components/ui";
import { api, type Dataset } from "../lib/api";
import { formatIst, formatUtc } from "../lib/time";

function coverage(d: Dataset) {
  if (d.meets_target) return <Badge tone="good">24-month target met</Badge>;
  if (d.meets_minimum) return <Badge tone="warn">12-month fallback</Badge>;
  return <Badge tone="bad">Below 12-month minimum</Badge>;
}

const QUALITY = { ok: "good", warning: "warn", fail: "bad" } as const;

export function Data() {
  const client = useQueryClient();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 5000 });
  const connected = health.data?.mt5_connected ?? false;
  const symbols = useQuery({ queryKey: ["symbols"], queryFn: api.symbols, enabled: connected });
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
  const [symbol, setSymbol] = useState("");
  const chosen = symbol || symbols.data?.symbols[0]?.name || "";

  const update = useMutation({
    mutationFn: () => api.updateData(chosen),
    onSettled: () => client.invalidateQueries({ queryKey: ["datasets"] }),
  });

  return (
    <div className="grid gap-4">
      <Panel title="Download or update">
        {!connected ? (
          <p className="text-sm text-muted">Connect to MT5 on the Overview page to download history.</p>
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={chosen}
              onChange={(e) => setSymbol(e.target.value)}
              className="rounded border border-line bg-ink px-3 py-1.5 text-sm"
            >
              {symbols.data?.symbols.map((s) => (
                <option key={s.name} value={s.name}>{s.name}</option>
              ))}
            </select>
            <button
              onClick={() => update.mutate()}
              disabled={!chosen || update.isPending}
              className="rounded border border-line px-3 py-1.5 text-sm hover:border-muted disabled:opacity-50"
            >
              {update.isPending ? "Downloading…" : "Download M5, M15, H1, H4"}
            </button>
            <span className="text-xs text-muted">
              Targets 24 months; only missing bars are fetched on later updates. Gaps are reported, never filled.
            </span>
          </div>
        )}
        {update.isError && <p className="mt-3 text-sm text-bad">{update.error.message}</p>}
        {update.data?.errors.map((e) => <p key={e} className="mt-3 text-sm text-bad">{e}</p>)}
      </Panel>

      <Panel title={`Cached datasets (${datasets.data?.length ?? 0})`}>
        {!datasets.data?.length ? (
          <p className="text-sm text-muted">No historical data cached yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted">
                <tr>
                  {["Symbol", "TF", "Source", "Bars", "Range (UTC)", "Coverage", "Quality", "Retrieved"].map((c) => (
                    <th key={c} className="pb-2 pr-4 font-medium">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {datasets.data.map((d) => (
                  <tr key={d.id} className="border-t border-line align-top">
                    <td className="num py-2 pr-4">{d.symbol}</td>
                    <td className="num pr-4">{d.timeframe}</td>
                    <td className="pr-4">
                      {d.is_simulated ? <Badge tone="warn">Simulated</Badge> : <Badge tone="good">{d.broker_server}</Badge>}
                    </td>
                    <td className="num pr-4">{d.bar_count.toLocaleString("en-GB")}</td>
                    <td className="num pr-4 text-xs">
                      {d.first_time?.slice(0, 10)} → {d.last_time?.slice(0, 10)}
                    </td>
                    <td className="pr-4">
                      {coverage(d)} <span className="num text-xs text-muted">{d.coverage_months} mo</span>
                    </td>
                    <td className="pr-4">
                      <Badge tone={QUALITY[d.quality_status as keyof typeof QUALITY] ?? "muted"}>{d.quality_status}</Badge>
                      {[...d.failures, ...d.warnings].map((m) => (
                        <div key={m} className="mt-1 max-w-xs text-xs text-muted">{m}</div>
                      ))}
                    </td>
                    <td className="num pr-4 text-xs">
                      <div>{formatUtc(d.retrieved_at)}</div>
                      <div className="text-muted">{formatIst(d.retrieved_at)}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
