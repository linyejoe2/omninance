import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import RefreshIcon from '@mui/icons-material/Refresh'
import StopIcon from '@mui/icons-material/Stop'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import Grid from '@mui/material/Grid'
import IconButton from '@mui/material/IconButton'
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
import {
  CreateStrategyParams,
  DailyLogRow,
  DailyLogStatus,
  OrderRecordRow,
  PositionRow,
  StrategyRow,
  traderApi,
} from '../../services/traderApi'

const DEFAULT_PARAMS: CreateStrategyParams = {
  name: 'Omninance Alpha',
  initial_capital: 100000,
  position_slots: 10,
  volume_multiplier: 2,
  concentration_slope: 0.1,
  atr_multiplier: 4,
}

const DAILY_LOG_STATUS: Record<DailyLogStatus, { label: string; color: 'info' | 'warning' | 'secondary' | 'success' }> = {
  'signal-generated': { label: '訊號已產生', color: 'info' },
  executing: { label: '執行中', color: 'warning' },
  finalizing: { label: '結算中', color: 'secondary' },
  ended: { label: '已結算', color: 'success' },
}

const ORDER_STATUS: Record<OrderRecordRow['status'], { label: string; color: 'default' | 'success' | 'error' | 'warning' }> = {
  PENDING: { label: '掛單中', color: 'default' },
  PARTIAL: { label: '部分成交', color: 'warning' },
  FILLED: { label: '已成交', color: 'success' },
  CANCELLED: { label: '已取消', color: 'default' },
  FAILED: { label: '失敗', color: 'error' },
  TIMEOUT: { label: '逾時', color: 'error' },
}

interface StrategyWithStats extends StrategyRow {
  total_equity: number | null
  daily_pnl: number | null
  available_balance: number | null
  position_count: number
}

function DailyLogStatusChip({ status }: { status: DailyLogStatus }) {
  const meta = DAILY_LOG_STATUS[status] ?? { label: status, color: 'default' as const }
  return <Chip label={meta.label} size="small" color={meta.color} variant="outlined" />
}

function OrderStatusChip({ status }: { status: OrderRecordRow['status'] }) {
  const meta = ORDER_STATUS[status] ?? { label: status, color: 'default' as const }
  return <Chip label={meta.label} size="small" color={meta.color} variant="outlined" />
}

function money(value: number | null | undefined): string {
  return value != null ? `NT$ ${value.toLocaleString()}` : '—'
}

function pnlColor(value: number | null | undefined) {
  if (value == null) return undefined
  return value >= 0 ? 'success.main' : 'error.main'
}

