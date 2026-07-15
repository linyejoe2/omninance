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
import Typography from '@mui/material/Typography'
import CloseIcon from '@mui/icons-material/Close'
import { useEffect, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { HolderRow, TickerPoint, traderApi } from '../../services/traderApi'

interface StockDetailDrawerProps {
  symbol: string | null
  onClose: () => void
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
            <Typography variant="subtitle2" fontWeight="bold" mb={1}>股價走勢 (收盤價)</Typography>
            {tickers.length === 0 ? (
              <Typography variant="body2" color="text.secondary" mb={2}>無股價資料</Typography>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={tickers} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v: string) => v.slice(2, 7).replace('-', '/')} minTickGap={40} />
                  <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} width={48} />
                  <Tooltip
                    formatter={(value: number) => [value.toFixed(2), '收盤價']}
                    labelFormatter={(l: string) => l}
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
