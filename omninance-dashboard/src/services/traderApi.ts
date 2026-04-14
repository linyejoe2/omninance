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
  back_test_period: number
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
}