export function ExecutePanel() {
  const [params, setParams] = useState<CreateStrategyParams>(DEFAULT_PARAMS)
  const [strategies, setStrategies] = useState<StrategyWithStats[]>([])
  const [strategiesLoading, setStrategiesLoading] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [stopLoading, setStopLoading] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detailLogs, setDetailLogs] = useState<DailyLogRow[]>([])
  const [positions, setPositions] = useState<PositionRow[]>([])
  const [orders, setOrders] = useState<OrderRecordRow[]>([])
  const [detailLoading, setDetailLoading] = useState(false)

  const setNumber = (key: keyof CreateStrategyParams) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setParams((p) => ({ ...p, [key]: Number(e.target.value) }))

  const fetchStrategies = useCallback(async () => {
    setStrategiesLoading(true)
    try {
      const raw = await traderApi.listStrategies()
      const withStats = await Promise.all(
        raw.map(async (s): Promise<StrategyWithStats> => {
          try {
            const [logs, positionRows] = await Promise.all([
              traderApi.getDailyLogs(s.id),
              traderApi.getPositions(s.id),
            ])
            const latest = logs[0] ?? null
            return {
              ...s,
              total_equity: latest?.total_equity ?? null,
              daily_pnl: latest?.daily_pnl ?? null,
              available_balance: latest?.available_balance ?? null,
              position_count: positionRows.length,
            }
          } catch {
            return { ...s, total_equity: null, daily_pnl: null, available_balance: null, position_count: 0 }
          }
        })
      )
      setStrategies(withStats)
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    } finally {
      setStrategiesLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStrategies()
  }, [fetchStrategies])

  const loadDetail = useCallback(async (id: string) => {
    setDetailLoading(true)
    try {
      const [logs, positionRows, orderRows] = await Promise.all([
        traderApi.getDailyLogs(id),
        traderApi.getPositions(id),
        traderApi.listOrderRecords(id, 200),
      ])
      setDetailLogs(logs)
      setPositions(positionRows)
      setOrders(orderRows)
    } catch {
      setDetailLogs([])
      setPositions([])
      setOrders([])
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const handleSelectStrategy = useCallback(
    async (id: string) => {
      if (selectedId === id) {
        setSelectedId(null)
        return
      }
      setSelectedId(id)
      await loadDetail(id)
    },
    [selectedId, loadDetail]
  )

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
      if (selectedId === id) setSelectedId(null)
      await fetchStrategies()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    } finally {
      setStopLoading(null)
    }
  }

  const activeStrategies = strategies.filter((s) => s.status === 'active')
  const stoppedStrategies = strategies.filter((s) => s.status === 'stopped')
  const selectedStrategy = strategies.find((s) => s.id === selectedId) ?? null

  // Equity curve from settled logs, oldest first
  const chartData = [...detailLogs]
    .filter((l) => l.status === 'ended')
    .reverse()
    .map((l) => ({
      date: l.record_date,
      total_equity: l.total_equity,
      available_balance: l.available_balance,
    }))

  const todayPrefix = new Date().toLocaleDateString('sv-SE')
  const todayOrders = orders.filter((o) => o.create_at.startsWith(todayPrefix))

  return (
    <Stack spacing={3}>
      {/* 建立新策略 */}
      <Card variant="outlined">
        <CardContent>
          <Typography variant="subtitle2" fontWeight="bold" mb={2}>建立新策略</Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={4}>
              <TextField label="策略名稱" size="small" fullWidth
                value={params.name}
                onChange={(e) => setParams((p) => ({ ...p, name: e.target.value }))}
                disabled={createLoading} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="初始資金 (NT$)" type="number" size="small" fullWidth
                value={params.initial_capital} onChange={setNumber('initial_capital')} disabled={createLoading} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="持倉分數" type="number" size="small" fullWidth
                value={params.position_slots} onChange={setNumber('position_slots')} disabled={createLoading}
                inputProps={{ min: 1 }} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="成交量倍數" type="number" size="small" fullWidth
                value={params.volume_multiplier} onChange={setNumber('volume_multiplier')} disabled={createLoading}
                inputProps={{ step: 0.1 }} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="大戶籌碼斜率" type="number" size="small" fullWidth
                value={params.concentration_slope} onChange={setNumber('concentration_slope')} disabled={createLoading}
                inputProps={{ step: 0.001 }} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="止損 ATR 乘數" type="number" size="small" fullWidth
                value={params.atr_multiplier} onChange={setNumber('atr_multiplier')} disabled={createLoading}
                inputProps={{ step: 0.5 }} />
            </Grid>
          </Grid>

          <Box mt={2} display="flex" alignItems="center" gap={2}>
            <Button
              variant="contained"
              color="success"
              startIcon={createLoading ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
              onClick={handleCreate}
              disabled={createLoading || !params.name.trim()}
            >
              {createLoading ? '建立中…' : '建立策略'}
            </Button>
            <Typography variant="caption" color="text.secondary">
              建立後於背景產生明日訊號，次一交易日開盤執行
            </Typography>
            {actionError && (
              <Typography variant="body2" color="error">{actionError}</Typography>
            )}
          </Box>
        </CardContent>
      </Card>

      {/* 策略清單 */}
      <Card variant="outlined">
        <CardContent>
          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <Typography variant="subtitle2" fontWeight="bold">執行中策略</Typography>
            <Chip label={activeStrategies.length} size="small" color="success" variant="outlined" />
            <Typography variant="caption" color="text.secondary" sx={{ flexGrow: 1 }}>
              點選列查看詳情
            </Typography>
            <IconButton size="small" onClick={fetchStrategies} disabled={strategiesLoading}>
              {strategiesLoading ? <CircularProgress size={16} /> : <RefreshIcon fontSize="small" />}
            </IconButton>
          </Box>

          {activeStrategies.length === 0 ? (
            <Typography variant="body2" color="text.secondary">無執行中的策略</Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>名稱</TableCell>
                  <TableCell>ID</TableCell>
                  <TableCell align="right">初始資金</TableCell>
                  <TableCell align="right">總資產</TableCell>
                  <TableCell align="right">當日盈虧</TableCell>
                  <TableCell align="right">可用餘額</TableCell>
                  <TableCell align="right">持倉數</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {activeStrategies.map((s) => (
                  <TableRow
                    key={s.id}
                    hover
                    selected={selectedId === s.id}
                    onClick={() => handleSelectStrategy(s.id)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell>{s.name}</TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: 11 }}>{s.id.slice(0, 8)}</TableCell>
                    <TableCell align="right">{s.initial_capital.toLocaleString()}</TableCell>
                    <TableCell align="right">{s.total_equity != null ? s.total_equity.toLocaleString() : '—'}</TableCell>
                    <TableCell align="right" sx={{ color: pnlColor(s.daily_pnl) }}>
                      {s.daily_pnl != null ? s.daily_pnl.toLocaleString() : '—'}
                    </TableCell>
                    <TableCell align="right">{s.available_balance != null ? s.available_balance.toLocaleString() : '—'}</TableCell>
                    <TableCell align="right">{s.position_count}</TableCell>
                    <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                      <Button
                        size="small"
                        color="error"
                        variant="outlined"
                        startIcon={stopLoading === s.id
                          ? <CircularProgress size={12} color="inherit" />
                          : <StopIcon fontSize="small" />}
                        onClick={() => handleStop(s.id)}
                        disabled={stopLoading === s.id}
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

      {/* 策略詳情 */}
      {selectedStrategy && (
        <Card variant="outlined">
          <CardContent>
            <Box display="flex" alignItems="center" gap={1} mb={2}>
              <Typography variant="subtitle2" fontWeight="bold">
                策略詳情 — {selectedStrategy.name}
              </Typography>
              {detailLoading && <CircularProgress size={14} />}
              <Chip
                label={selectedStrategy.status === 'active' ? '執行中' : '已停止'}
                size="small"
                color={selectedStrategy.status === 'active' ? 'success' : 'default'}
                variant="outlined"
              />
            </Box>

            {/* 參數摘要 */}
            <Grid container spacing={1} mb={2}>
              {[
                { label: '初始資金', value: money(selectedStrategy.initial_capital) },
                { label: '持倉分數', value: selectedStrategy.position_slots },
                { label: '成交量倍數', value: selectedStrategy.volume_multiplier },
                { label: '大戶籌碼斜率', value: selectedStrategy.concentration_slope },
                { label: '止損 ATR 乘數', value: selectedStrategy.atr_multiplier },
                { label: '建立時間', value: selectedStrategy.create_at.slice(0, 10) },
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

            {/* 資產走勢 */}
            {chartData.length > 0 && (
              <>
                <Typography variant="subtitle2" fontWeight="bold" mb={1}>資產走勢</Typography>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} minTickGap={30} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}K`} width={48} />
                    <Tooltip
                      formatter={(value: number, name: string) => [
                        money(value),
                        name === 'total_equity' ? '總資產' : '可用餘額',
                      ]}
                      contentStyle={{ fontSize: 12 }}
                    />
                    <Legend
                      formatter={(v) => (v === 'total_equity' ? '總資產' : '可用餘額')}
                      wrapperStyle={{ fontSize: 12 }}
                    />
                    <Line type="monotone" dataKey="total_equity" stroke="#4fc3f7" dot={false} strokeWidth={2} connectNulls />
                    <Line type="monotone" dataKey="available_balance" stroke="#81c784" dot={false} strokeWidth={1.5} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
                <Divider sx={{ my: 2 }} />
              </>
            )}

            {/* 當前持倉（position 表） */}
            <Box display="flex" alignItems="center" gap={1} mb={1}>
              <Typography variant="subtitle2" fontWeight="bold">當前持倉</Typography>
              <Chip label={positions.length} size="small" variant="outlined" />
            </Box>
            {positions.length === 0 ? (
              <Typography variant="body2" color="text.secondary" mb={2}>無持倉</Typography>
            ) : (
              <Table size="small" sx={{ mb: 2 }}>
                <TableHead>
                  <TableRow>
                    <TableCell>股票代碼</TableCell>
                    <TableCell align="right">股數</TableCell>
                    <TableCell align="right">平均成本</TableCell>
                    <TableCell align="right">現價</TableCell>
                    <TableCell align="right">最高價</TableCell>
                    <TableCell align="right">移動停損價</TableCell>
                    <TableCell align="right">未實現損益</TableCell>
                    <TableCell align="right">報酬率</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {positions.map((p) => {
                    const unrealized = (p.current_price - p.average_cost) * p.quantity
                    const returnRate = p.average_cost > 0
                      ? ((p.current_price - p.average_cost) / p.average_cost) * 100
                      : 0
                    return (
                      <TableRow key={p.id} hover>
                        <TableCell>{p.symbol}</TableCell>
                        <TableCell align="right">{p.quantity.toLocaleString()}</TableCell>
                        <TableCell align="right">{p.average_cost.toLocaleString()}</TableCell>
                        <TableCell align="right">{p.current_price.toLocaleString()}</TableCell>
                        <TableCell align="right">{p.highest_price.toLocaleString()}</TableCell>
                        <TableCell align="right">{p.trailing_stop_price.toLocaleString()}</TableCell>
                        <TableCell align="right" sx={{ color: pnlColor(unrealized) }}>
                          {money(Math.round(unrealized))}
                        </TableCell>
                        <TableCell align="right" sx={{ color: pnlColor(returnRate) }}>
                          {returnRate.toFixed(2)}%
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}

            {/* 今日委託 */}
            <Divider sx={{ my: 2 }} />
            <Box display="flex" alignItems="center" gap={1} mb={1}>
              <Typography variant="subtitle2" fontWeight="bold">今日委託</Typography>
              <Chip label={todayOrders.length} size="small" color="primary" variant="outlined" />
            </Box>
            {todayOrders.length === 0 ? (
              <Typography variant="body2" color="text.secondary" mb={2}>今日無委託紀錄</Typography>
            ) : (
              <Table size="small" sx={{ mb: 2 }}>
                <TableHead>
                  <TableRow>
                    <TableCell>股票</TableCell>
                    <TableCell>動作</TableCell>
                    <TableCell>委託號</TableCell>
                    <TableCell align="right">成交/委託股數</TableCell>
                    <TableCell align="right">成交均價</TableCell>
                    <TableCell>狀態</TableCell>
                    <TableCell align="right">手續費</TableCell>
                    <TableCell align="right">交易稅</TableCell>
                    <TableCell align="right">實現損益</TableCell>
                    <TableCell>時間</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {todayOrders.map((o) => (
                    <TableRow key={o.id} hover>
                      <TableCell>{o.symbol}</TableCell>
                      <TableCell>
                        <Chip
                          label={o.action === 'BUY' ? '買入' : '賣出'}
                          size="small"
                          color={o.action === 'BUY' ? 'primary' : 'warning'}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: 11 }}>{o.broker_order_id ?? '—'}</TableCell>
                      <TableCell align="right">
                        {o.filled_quantity.toLocaleString()} / {o.req_quantity.toLocaleString()}
                      </TableCell>
                      <TableCell align="right">{o.filled_price != null ? o.filled_price.toLocaleString() : '—'}</TableCell>
                      <TableCell><OrderStatusChip status={o.status} /></TableCell>
                      <TableCell align="right">{o.fee > 0 ? o.fee.toLocaleString() : '—'}</TableCell>
                      <TableCell align="right">{o.tax > 0 ? o.tax.toLocaleString() : '—'}</TableCell>
                      <TableCell align="right" sx={{ color: pnlColor(o.realized_pnl) }}>
                        {o.action === 'SELL' ? money(o.realized_pnl) : '—'}
                      </TableCell>
                      <TableCell sx={{ fontSize: 11 }}>{o.create_at.slice(11, 19)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}

            {/* 每日日誌 */}
            <Divider sx={{ my: 2 }} />
            <Box display="flex" alignItems="center" gap={1} mb={1}>
              <Typography variant="subtitle2" fontWeight="bold">每日日誌</Typography>
              <Chip label={detailLogs.length} size="small" variant="outlined" />
            </Box>
            {detailLogs.length === 0 ? (
              <Typography variant="body2" color="text.secondary">尚無每日日誌</Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>日期</TableCell>
                    <TableCell>狀態</TableCell>
                    <TableCell align="right">總資產</TableCell>
                    <TableCell align="right">可用餘額</TableCell>
                    <TableCell align="right">當日盈虧</TableCell>
                    <TableCell align="right">買入訊號</TableCell>
                    <TableCell sx={{ color: 'error.main' }}>錯誤</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {detailLogs.map((l) => (
                    <TableRow key={l.id} hover>
                      <TableCell>{l.record_date}</TableCell>
                      <TableCell><DailyLogStatusChip status={l.status} /></TableCell>
                      <TableCell align="right">{l.total_equity.toLocaleString()}</TableCell>
                      <TableCell align="right">{l.available_balance.toLocaleString()}</TableCell>
                      <TableCell align="right" sx={{ color: pnlColor(l.daily_pnl) }}>
                        {l.status === 'ended' ? l.daily_pnl.toLocaleString() : '—'}
                      </TableCell>
                      <TableCell align="right">{l.buy_signals_snapshot?.length ?? 0}</TableCell>
                      <TableCell sx={{ fontSize: 11, color: 'error.main', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {(l.errors ?? []).join('; ')}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </Stack>
  )
}
