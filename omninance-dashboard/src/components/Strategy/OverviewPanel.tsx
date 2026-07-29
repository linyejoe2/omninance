import CloseIcon from '@mui/icons-material/Close'
import RefreshIcon from '@mui/icons-material/Refresh'
import TrendingDownIcon from '@mui/icons-material/TrendingDown'
import TrendingFlatIcon from '@mui/icons-material/TrendingFlat'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardActionArea from '@mui/material/CardActionArea'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Dialog from '@mui/material/Dialog'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Divider from '@mui/material/Divider'
import Grid from '@mui/material/Grid'
import IconButton from '@mui/material/IconButton'
import Paper from '@mui/material/Paper'
import Skeleton from '@mui/material/Skeleton'
import Stack from '@mui/material/Stack'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Typography from '@mui/material/Typography'
import { useTheme } from '@mui/material/styles'
import dayjs from 'dayjs'
import { useCallback, useEffect, useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useTraderData } from '../../hooks/useTraderData'
import {
  DailyLogRow,
  OrderRecordRow,
  PositionRow,
  StrategyRow,
  traderApi,
} from '../../services/traderApi'

// ---------------------------------------------------------------------------
// 運行中策略卡片
// ---------------------------------------------------------------------------

interface StrategyCardData extends StrategyRow {
  logs: DailyLogRow[]
  positions: PositionRow[]
}

interface EquityPoint {
  date: string
  total_equity: number
  available_balance: number
}

function equitySeries(logs: DailyLogRow[]): EquityPoint[] {
  return [...logs]
    .filter((l) => l.status === 'ended')
    .reverse()
    .map((l) => ({
      date: l.record_date,
      total_equity: l.total_equity,
      available_balance: l.available_balance,
    }))
}

function latestOf(data: StrategyCardData): DailyLogRow | null {
  return data.logs[0] ?? null
}

function money(value: number | null | undefined): string {
  return value != null ? `NT$ ${Math.round(value).toLocaleString()}` : '—'
}

