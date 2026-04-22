import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import StopIcon from '@mui/icons-material/Stop'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import Grid from '@mui/material/Grid'
import Stack from '@mui/material/Stack'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import { useCallback, useEffect, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { traderApi, StrategyParams } from '../../services/traderApi'

interface Strategy {
  _id: string
  initial_capital: number
  partition: number
  volume_multiplier: number
  concentration_slope: number
  atr_multiplier: number
  back_test_period: number
  status: string
  create_at: string
}

interface DailyLog {
  _id: number
  strategy_id: string
  run_date: string
  total_equity: number | null
  available_balance: number | null
  daily_pnl: number | null
  holdings_snapshot: string | null
  error: string | null
}

interface Holding {
  symbol: string
  qty: number
  cost: number
}

interface TradeRecord {
  _id: number
  strategy_id: string
  order_id: string | null
  action: 'BUY' | 'SELL'
  symbol: string
  quantity: number | null
  price: number | null
  status: string
  pnl: number
  fee: number
  return_rate: number
  result: string | null
  error: string | null
  create_at: string
  update_at: string | null
}

interface StrategyWithStats extends Strategy {
  total_equity: number | null
  daily_pnl: number | null
  available_balance: number | null
  holding_count: number
  buy_count: number
  sell_count: number
}

const DEFAULT_PARAMS: StrategyParams = {
  initial_capital: 100000,
  partition: 10,
  volume_multiplier: 2,
  concentration_slope: 0.02,
  atr_multiplier: 4,
  back_test_period: 4,
}

export function ExecutePanel() {
  const [params, setParams] = useState<StrategyParams>(DEFAULT_PARAMS)
  const [strategies, setStrategies] = useState<StrategyWithStats[]>([])
  const [strategiesLoading, setStrategiesLoading] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [stopLoading, setStopLoading] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detailLogs, setDetailLogs] = useState<DailyLog[]>([])
  const [tradeRecords, setTradeRecords] = useState<TradeRecord[]>([])
  const [detailLoading, setDetailLoading] = useState(false)

  const set = (key: keyof StrategyParams) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setParams((p) => ({ ...p, [key]: Number(e.target.value) }))

  const fetchStrategies = useCallback(async () => {
    setStrategiesLoading(true)
    const today = new Date().toLocaleDateString('sv-SE') // YYYY-MM-DD local
    try {
      const raw = (await traderApi.listStrategies()) as unknown as Strategy[]

      const withStats = await Promise.all(
        raw.map(async (s): Promise<StrategyWithStats> => {
          const empty: StrategyWithStats = {
            ...s, total_equity: null, daily_pnl: null, available_balance: null,
            holding_count: 0, buy_count: 0, sell_count: 0,
          }
          try {
            const [logs, records] = await Promise.all([
              traderApi.getDailyLogs(s._id),
              traderApi.listTradeRecords(s._id, 1000),
            ])
            const latestLog = (logs as unknown as DailyLog[])[0] ?? null
            const allRecords = records as unknown as TradeRecord[]
            const todayRecords = allRecords.filter((r) => r.create_at.startsWith(today))
            const holdings: Holding[] = (() => {
              if (!latestLog?.holdings_snapshot) return []
              try { return JSON.parse(latestLog.holdings_snapshot) } catch { return [] }
            })()
            return {
              ...s,
              total_equity: latestLog?.total_equity ?? null,
              daily_pnl: latestLog?.daily_pnl ?? null,
              available_balance: latestLog?.available_balance ?? null,
              holding_count: holdings.length,
              buy_count: todayRecords.filter((r) => r.action === 'BUY').length,
              sell_count: todayRecords.filter((r) => r.action === 'SELL').length,
            }
          } catch {
            return empty
          }
        })
      )
      setStrategies(withStats)
    } catch {
      // silently ignore
    } finally {
      setStrategiesLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStrategies()
  }, [fetchStrategies])

  const handleSelectStrategy = useCallback(async (id: string) => {
    if (selectedId === id) {
      setSelectedId(null)
      setDetailLogs([])
      setTradeRecords([])
      return
    }
    setSelectedId(id)
    setDetailLoading(true)
    try {
      const [logs, records] = await Promise.all([
        traderApi.getDailyLogs(id),
        traderApi.listTradeRecords(id, 1000),
      ])
      setDetailLogs((logs as unknown as DailyLog[]).slice().reverse()) // oldest first for chart
      setTradeRecords(records as unknown as TradeRecord[])
    } catch {
      setDetailLogs([])
      setTradeRecords([])
    } finally {
      setDetailLoading(false)
    }
  }, [selectedId])

  const handleCreate = async () => {
    setActionError(null)
    setCreateLoading(true)
    try {
      await traderApi.createStrategy(params)
      await fetchStrategies()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    } finally {
      setCreateLoading(false)
    }
  }

  const handleStop = async (id: string) => {
    setStopLoading(id)
    try {
      await traderApi.stopStrategy(id)
      if (selectedId === id) {
        setSelectedId(null)
        setDetailLogs([])
        setTradeRecords([])
      }
      await fetchStrategies()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    } finally {
      setStopLoading(null)
    }
  }

  const activeStrategies = strategies.filter((s) => s.status === 'active')
  const stoppedStrategies = strategies.filter((s) => s.status === 'stopped')
  const selectedStrategy = strategies.find((s) => s._id === selectedId) ?? null

  // Today's date prefix (YYYY-MM-DD) for filtering trade records
  const todayPrefix = new Date().toLocaleDateString('sv-SE') // 'sv-SE' gives YYYY-MM-DD in local time

  const todayBuys  = tradeRecords.filter((r) => r.action === 'BUY'  && r.create_at.startsWith(todayPrefix))
  const todaySells = tradeRecords.filter((r) => r.action === 'SELL' && r.create_at.startsWith(todayPrefix))

  // Parse holdings from the most recent log that has a snapshot
  const latestHoldings: Holding[] = (() => {
    const logWithHoldings = [...detailLogs].reverse().find((l) => l.holdings_snapshot)
    if (!logWithHoldings?.holdings_snapshot) return []
    try {
      return JSON.parse(logWithHoldings.holdings_snapshot) as Holding[]
    } catch {
      return []
    }
  })()

  // Chart data: equity over time
  const chartData = detailLogs
    .filter((l) => l.total_equity != null || l.available_balance != null)
    .map((l) => ({
      date: l.run_date,
      total_equity: l.total_equity,
      available_balance: l.available_balance,
      daily_pnl: l.daily_pnl,
    }))

  return (
    <Stack spacing={3}>
      {/* Params form */}
      <Card variant="outlined">
        <CardContent>
          <Typography variant="subtitle2" fontWeight="bold" mb={2}>建立新策略</Typography>
          <Grid container spacing={2}>
            <Grid item xs={6} sm={4}>
              <TextField label="初始資金 (NT$)" type="number" size="small" fullWidth
                value={params.initial_capital} onChange={set('initial_capital')} disabled={createLoading} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="資金分份" type="number" size="small" fullWidth
                value={params.partition} onChange={set('partition')} disabled={createLoading} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="成交量倍數" type="number" size="small" fullWidth
                value={params.volume_multiplier} onChange={set('volume_multiplier')} disabled={createLoading}
                inputProps={{ step: 0.1 }} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="大戶籌碼斜率" type="number" size="small" fullWidth
                value={params.concentration_slope} onChange={set('concentration_slope')} disabled={createLoading}
                inputProps={{ step: 0.001 }} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="止損 ATR 乘數" type="number" size="small" fullWidth
                value={params.atr_multiplier} onChange={set('atr_multiplier')} disabled={createLoading}
                inputProps={{ step: 0.5 }} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="回測年數" type="number" size="small" fullWidth
                value={params.back_test_period} onChange={set('back_test_period')} disabled={createLoading}
                inputProps={{ min: 1, max: 10 }} />
            </Grid>
          </Grid>

          <Box mt={2} display="flex" alignItems="center" gap={2}>
            <Button
              variant="contained"
              color="success"
              startIcon={createLoading ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
              onClick={handleCreate}
              disabled={createLoading}
            >
              {createLoading ? '建立中…' : '建立策略'}
            </Button>
            {actionError && (
              <Typography variant="body2" color="error">{actionError}</Typography>
            )}
          </Box>
        </CardContent>
      </Card>

      {/* Strategy list */}
      <Card variant="outlined">
        <CardContent>
          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <Typography variant="subtitle2" fontWeight="bold">執行中策略</Typography>
            {strategiesLoading && <CircularProgress size={14} />}
            <Chip label={activeStrategies.length} size="small" color="success" variant="outlined" />
            <Typography variant="caption" color="text.secondary">點選列查看詳情</Typography>
          </Box>

          {activeStrategies.length === 0 ? (
            <Typography variant="body2" color="text.secondary">無執行中的策略</Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell align="right">初始資金</TableCell>
                  <TableCell align="right">總資產</TableCell>
                  <TableCell align="right">當日盈虧</TableCell>
                  <TableCell align="right">可用餘額</TableCell>
                  <TableCell align="right">持倉數</TableCell>
                  <TableCell align="right">今日買入</TableCell>
                  <TableCell align="right">今日賣出</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {activeStrategies.map((s) => (
                  <TableRow
                    key={s._id}
                    hover
                    selected={selectedId === s._id}
                    onClick={() => handleSelectStrategy(s._id)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: 11 }}>{s._id.slice(0, 8)}</TableCell>
                    <TableCell align="right">{s.initial_capital.toLocaleString()}</TableCell>
                    <TableCell align="right">{s.total_equity != null ? s.total_equity.toLocaleString() : '—'}</TableCell>
                    <TableCell align="right"
                      sx={{ color: s.daily_pnl == null ? undefined : s.daily_pnl >= 0 ? 'success.main' : 'error.main' }}>
                      {s.daily_pnl != null ? s.daily_pnl.toLocaleString() : '—'}
                    </TableCell>
                    <TableCell align="right">{s.available_balance != null ? s.available_balance.toLocaleString() : '—'}</TableCell>
                    <TableCell align="right">{s.holding_count}</TableCell>
                    <TableCell align="right">{s.buy_count}</TableCell>
                    <TableCell align="right">{s.sell_count}</TableCell>
                    <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                      <Button
                        size="small"
                        color="error"
                        variant="outlined"
                        startIcon={stopLoading === s._id
                          ? <CircularProgress size={12} color="inherit" />
                          : <StopIcon fontSize="small" />}
                        onClick={() => handleStop(s._id)}
                        disabled={stopLoading === s._id}
                        sx={{ minWidth: 0, px: 1 }}
                      >
                        停止
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {stoppedStrategies.length > 0 && (
            <>
              <Divider sx={{ my: 1.5 }} />
              <Typography variant="caption" color="text.secondary">
                已停止：{stoppedStrategies.length} 筆
              </Typography>
            </>
          )}
        </CardContent>
      </Card>

      {/* Strategy detail panel */}
      {selectedStrategy && (
        <Card variant="outlined">
          <CardContent>
            <Box display="flex" alignItems="center" gap={1} mb={2}>
              <Typography variant="subtitle2" fontWeight="bold">
                策略詳情 — {selectedStrategy._id.slice(0, 8)}
              </Typography>
              {detailLoading && <CircularProgress size={14} />}
              <Chip
                label={selectedStrategy.status === 'active' ? '執行中' : '已停止'}
                size="small"
                color={selectedStrategy.status === 'active' ? 'success' : 'default'}
                variant="outlined"
              />
            </Box>

            {/* Params summary */}
            <Grid container spacing={1} mb={2}>
              {[
                { label: '初始資金', value: `NT$ ${selectedStrategy.initial_capital.toLocaleString()}` },
                { label: '資金分份', value: selectedStrategy.partition },
                { label: '成交量倍數', value: selectedStrategy.volume_multiplier },
                { label: '大戶籌碼斜率', value: selectedStrategy.concentration_slope },
                { label: '止損 ATR 乘數', value: selectedStrategy.atr_multiplier },
                { label: '回測年數', value: `${selectedStrategy.back_test_period} 年` },
              ].map(({ label, value }) => (
                <Grid item xs={6} sm={4} key={label}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">{label}</Typography>
                    <Typography variant="body2" fontWeight="medium">{value}</Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>

            <Divider sx={{ mb: 2 }} />

            {detailLogs.length === 0 && !detailLoading ? (
              <Typography variant="body2" color="text.secondary">尚無每日執行紀錄</Typography>
            ) : (
              <>
                {/* Equity line chart */}
                {chartData.length > 0 && (
                  <>
                    <Typography variant="subtitle2" fontWeight="bold" mb={1}>資產走勢</Typography>
                    <ResponsiveContainer width="100%" height={220}>
                      <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 11 }}
                          tickFormatter={(v: string) => v.slice(5)}
                          minTickGap={30}
                        />
                        <YAxis
                          tick={{ fontSize: 11 }}
                          tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}K`}
                          width={48}
                        />
                        <Tooltip
                          formatter={(value: number, name: string) => [
                            `NT$ ${value.toLocaleString()}`,
                            name === 'total_equity' ? '總資產' : '可用餘額',
                          ]}
                          labelFormatter={(l: string) => l}
                          contentStyle={{ fontSize: 12 }}
                        />
                        <Legend
                          formatter={(v) => (v === 'total_equity' ? '總資產' : '可用餘額')}
                          wrapperStyle={{ fontSize: 12 }}
                        />
                        <Line type="monotone" dataKey="total_equity" stroke="#4fc3f7" dot={false}
                          strokeWidth={2} connectNulls />
                        <Line type="monotone" dataKey="available_balance" stroke="#81c784" dot={false}
                          strokeWidth={1.5} connectNulls />
                      </LineChart>
                    </ResponsiveContainer>
                    <Divider sx={{ my: 2 }} />
                  </>
                )}

                {/* Current holdings */}
                <Typography variant="subtitle2" fontWeight="bold" mb={1}>
                  當前持倉
                  {latestHoldings.length > 0 && (
                    <Chip label={latestHoldings.length} size="small" sx={{ ml: 1 }} />
                  )}
                </Typography>
                {latestHoldings.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">無持倉紀錄</Typography>
                ) : (
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>股票代碼</TableCell>
                        <TableCell align="right">張數</TableCell>
                        <TableCell align="right">成本</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {latestHoldings.map((h) => (
                        <TableRow key={h.symbol} hover>
                          <TableCell>{h.symbol}</TableCell>
                          <TableCell align="right">{h.qty.toLocaleString()}</TableCell>
                          <TableCell align="right">
                            {h.cost != null ? `NT$ ${Number(h.cost).toLocaleString()}` : '—'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}

                {/* Today's trade records */}
                <Divider sx={{ my: 2 }} />
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <Typography variant="subtitle2" fontWeight="bold">今日買入紀錄</Typography>
                  <Chip label={todayBuys.length} size="small" color="primary" variant="outlined" />
                </Box>
                {todayBuys.length === 0 ? (
                  <Typography variant="body2" color="text.secondary" mb={2}>今日無買入紀錄</Typography>
                ) : (
                  <Table size="small" sx={{ mb: 2 }}>
                    <TableHead>
                      <TableRow>
                        <TableCell>股票</TableCell>
                        <TableCell>委託號</TableCell>
                        <TableCell align="right">張數</TableCell>
                        <TableCell align="right">成交價</TableCell>
                        <TableCell>狀態</TableCell>
                        <TableCell align="right">手續費</TableCell>
                        <TableCell>時間</TableCell>
                        <TableCell sx={{ color: 'error.main' }}>錯誤</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {todayBuys.map((r) => (
                        <TableRow key={r._id} hover>
                          <TableCell>{r.symbol}</TableCell>
                          <TableCell sx={{ fontFamily: 'monospace', fontSize: 11 }}>{r.order_id ?? '—'}</TableCell>
                          <TableCell align="right">{r.quantity ?? '—'}</TableCell>
                          <TableCell align="right">{r.price != null ? r.price.toLocaleString() : '—'}</TableCell>
                          <TableCell>
                            <Chip
                              label={r.status}
                              size="small"
                              color={r.status === 'FILLED' ? 'success' : r.status === 'FAILED' || r.status === 'TIMEOUT' ? 'error' : 'default'}
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell align="right">{r.fee > 0 ? r.fee.toLocaleString() : '—'}</TableCell>
                          <TableCell sx={{ fontSize: 11 }}>{r.create_at.slice(11, 19)}</TableCell>
                          <TableCell sx={{ fontSize: 11, color: 'error.main', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {r.error ?? ''}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}

                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <Typography variant="subtitle2" fontWeight="bold">今日賣出紀錄</Typography>
                  <Chip label={todaySells.length} size="small" color="warning" variant="outlined" />
                </Box>
                {todaySells.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">今日無賣出紀錄</Typography>
                ) : (
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>股票</TableCell>
                        <TableCell>委託號</TableCell>
                        <TableCell align="right">張數</TableCell>
                        <TableCell align="right">成交價</TableCell>
                        <TableCell>狀態</TableCell>
                        <TableCell align="right">損益</TableCell>
                        <TableCell align="right">報酬率</TableCell>
                        <TableCell>時間</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {todaySells.map((r) => (
                        <TableRow key={r._id} hover>
                          <TableCell>{r.symbol}</TableCell>
                          <TableCell sx={{ fontFamily: 'monospace', fontSize: 11 }}>{r.order_id ?? '—'}</TableCell>
                          <TableCell align="right">{r.quantity ?? '—'}</TableCell>
                          <TableCell align="right">{r.price != null ? r.price.toLocaleString() : '—'}</TableCell>
                          <TableCell>
                            <Chip
                              label={r.status}
                              size="small"
                              color={r.status === 'FILLED' ? 'success' : r.status === 'FAILED' || r.status === 'TIMEOUT' ? 'error' : 'default'}
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell align="right"
                            sx={{ color: r.pnl >= 0 ? 'success.main' : 'error.main' }}>
                            {r.pnl !== 0 ? `NT$ ${r.pnl.toLocaleString()}` : '—'}
                          </TableCell>
                          <TableCell align="right"
                            sx={{ color: r.return_rate >= 0 ? 'success.main' : 'error.main' }}>
                            {r.return_rate !== 0 ? `${(r.return_rate * 100).toFixed(2)}%` : '—'}
                          </TableCell>
                          <TableCell sx={{ fontSize: 11 }}>{r.create_at.slice(11, 19)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}
    </Stack>
  )
}
