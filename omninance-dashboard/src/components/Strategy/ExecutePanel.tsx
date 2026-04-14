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
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Typography from '@mui/material/Typography'
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { traderApi, StrategyParams } from '../../services/traderApi'

const DAY_OPTIONS = [7, 14, 30, 60, 90]

const LINE_COLORS = [
  '#4fc3f7', '#81c784', '#ffb74d', '#f06292', '#ce93d8',
  '#80cbc4', '#fff176', '#ff8a65', '#90caf9', '#a5d6a7',
]

type ChartRow = Record<string, string | number | null>

interface Strategy {
  _id: string
  initial_capital: number
  partition: number
  volume_multiplier: number
  concentration_slope: number
  atr_multiplier: number
  back_test_period: number
  status: string
  create_date: string
}

interface ExecutePanelProps {
  buy: string[]
  snapshot: Record<string, { p: number; atr: number }>
}

const DEFAULT_PARAMS: StrategyParams = {
  initial_capital: 100000,
  partition: 10,
  volume_multiplier: 2,
  concentration_slope: 0.02,
  atr_multiplier: 4,
  back_test_period: 4,
}

export function ExecutePanel({ buy }: ExecutePanelProps) {
  const [params, setParams] = useState<StrategyParams>(DEFAULT_PARAMS)
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [strategiesLoading, setStrategiesLoading] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [stopLoading, setStopLoading] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [days, setDays] = useState<number>(30)
  const [chartData, setChartData] = useState<ChartRow[]>([])
  const [chartLoading, setChartLoading] = useState(false)

  const set = (key: keyof StrategyParams) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setParams((p) => ({ ...p, [key]: Number(e.target.value) }))

  const fetchStrategies = useCallback(async () => {
    setStrategiesLoading(true)
    try {
      const data = await traderApi.listStrategies()
      setStrategies(data as unknown as Strategy[])
    } catch {
      // silently ignore — strategies section just stays empty
    } finally {
      setStrategiesLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStrategies()
  }, [fetchStrategies])

  // Price chart
  const buyRef = useRef(buy)
  buyRef.current = buy

  useEffect(() => {
    if (buy.length === 0) {
      setChartData([])
      return
    }
    let cancelled = false
    setChartLoading(true)
    traderApi
      .priceHistory(buy.join(','), days)
      .then((rows) => {
        if (cancelled) return
        const firstValues: Record<string, number> = {}
        const normalized = rows.map((row) => {
          const entry: ChartRow = { date: row['date'] as string }
          for (const sym of buy) {
            const raw = row[sym] as number | null
            if (raw !== null && raw !== undefined) {
              if (firstValues[sym] === undefined) firstValues[sym] = raw
              entry[sym] = parseFloat(((raw / firstValues[sym]) * 100).toFixed(2))
            } else {
              entry[sym] = null
            }
          }
          return entry
        })
        setChartData(normalized)
      })
      .catch(() => { if (!cancelled) setChartData([]) })
      .finally(() => { if (!cancelled) setChartLoading(false) })
    return () => { cancelled = true }
  }, [buy.join(','), days]) // eslint-disable-line react-hooks/exhaustive-deps

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
      await fetchStrategies()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    } finally {
      setStopLoading(null)
    }
  }

  const activeStrategies = strategies.filter((s) => s.status === 'active')
  const stoppedStrategies = strategies.filter((s) => s.status === 'stopped')

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

      {/* Active strategies */}
      <Card variant="outlined">
        <CardContent>
          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <Typography variant="subtitle2" fontWeight="bold">執行中策略</Typography>
            {strategiesLoading && <CircularProgress size={14} />}
            <Chip label={activeStrategies.length} size="small" color="success" variant="outlined" />
          </Box>
          {activeStrategies.length === 0 ? (
            <Typography variant="body2" color="text.secondary">無執行中的策略</Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell align="right">資金</TableCell>
                  <TableCell align="right">分份</TableCell>
                  <TableCell align="right">量倍</TableCell>
                  <TableCell align="right">斜率</TableCell>
                  <TableCell align="right">ATR</TableCell>
                  <TableCell align="right">年數</TableCell>
                  <TableCell align="right">建立時間</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {activeStrategies.map((s) => (
                  <TableRow key={s._id} hover>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: 11 }}>{s._id.slice(0, 8)}</TableCell>
                    <TableCell align="right">{s.initial_capital.toLocaleString()}</TableCell>
                    <TableCell align="right">{s.partition}</TableCell>
                    <TableCell align="right">{s.volume_multiplier}</TableCell>
                    <TableCell align="right">{s.concentration_slope}</TableCell>
                    <TableCell align="right">{s.atr_multiplier}</TableCell>
                    <TableCell align="right">{s.back_test_period}</TableCell>
                    <TableCell align="right" sx={{ fontSize: 11 }}>
                      {s.create_date.slice(0, 10)}
                    </TableCell>
                    <TableCell align="right">
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

      <Divider />

      {/* Days selector + price chart */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Typography variant="body2" color="text.secondary">訊號標的近期走勢</Typography>
        <ToggleButtonGroup
          value={days}
          exclusive
          onChange={(_, v: number | null) => { if (v !== null) setDays(v) }}
          size="small"
        >
          {DAY_OPTIONS.map((d) => (
            <ToggleButton key={d} value={d} sx={{ px: 1.5 }}>{d}日</ToggleButton>
          ))}
        </ToggleButtonGroup>
        {chartLoading && <CircularProgress size={16} />}
      </Box>

      {buy.length === 0 ? (
        <Typography variant="body2" color="text.secondary">無買入訊號，無法顯示走勢圖</Typography>
      ) : chartData.length > 0 ? (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${v.toFixed(0)}`}
              domain={['auto', 'auto']} width={40} />
            <Tooltip
              formatter={(value: number) => [`${value.toFixed(1)}`, '']}
              labelFormatter={(label: string) => label}
              contentStyle={{ fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} formatter={(v) => v.split('.')[0]} />
            {buy.map((sym, i) => (
              <Line key={sym} type="monotone" dataKey={sym} name={sym}
                stroke={LINE_COLORS[i % LINE_COLORS.length]} dot={false}
                strokeWidth={1.5} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      ) : (
        !chartLoading && (
          <Typography variant="body2" color="text.secondary">無法載入走勢資料</Typography>
        )
      )}
    </Stack>
  )
}