function EquitySparkline({ series, positive }: { series: EquityPoint[]; positive: boolean }) {
  const theme = useTheme()
  const color = positive ? theme.palette.success.main : theme.palette.error.main
  const id = `spark-${positive ? 'up' : 'down'}`

  if (series.length < 2) {
    return (
      <Box sx={{ height: 56, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Typography variant="caption" color="text.secondary">結算滿兩日後顯示走勢</Typography>
      </Box>
    )
  }
  return (
    <ResponsiveContainer width="100%" height={56}>
      <AreaChart data={series} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <YAxis hide domain={['dataMin', 'dataMax']} />
        <Area
          type="monotone"
          dataKey="total_equity"
          stroke={color}
          strokeWidth={2}
          fill={`url(#${id})`}
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

function StrategyCard({ data, onClick }: { data: StrategyCardData; onClick: () => void }) {
  const latest = latestOf(data)
  const equity = latest?.total_equity ?? data.initial_capital
  const pnl = latest?.status === 'ended' ? latest.daily_pnl : null
  const totalReturn = data.initial_capital > 0
    ? ((equity - data.initial_capital) / data.initial_capital) * 100
    : 0
  const positive = totalReturn >= 0
  const series = equitySeries(data.logs)

  const PnlIcon = pnl == null ? TrendingFlatIcon : pnl >= 0 ? TrendingUpIcon : TrendingDownIcon
  const pnlColor = pnl == null ? 'default' : pnl >= 0 ? 'success' : 'error'

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardActionArea onClick={onClick} sx={{ height: '100%', p: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography variant="subtitle2" fontWeight="bold" noWrap sx={{ flexGrow: 1 }}>
            {data.name}
          </Typography>
          <Chip label="執行中" size="small" color="success" variant="outlined" />
        </Box>

        <Typography variant="h5" fontWeight="bold">{money(equity)}</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5, mb: 1 }}>
          <Chip
            icon={<PnlIcon fontSize="small" />}
            label={pnl != null ? `今日 ${pnl >= 0 ? '+' : ''}${Math.round(pnl).toLocaleString()}` : '今日 —'}
            size="small"
            color={pnlColor}
            variant="outlined"
          />
          <Typography variant="caption" color={positive ? 'success.main' : 'error.main'} fontWeight="medium">
            累計 {positive ? '+' : ''}{totalReturn.toFixed(2)}%
          </Typography>
        </Box>

        <EquitySparkline series={series} positive={positive} />

        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
          <Typography variant="caption" color="text.secondary">
            持倉 {data.positions.length} 檔
          </Typography>
          <Typography variant="caption" color="text.secondary">
            可用 {money(latest?.available_balance ?? data.initial_capital)}
          </Typography>
        </Box>
      </CardActionArea>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// 策略詳情 Modal
// ---------------------------------------------------------------------------

const ORDER_STATUS_LABEL: Record<OrderRecordRow['status'], string> = {
  PENDING: '掛單中',
  PARTIAL: '部分成交',
  FILLED: '已成交',
  CANCELLED: '已取消',
  FAILED: '失敗',
  TIMEOUT: '逾時',
}

function StrategyDetailDialog({
  data,
  onClose,
}: {
  data: StrategyCardData | null
  onClose: () => void
}) {
  const theme = useTheme()
  const [orders, setOrders] = useState<OrderRecordRow[]>([])
  const [ordersLoading, setOrdersLoading] = useState(false)

  useEffect(() => {
    if (!data) return
    setOrdersLoading(true)
    traderApi
      .listOrderRecords(data.id, 10)
      .then(setOrders)
      .catch(() => setOrders([]))
      .finally(() => setOrdersLoading(false))
  }, [data])

  if (!data) return null

  const series = equitySeries(data.logs)
  const latest = latestOf(data)
  const equity = latest?.total_equity ?? data.initial_capital
  const positive = equity >= data.initial_capital
  const color = positive ? theme.palette.success.main : theme.palette.error.main

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography variant="h6" fontWeight="bold" component="span" sx={{ flexGrow: 1 }}>
          {data.name}
        </Typography>
        <Chip label="執行中" size="small" color="success" variant="outlined" />
        <IconButton size="small" onClick={onClose}><CloseIcon fontSize="small" /></IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {/* 參數摘要 */}
        <Grid container spacing={1} mb={2}>
          {[
            { label: '初始資金', value: money(data.initial_capital) },
            { label: '持倉分數', value: `${data.position_slots} 份` },
            { label: '成交量倍數', value: data.volume_multiplier },
            { label: '大戶籌碼斜率', value: data.concentration_slope },
            { label: '止損 ATR 乘數', value: `${data.atr_multiplier}x` },
            { label: '建立時間', value: dayjs(data.create_at).format('YYYY-MM-DD') },
          ].map(({ label, value }) => (
            <Grid item xs={6} sm={4} key={label}>
              <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
              <Typography variant="body2" fontWeight="medium">{value}</Typography>
            </Grid>
          ))}
        </Grid>

        <Divider sx={{ mb: 2 }} />

        {/* 資產走勢 */}
        <Typography variant="subtitle2" fontWeight="bold" mb={1}>資產走勢</Typography>
        {series.length < 2 ? (
          <Typography variant="body2" color="text.secondary" mb={2}>結算滿兩日後顯示走勢</Typography>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={series} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <defs>
                <linearGradient id="detail-equity" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} minTickGap={30} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}K`} width={48} domain={['auto', 'auto']} />
              <Tooltip
                formatter={(value: number, name: string) => [
                  money(value),
                  name === 'total_equity' ? '總資產' : '可用餘額',
                ]}
                contentStyle={{ fontSize: 12 }}
              />
              <Area type="monotone" dataKey="total_equity" stroke={color} strokeWidth={2}
                fill="url(#detail-equity)" dot={false} />
              <Area type="monotone" dataKey="available_balance" stroke={theme.palette.info.main}
                strokeWidth={1.5} fill="none" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}

        {/* 當前持倉 */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 2, mb: 1 }}>
          <Typography variant="subtitle2" fontWeight="bold">當前持倉</Typography>
          <Chip label={data.positions.length} size="small" variant="outlined" />
        </Box>
        {data.positions.length === 0 ? (
          <Typography variant="body2" color="text.secondary" mb={2}>無持倉</Typography>
        ) : (
          <TableContainer sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>股票代碼</TableCell>
                  <TableCell align="right">股數</TableCell>
                  <TableCell align="right">平均成本</TableCell>
                  <TableCell align="right">現價</TableCell>
                  <TableCell align="right">移動停損價</TableCell>
                  <TableCell align="right">未實現損益</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.positions.map((p) => {
                  const unrealized = (p.current_price - p.average_cost) * p.quantity
                  return (
                    <TableRow key={p.id} hover>
                      <TableCell>{p.symbol}</TableCell>
                      <TableCell align="right">{p.quantity.toLocaleString()}</TableCell>
                      <TableCell align="right">{p.average_cost.toLocaleString()}</TableCell>
                      <TableCell align="right">{p.current_price.toLocaleString()}</TableCell>
                      <TableCell align="right">{p.trailing_stop_price.toLocaleString()}</TableCell>
                      <TableCell align="right" sx={{ color: unrealized >= 0 ? 'success.main' : 'error.main' }}>
                        {money(unrealized)}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {/* 近期委託 */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography variant="subtitle2" fontWeight="bold">近期委託</Typography>
          {ordersLoading && <CircularProgress size={14} />}
        </Box>
        {!ordersLoading && orders.length === 0 ? (
          <Typography variant="body2" color="text.secondary">尚無委託紀錄</Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>時間</TableCell>
                  <TableCell>股票</TableCell>
                  <TableCell>動作</TableCell>
                  <TableCell align="right">成交/委託</TableCell>
                  <TableCell align="right">成交均價</TableCell>
                  <TableCell>狀態</TableCell>
                  <TableCell align="right">實現損益</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {orders.map((o) => (
                  <TableRow key={o.id} hover>
                    <TableCell sx={{ fontSize: 11 }}>{dayjs(o.create_at).format('MM-DD HH:mm')}</TableCell>
                    <TableCell>{o.symbol}</TableCell>
                    <TableCell>
                      <Chip label={o.action === 'BUY' ? '買入' : '賣出'} size="small"
                        color={o.action === 'BUY' ? 'primary' : 'warning'} variant="outlined" />
                    </TableCell>
                    <TableCell align="right">
                      {o.filled_quantity.toLocaleString()} / {o.req_quantity.toLocaleString()}
                    </TableCell>
                    <TableCell align="right">{o.filled_price != null ? o.filled_price.toLocaleString() : '—'}</TableCell>
                    <TableCell>
                      <Chip
                        label={ORDER_STATUS_LABEL[o.status] ?? o.status}
                        size="small"
                        color={o.status === 'FILLED' ? 'success' : o.status === 'FAILED' || o.status === 'TIMEOUT' ? 'error' : 'default'}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell align="right" sx={{ color: o.realized_pnl >= 0 ? 'success.main' : 'error.main' }}>
                      {o.action === 'SELL' ? money(o.realized_pnl) : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// 最新訊號（chip-tracker latest_signals.json）
// ---------------------------------------------------------------------------

interface Snapshot { p: number | null; atr: number | null }

interface SignalData {
  metadata?: {
    strategy: string
    run_date: string
    action_date: string
    params: { partition: number; atr_mult: number }
  }
  actions?: { buy: string[]; sell_hint: string[] }
  snapshot?: Record<string, Snapshot>
}

function SignalTable({
  title,
  symbols,
  snapshot,
  chipColor,
}: {
  title: string
  symbols: string[]
  snapshot: Record<string, Snapshot>
  chipColor: 'success' | 'warning'
}) {
  return (
    <Paper variant="outlined" sx={{ height: '100%' }}>
      <Box sx={{ px: 2, pt: 1.5, pb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography variant="subtitle2" fontWeight="bold">{title}</Typography>
        <Chip label={symbols.length} size="small" color={chipColor} variant="outlined" />
      </Box>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 'bold' }}>股票代碼</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }} align="right">即時價格</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }} align="right">ATR</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {symbols.length === 0 && (
              <TableRow>
                <TableCell colSpan={3} align="center">
                  <Typography variant="body2" color="text.secondary">無訊號</Typography>
                </TableCell>
              </TableRow>
            )}
            {symbols.map((sym) => {
              const snap = snapshot[sym]
              return (
                <TableRow key={sym} hover>
                  <TableCell>{sym}</TableCell>
                  <TableCell align="right">{snap?.p != null ? snap.p.toFixed(2) : '—'}</TableCell>
                  <TableCell align="right">{snap?.atr != null ? snap.atr.toFixed(2) : '—'}</TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  )
}

// ---------------------------------------------------------------------------
// Overview panel
// ---------------------------------------------------------------------------

export function OverviewPanel() {
  const [cards, setCards] = useState<StrategyCardData[] | null>(null)
  const [cardsLoading, setCardsLoading] = useState(false)
  const [cardsError, setCardsError] = useState<string | null>(null)
  const [selected, setSelected] = useState<StrategyCardData | null>(null)

  const { data: signalRaw, loading: signalLoading, error: signalError, lastUpdated, refresh: refreshSignals } =
    useTraderData(traderApi.signals as unknown as () => Promise<SignalData>)

  const fetchCards = useCallback(async () => {
    setCardsLoading(true)
    setCardsError(null)
    try {
      const strategies = await traderApi.listStrategies('active')
      const withData = await Promise.all(
        strategies.map(async (s): Promise<StrategyCardData> => {
          try {
            const [logs, positions] = await Promise.all([
              traderApi.getDailyLogs(s.id),
              traderApi.getPositions(s.id),
            ])
            return { ...s, logs, positions }
          } catch {
            return { ...s, logs: [], positions: [] }
          }
        })
      )
      setCards(withData)
    } catch (e) {
      setCardsError(e instanceof Error ? e.message : String(e))
    } finally {
      setCardsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCards()
  }, [fetchCards])

  const handleRefresh = () => {
    fetchCards()
    refreshSignals()
  }

  const meta = signalRaw?.metadata
  const buy = signalRaw?.actions?.buy ?? []
  const sell = signalRaw?.actions?.sell_hint ?? []
  const snapshot = signalRaw?.snapshot ?? {}

  return (
    <Stack spacing={3}>
      {/* 運行中策略卡片 */}
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
          <Typography variant="subtitle1" fontWeight="bold" sx={{ flexGrow: 1 }}>
            運行中策略
            {cards != null && (
              <Chip label={cards.length} size="small" color="success" variant="outlined" sx={{ ml: 1 }} />
            )}
          </Typography>
          <IconButton size="small" onClick={handleRefresh} disabled={cardsLoading}>
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Box>

        {cardsError && (
          <Typography color="error" variant="body2" mb={1}>{cardsError}</Typography>
        )}

        <Grid container spacing={2}>
          {cardsLoading && cards == null &&
            [0, 1, 2].map((i) => (
              <Grid item xs={12} sm={6} md={4} key={i}>
                <Skeleton variant="rounded" height={190} />
              </Grid>
            ))}

          {cards != null && cards.length === 0 && (
            <Grid item xs={12}>
              <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary">
                  尚無運行中的策略 — 到「Execute」分頁建立第一個策略
                </Typography>
              </Paper>
            </Grid>
          )}

          {(cards ?? []).map((c) => (
            <Grid item xs={12} sm={6} md={4} key={c.id}>
              <StrategyCard data={c} onClick={() => setSelected(c)} />
            </Grid>
          ))}
        </Grid>
      </Box>

      {/* 最新訊號 */}
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
          <Typography variant="subtitle1" fontWeight="bold" sx={{ flexGrow: 1 }}>最新訊號</Typography>
          {signalLoading && <CircularProgress size={16} />}
          {lastUpdated && (
            <Typography variant="caption" color="text.secondary">
              更新於 {dayjs(lastUpdated).format('HH:mm:ss')}
            </Typography>
          )}
        </Box>

        {signalError && <Typography color="error" variant="body2" mb={1}>{signalError}</Typography>}

        {meta && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
            <Chip size="small" variant="outlined" label={`策略：${meta.strategy}`} />
            <Chip size="small" variant="outlined"
              label={`訊號日期：${dayjs(meta.run_date, 'YYYYMMDD').format('YYYY-MM-DD')}`} />
            <Chip size="small" variant="outlined" color="primary" label={`執行日期：${meta.action_date}`} />
            <Chip size="small" variant="outlined" label={`資金分份：${meta.params.partition} 份`} />
            <Chip size="small" variant="outlined" label={`ATR 乘數：${meta.params.atr_mult}x`} />
          </Box>
        )}

        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <SignalTable title="買入訊號" symbols={buy} snapshot={snapshot} chipColor="success" />
          </Grid>
          <Grid item xs={12} md={6}>
            <SignalTable title="減碼提示" symbols={sell} snapshot={snapshot} chipColor="warning" />
          </Grid>
        </Grid>
      </Box>

      <StrategyDetailDialog data={selected} onClose={() => setSelected(null)} />
    </Stack>
  )
}
