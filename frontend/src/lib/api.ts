export interface Health {
  status: string;
  app: string;
  version: string;
  environment: string;
  server_time_utc: string;
  database_ok: boolean;
  mt5_adapter: string;
  mt5_is_simulated: boolean;
  mt5_connected: boolean;
  operating_mode: string;
  kill_switch_engaged: boolean;
  real_money_execution: boolean;
}

export interface MT5Status {
  adapter: string;
  is_simulated: boolean;
  connected: boolean;
  terminal_name: string | null;
  terminal_build: number | null;
  error: string | null;
}

export interface Account {
  is_simulated: boolean;
  login_masked: string;
  server: string;
  company: string;
  currency: string;
  leverage: number;
  balance: number;
  equity: number;
  margin: number;
  margin_free: number;
  margin_level: number | null;
  trade_mode: string;
  demo_verification: { is_demo: boolean; reason: string };
  requested_initial_balance: number;
  balance_discrepancy: number;
  balance_matches_request: boolean;
}

export interface SymbolSpec {
  name: string;
  canonical: string;
  digits: number;
  tick_size: number;
  tick_value: number;
  contract_size: number;
  volume_min: number;
  volume_max: number;
  volume_step: number;
  spread_points: number;
  trade_allowed: boolean;
}

export interface Symbols {
  is_simulated: boolean;
  count: number;
  symbols: SymbolSpec[];
}

export interface SystemState {
  operating_mode: string;
  kill_switch_engaged: boolean;
  demo_only: boolean;
  timeframes: string[];
  history_target_months: number;
  history_minimum_months: number;
  demo_experiment_days: number;
  risk: Record<string, number | boolean>;
}

export interface Dataset {
  id: number;
  source: string;
  is_simulated: boolean;
  broker_server: string;
  symbol: string;
  canonical: string;
  timeframe: string;
  bar_count: number;
  first_time: string | null;
  last_time: string | null;
  coverage_months: number;
  meets_target: boolean;
  meets_minimum: boolean;
  quality_status: string;
  failures: string[];
  warnings: string[];
  time_basis: string;
  retrieved_at: string;
}

async function request<T>(path: string, method: "GET" | "POST" = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/health"),
  systemState: () => request<SystemState>("/system/state"),
  mt5Status: () => request<MT5Status>("/mt5/status"),
  mt5Connect: () => request<MT5Status>("/mt5/connect", "POST"),
  mt5Disconnect: () => request<MT5Status>("/mt5/disconnect", "POST"),
  account: () => request<Account>("/mt5/account"),
  symbols: () => request<Symbols>("/mt5/symbols"),
  datasets: () => request<Dataset[]>("/data/datasets"),
  updateData: (symbol: string) =>
    request<{ datasets: Dataset[]; errors: string[] }>("/data/update", "POST", { symbol }),
};
