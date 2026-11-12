import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge, Panel, Row, Stat } from "../components/ui";
import { api } from "../lib/api";
import { formatIst, formatUtc } from "../lib/time";

const money = (value: number, currency: string) =>
  `${value.toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;

export function Overview() {
  const client = useQueryClient();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 5000 });
  const connected = health.data?.mt5_connected ?? false;
  const account = useQuery({ queryKey: ["account"], queryFn: api.account, enabled: connected, refetchInterval: 5000 });
  const symbols = useQuery({ queryKey: ["symbols"], queryFn: api.symbols, enabled: connected });

  const toggle = useMutation({
    mutationFn: () => (connected ? api.mt5Disconnect() : api.mt5Connect()),
    onSettled: () => client.invalidateQueries(),
  });

  if (health.isError) {
    return (
      <Panel title="Backend unreachable">
        <p className="text-sm text-bad">
          The API at /api/health did not respond. Start it with <code className="num">python -m backend.main</code>.
        </p>
      </Panel>
    );
  }
  const h = health.data;
  const a = connected ? account.data : undefined;

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Panel
        title="MT5 connection"
        aside={
          <button
            onClick={() => toggle.mutate()}
            disabled={!h || toggle.isPending}
            className="rounded border border-line px-3 py-1 text-xs hover:border-muted disabled:opacity-50"
          >
            {connected ? "Disconnect" : "Connect"}
          </button>
        }
      >
        <Row label="Status">
          <Badge tone={connected ? "good" : "muted"}>{connected ? "Connected" : "Not connected"}</Badge>
        </Row>
        <Row label="Adapter">
          {h?.mt5_is_simulated ? <Badge tone="warn">Mock — simulated data</Badge> : <Badge tone="good">MT5 terminal</Badge>}
        </Row>
        {toggle.data?.error && <p className="mt-2 text-xs text-bad">{toggle.data.error}</p>}
      </Panel>

      <Panel title="System">
        <Row label="Backend">
          <Badge tone={h?.status === "ok" ? "good" : "bad"}>{h?.status ?? "…"}</Badge>
        </Row>
        <Row label="Database">
          <Badge tone={h?.database_ok ? "good" : "bad"}>{h?.database_ok ? "Reachable" : "Unavailable"}</Badge>
        </Row>
        <Row label="Operating mode">
          <span className="num">{h?.operating_mode ?? "…"}</span>
        </Row>
        <Row label="Kill switch">
          <Badge tone={h?.kill_switch_engaged ? "bad" : "muted"}>{h?.kill_switch_engaged ? "Engaged" : "Not engaged"}</Badge>
        </Row>
      </Panel>

      <Panel title="Server time">
        {h && (
          <>
            <div className="num text-sm">{formatUtc(h.server_time_utc)}</div>
            <div className="num mt-1 text-sm text-muted">{formatIst(h.server_time_utc)}</div>
          </>
        )}
        <p className="mt-3 text-xs text-muted">All records are stored in UTC. v{h?.version}</p>
      </Panel>

      <div className="lg:col-span-3">
        <Panel
          title="Account"
          aside={
            a &&
            (a.demo_verification.is_demo ? (
              <Badge tone="good">Demo verified</Badge>
            ) : (
              <Badge tone="bad">Not a demo account — execution blocked</Badge>
            ))
          }
        >
          {!a ? (
            <p className="text-sm text-muted">Connect to MT5 to read account details.</p>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
                <Stat label="Balance" value={money(a.balance, a.currency)} />
                <Stat label="Equity" value={money(a.equity, a.currency)} />
                <Stat label="Free margin" value={money(a.margin_free, a.currency)} />
                <Stat label="Leverage" value={`1:${a.leverage}`} note={`${a.server} · ${a.login_masked}`} />
              </div>
              {!a.balance_matches_request && (
                <p className="mt-4 text-sm text-warn">
                  Requested demo balance was {money(a.requested_initial_balance, a.currency)}; the account actually holds{" "}
                  {money(a.balance, a.currency)}.
                </p>
              )}
              {a.is_simulated && (
                <p className="mt-4 text-xs text-warn">These figures come from the mock adapter, not from a broker.</p>
              )}
            </>
          )}
        </Panel>
      </div>

      <div className="lg:col-span-3">
        <Panel title={`Forex symbols${connected && symbols.data ? ` (${symbols.data.count})` : ""}`}>
          {!connected || !symbols.data ? (
            <p className="text-sm text-muted">Symbols are discovered from the broker after connecting.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted">
                  <tr>
                    {["Broker symbol", "Pair", "Digits", "Contract", "Tick value", "Min lot", "Lot step", "Spread (pts)"].map((c) => (
                      <th key={c} className="pb-2 pr-4 font-medium">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="num">
                  {symbols.data.symbols.map((s) => (
                    <tr key={s.name} className="border-t border-line">
                      <td className="py-1.5 pr-4">{s.name}</td>
                      <td className="pr-4 text-muted">{s.canonical}</td>
                      <td className="pr-4">{s.digits}</td>
                      <td className="pr-4">{s.contract_size.toLocaleString("en-GB")}</td>
                      <td className="pr-4">{s.tick_value}</td>
                      <td className="pr-4">{s.volume_min}</td>
                      <td className="pr-4">{s.volume_step}</td>
                      <td className="pr-4">{s.spread_points}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
