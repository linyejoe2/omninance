import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import StopIcon from '@mui/icons-material/Stop'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import InputAdornment from '@mui/material/InputAdornment'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Typography from '@mui/material/Typography'
import { useEffect, useRef, useState } from 'react'
import {
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { traderApi } from '../../services/traderApi'

const DAY_OPTIONS = [7, 14, 30, 60, 90]

// Palette for chart lines — cycles if more symbols than colours
const LINE_COLORS = [
  '#4fc3f7', '#81c784', '#ffb74d', '#f06292', '#ce93d8',
  '#80cbc4', '#fff176', '#ff8a65', '#90caf9', '#a5d6a7',
]

type ChartRow = Record<string, string | number | null>
type Status = 'idle' | 'running'

interface ExecutePanelProps {
  buy: string[]
  snapshot: Record<string, { p: number; atr: number }>
}

export function ExecutePanel({ buy, snapshot }: ExecutePanelProps) {
  const [status, setStatus] = useState<Status>('idle')
  const [initialCapital, setInitialCapital] = useState<number>(100000)
  const [days, setDays] = useState<number>(30)
  const [chartData, setChartData] = useState<ChartRow[]>([])
  const [chartLoading, setChartLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  // Stable ref so the effect doesn't re-run when buy array reference changes
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
        // Normalize each symbol: index to 100 at first non-null value
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
      .catch(() => {
        if (!cancelled) setChartData([])
      })
      .finally(() => {
        if (!cancelled) setChartLoading(false)
      })
    return () => { cancelled = true }
  }, [buy.join(','), days]) // eslint-disable-line react-hooks/exhaustive-deps

  // Quantity per stock: floor( capital / count / (avgPrice * 1000) ) lots, minimum 1
  const lotsPerStock = (() => {
    if (buy.length === 0) return 1
    const totalAvgPrice =
      buy.reduce((sum, sym) => sum + (snapshot[sym]?.p ?? 0), 0) / buy.length
    if (totalAvgPrice === 0) return 1
    return Math.max(1, Math.floor(initialCapital / buy.length / (totalAvgPrice * 1000)))
  })()

  const handleStart = async () => {
    setActionError(null)
    setActionLoading(true)
    try {
      await traderApi.executeSignals({ quantity: lotsPerStock, price_flag: '4' })
      setStatus('running')
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    } finally {
      setActionLoading(false)
    }
  }

  const handleStop = async () => {
    setActionError(null)
    setActionLoading(true)
    try {
      await traderApi.stopSignals()
      setStatus('idle')
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <Stack spacing={2}>
      {/* Capital + lots estimate */}
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <TextField
          label="初始資金"
          type="number"
          size="small"
          value={initialCapital}
          onChange={(e) => setInitialCapital(Math.max(1, Number(e.target.value)))}
          InputProps={{
            startAdornment: <InputAdornment position="start">NT$</InputAdornment>,
          }}
          sx={{ width: 200 }}
          disabled={status === 'running'}
        />
        <Typography variant="body2" color="text.secondary">
          每檔 <strong>{lotsPerStock}</strong> 張 × {buy.length} 檔
        </Typography>
      </Box>

      {/* Start / Stop buttons */}
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <Button
          variant="contained"
          color="success"
          startIcon={actionLoading && status === 'idle' ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
          onClick={handleStart}
          disabled={actionLoading || status === 'running' || buy.length === 0}
        >
          開始策略
        </Button>
        <Button
          variant="outlined"
          color="error"
          startIcon={actionLoading && status === 'running' ? <CircularProgress size={16} color="inherit" /> : <StopIcon />}
          onClick={handleStop}
          disabled={actionLoading || status === 'idle'}
        >
          停止策略
        </Button>
        {status === 'running' && (
          <Typography variant="body2" color="success.main" fontWeight="medium">執行中</Typography>
        )}
        {actionError && (
          <Typography variant="body2" color="error">{actionError}</Typography>
        )}
      </Box>

      <Divider />

      {/* Days selector */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Typography variant="body2" color="text.secondary">近期走勢</Typography>
        <ToggleButtonGroup
          value={days}
          exclusive
          onChange={(_, v: number | null) => { if (v !== null) setDays(v) }}
          size="small"
        >
          {DAY_OPTIONS.map((d) => (
            <ToggleButton key={d} value={d} sx={{ px: 1.5 }}>
              {d}日
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
        {chartLoading && <CircularProgress size={16} />}
      </Box>

      {/* Normalized price chart */}
      {buy.length === 0 ? (
        <Typography variant="body2" color="text.secondary">無買入訊號，無法顯示走勢圖</Typography>
      ) : chartData.length > 0 ? (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickFormatter={(v: string) => v.slice(5)} // MM-DD
            />
            <YAxis
              tick={{ fontSize: 11 }}
              tickFormatter={(v: number) => `${v.toFixed(0)}`}
              domain={['auto', 'auto']}
              width={40}
            />
            <Tooltip
              formatter={(value: number) => [`${value.toFixed(1)}`, '']}
              labelFormatter={(label: string) => label}
              contentStyle={{ fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} formatter={(v) => v.split('.')[0]} />
            {buy.map((sym, i) => (
              <Line
                key={sym}
                type="monotone"
                dataKey={sym}
                name={sym}
                stroke={LINE_COLORS[i % LINE_COLORS.length]}
                dot={false}
                strokeWidth={1.5}
                connectNulls
              />
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
