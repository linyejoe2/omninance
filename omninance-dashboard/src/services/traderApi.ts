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
  strategyStart: (body: { initial_capital: number }) =>
    post<Record<string, unknown>>('/api/strategy/start', body),
  strategyStop: () =>
    post<Record<string, unknown>>('/api/strategy/stop', {}),
  strategyExecutions: (limit = 100) =>
    get<Record<string, unknown>[]>(`/api/strategy/executions?limit=${limit}`),
  runBacktest: (params: {
    initial_capital: number
    partition: number
    volume_multiplier: number
    concentration_slope: number
    atr_multiplier: number
    back_test_period: number
  }) => post<Record<string, unknown>>('/api/backtest', params),
}
