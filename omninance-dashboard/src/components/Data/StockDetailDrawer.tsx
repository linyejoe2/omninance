import Box from '@mui/material/Box'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import Drawer from '@mui/material/Drawer'
import IconButton from '@mui/material/IconButton'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Typography from '@mui/material/Typography'
import CloseIcon from '@mui/icons-material/Close'
import dayjs from 'dayjs'
import { useEffect, useMemo, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { HolderRow, TickerPoint, traderApi } from '../../services/traderApi'

interface StockDetailDrawerProps {
  symbol: string | null
  onClose: () => void
}

type RangeKey = '1D' | '5D' | '1M' | '6M' | 'YTD' | '1Y' | '5Y' | 'MAX'

const RANGES: RangeKey[] = ['1D', '5D', '1M', '6M', 'YTD', '1Y', '5Y', 'MAX']

/** Filters ascending-by-date ticker data down to the trailing window, anchored
 * on the latest data point (not "today") so the range stays meaningful even
 * when the pipeline is a day or two behind. */
function filterByRange(data: TickerPoint[], range: RangeKey): TickerPoint[] {
  if (range === 'MAX' || data.length === 0) return data
  const last = dayjs(data[data.length - 1].date)
  const cutoff =
    range === '1D' ? last.subtract(1, 'day') :
    range === '5D' ? last.subtract(5, 'day') :
    range === '1M' ? last.subtract(1, 'month') :
    range === '6M' ? last.subtract(6, 'month') :
    range === 'YTD' ? last.startOf('year') :
    range === '1Y' ? last.subtract(1, 'year') :
    last.subtract(5, 'year') // 5Y
  return data.filter((d) => !dayjs(d.date).isBefore(cutoff))
}

const HOLDER_COLUMNS: { key: keyof HolderRow; label: string; format?: (v: number | null) => string }[] = [
  { key: 'date', label: '資料日期' },
  { key: 'close_price', label: '收盤價', format: (v) => (v == null ? '—' : v.toFixed(2)) },
  { key: 'total_shareholders', label: '總股東人數', format: (v) => (v == null ? '—' : v.toLocaleString()) },
  { key: 'avg_sheets_per_person', label: '平均張數/人', format: (v) => (v == null ? '—' : v.toFixed(2)) },
  { key: 'over400_percentage', label: '>400張持股%', format: (v) => (v == null ? '—' : `${v.toFixed(2)}%`) },
  { key: 'over1000_percentage', label: '>1000張持股%', format: (v) => (v == null ? '—' : `${v.toFixed(2)}%`) },
]

export function StockDetailDrawer({ symbol, onClose }: StockDetailDrawerProps) {
  const [tickers, setTickers] = useState<TickerPoint[]>([])
  const [holders, setHolders] = useState<HolderRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [range, setRange] = useState<RangeKey>('6M')

  useEffect(() => {
    if (!symbol) return
    let cancelled = false
    setLoading(true)
    setError(null)
    setTickers([])
    setHolders([])

    Promise.all([traderApi.getStockTickers(symbol), traderApi.getStockHolders(symbol)])
      .then(([tickerData, holderData]) => {
        if (cancelled) return
        setTickers(tickerData)
        setHolders(holderData)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [symbol])

  const holderRowsDesc = [...holders].reverse()
  const chartData = useMemo(() => filterByRange(tickers, range), [tickers, range])

  return (
    <Drawer anchor="right" open={symbol != null} onClose={onClose}>
      <Box sx={{ width: { xs: '100vw', sm: '70vw' }, p: 2 }} role="presentation">
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="h6" fontWeight="bold">{symbol}</Typography>
          <IconButton onClick={onClose} size="small">
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
        <Divider sx={{ mb: 2 }} />

        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={24} />
          </Box>
        )}
        {error && <Typography color="error" variant="body2">{error}</Typography>}

        {!loading && !error && (
          <>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1, flexWrap: 'wrap', gap: 1 }}>
              <Typography variant="subtitle2" fontWeight="bold">股價走勢 (收盤價)</Typography>
              <ToggleButtonGroup
                size="small"
                exclusive
                value={range}
                onChange={(_, v: RangeKey | null) => v && setRange(v)}
              >
                {RANGES.map((r) => (
                  <ToggleButton key={r} value={r} sx={{ px: 1, fontSize: 11 }}>
                    {r}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            </Box>
            {tickers.length === 0 ? (
              <Typography variant="body2" color="text.secondary" mb={2}>無股價資料</Typography>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v: string) => v.slice(2, 7).replace('-', '/')} minTickGap={40} />
                  <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} width={48} />
                  <Tooltip
                    formatter={(value: number, _name: string, item: any) => [
                      `${value.toFixed(2)} 元`,
                      `時間：${item.payload.date} | 收盤價`
                    ]}
                    contentStyle={{ fontSize: 12 }}
                  />
                  <Line type="monotone" dataKey="close" stroke="#4fc3f7" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            )}

            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" fontWeight="bold" mb={1}>大戶持股資料</Typography>
            {holderRowsDesc.length === 0 ? (
              <Typography variant="body2" color="text.secondary">無持股資料</Typography>
            ) : (
              <TableContainer sx={{ maxHeight: 360 }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      {HOLDER_COLUMNS.map((col) => (
                        <TableCell key={col.key} sx={{ fontWeight: 'bold' }}>{col.label}</TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {holderRowsDesc.map((row) => (
                      <TableRow key={row.date} hover>
                        {HOLDER_COLUMNS.map((col) => (
                          <TableCell key={col.key}>
                            {col.format ? col.format(row[col.key] as number | null) : String(row[col.key])}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </>
        )}
      </Box>
    </Drawer>
  )
}
