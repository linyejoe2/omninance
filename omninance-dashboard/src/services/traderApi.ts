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

export interface StrategyParams {
  initial_capital: number
  partition: number
  volume_multiplier: number
  concentration_slope: number
  atr_multiplier: number
  back_test_period?: number
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

  // strategy management (omninance-backend)
  createStrategy: (body: StrategyParams) =>
    post<Record<string, unknown>>('/api/strategies', body),
  listStrategies: (status?: string) =>
    get<Record<string, unknown>[]>(`/api/strategies${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  stopStrategy: (id: string) =>
    post<Record<string, unknown>>(`/api/strategies/${encodeURIComponent(id)}/stop`, {}),
  getDailyLogs: (strategyId: string) =>
    get<Record<string, unknown>[]>(`/api/strategies/${encodeURIComponent(strategyId)}/daily-logs`),
  listTradeRecords: (strategyId?: string, limit = 100) =>
    get<Record<string, unknown>[]>(
      `/api/trade-records?limit=${limit}${strategyId ? `&strategy_id=${encodeURIComponent(strategyId)}` : ''}`
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
