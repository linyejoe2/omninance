async function get<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

// chip-tracker backtest params (still uses `partition`)
export interface StrategyParams {
  initial_capital: number
  partition: number
  volume_multiplier: number
  concentration_slope: number
  atr_multiplier: number
  back_test_period?: number
}

// omninance-backend strategy store (PostgreSQL)
export interface CreateStrategyParams {
  name: string
  initial_capital: number
  position_slots: number
  volume_multiplier: number
  concentration_slope: number
  atr_multiplier: number
}

export interface StrategyRow {
  id: string
  name: string
  initial_capital: number
  position_slots: number
  volume_multiplier: number
  concentration_slope: number
  atr_multiplier: number
  status: 'active' | 'stopped'
  create_at: string
}

export interface PositionRow {
  id: number
  strategy_id: string
  symbol: string
  quantity: number
  average_cost: number
  current_price: number
  highest_price: number
  trailing_stop_price: number
  create_at: string
  update_at: string
}

export interface OrderRecordRow {
  id: number
  strategy_id: string
  broker_order_id: string | null
  symbol: string
  action: 'BUY' | 'SELL'
  status: 'PENDING' | 'PARTIAL' | 'FILLED' | 'CANCELLED' | 'FAILED' | 'TIMEOUT'
  sell_reason: string | null
  req_quantity: number
  req_price: number | null
  filled_quantity: number
  filled_price: number | null
  fee: number
  tax: number
  realized_pnl: number
  return_rate: number
  error_msg: string | null
  create_at: string
  update_at: string
}

export interface BuySignalSnapshot {
  symbol: string
  price: number | null
  atr: number | null
}

export interface HoldingSnapshot {
  symbol: string
  quantity: number
  average_cost: number
  current_price: number
  highest_price: number
  trailing_stop_price: number
}

export type DailyLogStatus = 'signal-generated' | 'executing' | 'finalizing' | 'ended'

export interface DailyLogRow {
  id: number
  strategy_id: string
  status: DailyLogStatus
  record_date: string
  execute_at: string | null
  total_equity: number
  available_balance: number
  daily_pnl: number
  holdings_snapshot: HoldingSnapshot[]
  buy_signals_snapshot: BuySignalSnapshot[]
  sell_signals_snapshot: { symbol: string }[]
  errors: string[]
}

export interface StockListItem {
  symbol: string
  name: string | null
  date: string | null
  rank: number | null
  capitals: number | null
  close: number | null
  mkt_val: number | null
  mkt_val_ratio: number | null
  desc: string | null
  tag: string | null
}

export interface TickerPoint {
  symbol: string
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface HolderRow {
  symbol: string
  date: string
  total_sheets: number
  total_shareholders: number
  avg_sheets_per_person: number
  over400_sheets: number
  over400_percentage: number
  over400_count: number
  count_400_to_600: number
  count_600_to_800: number
  count_800_to_1000: number
  over1000_count: number
  over1000_percentage: number
  close_price: number | null
}

export interface ScheduleLastRun {
  job: string
  status: string
  started_at: string
  finished_at: string
  duration_ms: number
}

export interface ScheduleInfo {
  job: string
  schedule: string
  last_run: ScheduleLastRun | null
}

export interface ScheduleLogRow {
  job: string
  status: string
  started_at: string
  finished_at: string
  duration_ms: number
  output: Record<string, unknown> | null
}

export const traderApi = {
  tradeStatus:  () => get<Record<string, unknown>>('/api/account/trade-status'),
  marketStatus: () => get<Record<string, unknown>>('/api/account/market-status'),
  certInfo:     () => get<Record<string, unknown>>('/api/account/cert-info'),
  keyInfo:      () => get<Record<string, unknown>>('/api/account/key-info'),
  inventories:  () => get<Record<string, unknown>[]>('/api/account/inventories'),
  balance:      () => get<Record<string, unknown>>('/api/account/balance'),
  settlements:  () => get<Record<string, unknown>[]>('/api/account/settlements'),
  signals:      () => get<Record<string, unknown>>('/api/signals'),
  priceHistory: (symbols: string, days: number) =>
    get<Record<string, unknown>[]>(`/api/price-history?symbols=${encodeURIComponent(symbols)}&days=${days}`),

  // strategy management (omninance-backend, PostgreSQL-backed)
  createStrategy: (body: CreateStrategyParams) =>
    post<{ strategy: StrategyRow }>('/api/strategies', body),
  listStrategies: (status?: string) =>
    get<StrategyRow[]>(`/api/strategies${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  stopStrategy: (id: string) =>
    post<Record<string, unknown>>(`/api/strategies/${encodeURIComponent(id)}/stop`, {}),
  getPositions: (strategyId: string) =>
    get<PositionRow[]>(`/api/strategies/${encodeURIComponent(strategyId)}/positions`),
  getDailyLogs: (strategyId: string) =>
    get<DailyLogRow[]>(`/api/strategies/${encodeURIComponent(strategyId)}/daily-logs`),
  listOrderRecords: (strategyId?: string, limit = 100) =>
    get<OrderRecordRow[]>(
      `/api/order-records?limit=${limit}${strategyId ? `&strategy_id=${encodeURIComponent(strategyId)}` : ''}`
    ),

  // backtest (chip-tracker)
  runBacktest: (params: StrategyParams) =>
    post<Record<string, unknown>>('/api/backtest', params),

  // data explorer (omninance-backend, MongoDB-backed)
  listStockList: () => get<StockListItem[]>('/api/stock-list'),
  getStockTickers: (symbol: string) =>
    get<TickerPoint[]>(`/api/stock-list/${encodeURIComponent(symbol)}/tickers`),
  getStockHolders: (symbol: string) =>
    get<HolderRow[]>(`/api/stock-list/${encodeURIComponent(symbol)}/holders`),

  // schedules (omninance-backend, MongoDB-backed)
  listSchedules: () => get<ScheduleInfo[]>('/api/schedules'),
  getScheduleLogs: (job: string, limit = 50) =>
    get<ScheduleLogRow[]>(`/api/schedules/${encodeURIComponent(job)}/logs?limit=${limit}`),
  triggerSchedule: (job: string) =>
    post<Record<string, unknown>>(`/api/schedules/${encodeURIComponent(job)}/trigger`, {}),
}
