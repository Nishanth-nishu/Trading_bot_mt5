import { useQuery } from "@tanstack/react-query";
import { Panel, Row } from "../components/ui";
import { api } from "../lib/api";

const RISK_LABELS: Record<string, string> = {
  risk_per_trade_pct: "Risk per trade (%)",
  max_daily_loss_pct: "Maximum daily loss (%)",
  max_total_drawdown_pct: "Maximum total drawdown (%)",
  max_open_positions: "Maximum open positions",
  max_trades_per_day: "Maximum trades per day",
  min_reward_to_risk: "Minimum reward-to-risk",
  max_concurrent_planned_risk_pct: "Maximum concurrent planned risk (%)",
  mandatory_stop_loss: "Mandatory stop-loss",
};

export function Settings() {
  const state = useQuery({ queryKey: ["system-state"], queryFn: api.systemState });
  const s = state.data;
  if (!s) return <p className="text-sm text-muted">{state.isError ? "Backend unreachable." : "Loading…"}</p>;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Risk limits">
        {Object.entries(s.risk).map(([key, value]) => (
          <Row key={key} label={RISK_LABELS[key] ?? key}>
            <span className="num">{typeof value === "boolean" ? (value ? "Yes" : "No") : value}</span>
          </Row>
        ))}
        <p className="mt-3 text-xs text-muted">
          Read-only for now. These are set through TRADELAB_RISK_* environment variables; editing them here arrives
          with the risk engine.
        </p>
      </Panel>
      <Panel title="Research configuration">
        <Row label="Execution">Demo accounts only</Row>
        <Row label="Operating mode"><span className="num">{s.operating_mode}</span></Row>
        <Row label="Timeframes"><span className="num">{s.timeframes.join(", ")}</span></Row>
        <Row label="History target"><span className="num">{s.history_target_months} months</span></Row>
        <Row label="History minimum"><span className="num">{s.history_minimum_months} months</span></Row>
        <Row label="Demo experiment"><span className="num">{s.demo_experiment_days} days</span></Row>
      </Panel>
    </div>
  );
}
