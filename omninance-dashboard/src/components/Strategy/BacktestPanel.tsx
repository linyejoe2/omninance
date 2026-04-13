import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import Grid from '@mui/material/Grid'
import Stack from '@mui/material/Stack'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableRow from '@mui/material/TableRow'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import { useState } from 'react'
import {
  Bar,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { traderApi } from '../../services/traderApi'

interface BacktestParams {
  initial_capital: number
  partition: number
  volume_multiplier: number
  concentration_slope: number
  atr_multiplier: number
  back_test_period: number
}

interface ChartRow {
  date: string
  strategy: number
  benchmark?: number | null
  buy_count: number
  sell_count: number
  hold_count: number
}

interface BacktestResult {
  stats: Record<string, number | string | null>
  benchmark_stats: Record<string, number | string | null> | null
  chart: ChartRow[]
}

const STAT_KEYS: { key: string; label: string; format?: (v: number | string | null) => string }[] = [
  { key: 'Start', label: '開始日期' },
  { key: 'End', label: '結束日期' },
  { key: 'Period', label: '持有期間' },
  { key: 'Total Return [%]', label: '總回報率', format: (v) => v != null ? `${Number(v).toFixed(2)}%` : '—' },
  { key: 'Max Drawdown [%]', label: '最大回撤', format: (v) => v != null ? `${Number(v).toFixed(2)}%` : '—' },
  { key: 'Sharpe Ratio', label: 'Sharpe 比率', format: (v) => v != null ? Number(v).toFixed(3) : '—' },
  { key: 'Win Rate [%]', label: '勝率', format: (v) => v != null ? `${Number(v).toFixed(2)}%` : '—' },
  { key: 'Total Trades', label: '總交易次數', format: (v) => v != null ? String(v) : '—' },
]

function fmt(row: typeof STAT_KEYS[0], stats: Record<string, number | string | null>): string {
  const v = stats[row.key]
  if (v == null) return '—'
  if (row.format) return row.format(v)
  return String(v)
}

const DEFAULT_PARAMS: BacktestParams = {
  initial_capital: 100000,
  partition: 10,
  volume_multiplier: 2,
  concentration_slope: 0.02,
  atr_multiplier: 4,
  back_test_period: 4,
}

export function BacktestPanel() {
  const [params, setParams] = useState<BacktestParams>(DEFAULT_PARAMS)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BacktestResult | null>(null)

  const set = (key: keyof BacktestParams) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setParams((p) => ({ ...p, [key]: Number(e.target.value) }))

  const handleRun = async () => {
    setError(null)
    setLoading(true)
    try {
      const data = await traderApi.runBacktest(params)
      setResult(data as unknown as BacktestResult)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Stack spacing={3}>
      {/* Settings */}
      <Card variant="outlined">
        <CardContent>
          <Typography variant="subtitle2" fontWeight="bold" mb={2}>回測參數</Typography>
          <Grid container spacing={2}>
            <Grid item xs={6} sm={4}>
              <TextField label="初始資金 (NT$)" type="number" size="small" fullWidth
                value={params.initial_capital} onChange={set('initial_capital')} disabled={loading} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="資金分份" type="number" size="small" fullWidth
                value={params.partition} onChange={set('partition')} disabled={loading} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="成交量倍數" type="number" size="small" fullWidth
                value={params.volume_multiplier} onChange={set('volume_multiplier')} disabled={loading}
                inputProps={{ step: 0.1 }} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="大戶籌碼斜率" type="number" size="small" fullWidth
                value={params.concentration_slope} onChange={set('concentration_slope')} disabled={loading}
                inputProps={{ step: 0.001 }} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="止損 ATR 乘數" type="number" size="small" fullWidth
                value={params.atr_multiplier} onChange={set('atr_multiplier')} disabled={loading}
                inputProps={{ step: 0.5 }} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField label="回測年數" type="number" size="small" fullWidth
                value={params.back_test_period} onChange={set('back_test_period')} disabled={loading}
                inputProps={{ min: 1, max: 10 }} />
            </Grid>
          </Grid>

          <Box mt={2} display="flex" alignItems="center" gap={2}>
            <Button
              variant="contained"
              onClick={handleRun}
              disabled={loading}
              startIcon={loading ? <CircularProgress size={16} color="inherit" /> : undefined}
            >
              {loading ? '回測中…' : '執行回測'}
            </Button>
            {error && <Typography variant="body2" color="error">{error}</Typography>}
          </Box>
        </CardContent>
      </Card>

      {/* Results */}
      {result && (
        <>
          {/* Stats table */}
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle2" fontWeight="bold" mb={1}>績效報告</Typography>
              <Divider sx={{ mb: 1 }} />
              <Table size="small">
                <TableBody>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 'bold', borderBottom: 'none' }} />
                    <TableCell align="right" sx={{ fontWeight: 'bold', color: '#4fc3f7', borderBottom: 'none' }}>策略</TableCell>
                    {result.benchmark_stats && (
                      <TableCell align="right" sx={{ fontWeight: 'bold', color: '#81c784', borderBottom: 'none' }}>0050 基準</TableCell>
                    )}
                  </TableRow>
                  {STAT_KEYS.map((row) => {
                    const sv = fmt(row, result.stats)
                    const bv = result.benchmark_stats ? fmt(row, result.benchmark_stats) : null
                    const isReturn = row.key === 'Total Return [%]'
                    const sNum = isReturn ? parseFloat(String(result.stats[row.key] ?? 0)) : NaN
                    const bNum = isReturn && result.benchmark_stats ? parseFloat(String(result.benchmark_stats[row.key] ?? 0)) : NaN
                    return (
                      <TableRow key={row.key} hover>
                        <TableCell sx={{ color: 'text.secondary' }}>{row.label}</TableCell>
                        <TableCell align="right" sx={{ color: isReturn ? (sNum >= 0 ? 'success.main' : 'error.main') : undefined }}>
                          {sv}
                        </TableCell>
                        {result.benchmark_stats && (
                          <TableCell align="right" sx={{ color: isReturn ? (bNum >= 0 ? 'success.main' : 'error.main') : undefined }}>
                            {bv ?? '—'}
                          </TableCell>
                        )}
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Charts */}
          {result.chart.length > 0 && (
            <Card variant="outlined">
              <CardContent>
                {/* Value chart */}
                <Typography variant="subtitle2" fontWeight="bold" mb={2}>淨值走勢 (基準 = 100)</Typography>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={result.chart} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(2, 7).replace('-', '/')} minTickGap={40} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${v.toFixed(0)}`} domain={['auto', 'auto']} width={44} />
                    <Tooltip
                      formatter={(value: number, name: string) => [`${value.toFixed(1)}`, name === 'strategy' ? '策略' : '0050']}
                      labelFormatter={(l: string) => l}
                      contentStyle={{ fontSize: 12 }}
                    />
                    <ReferenceLine y={100} stroke="#555" strokeDasharray="4 2" />
                    <Legend formatter={(v) => (v === 'strategy' ? '策略' : '0050 基準')} wrapperStyle={{ fontSize: 12 }} />
                    <Line type="monotone" dataKey="strategy" stroke="#4fc3f7" dot={false} strokeWidth={2} connectNulls />
                    {result.benchmark_stats && (
                      <Line type="monotone" dataKey="benchmark" stroke="#81c784" dot={false} strokeWidth={1.5} connectNulls />
                    )}
                  </LineChart>
                </ResponsiveContainer>

                <Divider sx={{ my: 2 }} />

                {/* Activity chart */}
                <Typography variant="subtitle2" fontWeight="bold" mb={2}>每日交易活動</Typography>
                <ResponsiveContainer width="100%" height={200}>
                  <ComposedChart data={result.chart} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(2, 7).replace('-', '/')} minTickGap={40} />
                    <YAxis yAxisId="count" tick={{ fontSize: 11 }} width={36} allowDecimals={false} />
                    <YAxis yAxisId="hold" orientation="right" tick={{ fontSize: 11 }} width={36} allowDecimals={false} />
                    <Tooltip
                      formatter={(value: number, name: string) => {
                        const labels: Record<string, string> = { buy_count: '買入', sell_count: '賣出', hold_count: '持倉' }
                        return [value, labels[name] ?? name]
                      }}
                      labelFormatter={(l: string) => l}
                      contentStyle={{ fontSize: 12 }}
                    />
                    <Legend
                      formatter={(v) => (({ buy_count: '買入', sell_count: '賣出', hold_count: '持倉' } as any)[v] ?? v)}
                      wrapperStyle={{ fontSize: 12 }}
                    />
                    <Bar yAxisId="count" dataKey="buy_count" fill="#4fc3f7" opacity={0.8} maxBarSize={4} />
                    <Bar yAxisId="count" dataKey="sell_count" fill="#f06292" opacity={0.8} maxBarSize={4} />
                    <Line yAxisId="hold" type="monotone" dataKey="hold_count" stroke="#ffb74d" dot={false} strokeWidth={1.5} />
                  </ComposedChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </Stack>
  )
}
