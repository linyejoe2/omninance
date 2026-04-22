import RefreshIcon from '@mui/icons-material/Refresh'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import CardHeader from '@mui/material/CardHeader'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Typography from '@mui/material/Typography'
import dayjs from 'dayjs'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import { useState } from 'react'
import { BacktestPanel } from '../components/Strategy/BacktestPanel'
import { ExecutePanel } from '../components/Strategy/ExecutePanel'
import { useTraderData } from '../hooks/useTraderData'
import { traderApi } from '../services/traderApi'

interface Snapshot { p: number; atr: number }

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
    <Paper variant="outlined">
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
                  <TableCell align="right">{snap ? snap.p.toFixed(2) : '—'}</TableCell>
                  <TableCell align="right">{snap ? snap.atr.toFixed(2) : '—'}</TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  )
}

export function Strategy() {
  const [tab, setTab] = useState(0)
  const { data: raw, loading, error, lastUpdated, refresh } =
    useTraderData(traderApi.signals as unknown as () => Promise<SignalData>)

  const meta = raw?.metadata
  const buy = raw?.actions?.buy ?? []
  const sell = raw?.actions?.sell_hint ?? []
  const snapshot = raw?.snapshot ?? {}

  return (
    <Box>
      <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 3 }}>
        <Tabs value={tab} onChange={(_, v: number) => setTab(v)}>
          <Tab label="Overview" />
          <Tab label="Backtest" />
          <Tab label="Execute" />
          {/* <Tab label="System" /> */}
        </Tabs>
      </Box>
      
      {tab === 0 && (
        <>
        <Card variant="outlined" sx={{ mb: 3 }}>
          <CardHeader
            title="策略訊號"
            titleTypographyProps={{ variant: 'subtitle1', fontWeight: 'bold' }}
            subheader={lastUpdated ? `Updated ${dayjs(lastUpdated).format('HH:mm:ss')}` : undefined}
            action={
              <IconButton size="small" onClick={refresh} disabled={loading}>
                <RefreshIcon fontSize="small" />
              </IconButton>
            }
          />
          <Divider />
          <CardContent>
            {loading && <CircularProgress size={20} />}
            {error && <Typography color="error" variant="body2">{error}</Typography>}
            {meta && (
              <Stack spacing={1.5}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">策略名稱</Typography>
                  <Typography variant="body2" fontWeight="medium">{meta.strategy}</Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">訊號日期</Typography>
                  <Typography variant="body2" fontWeight="medium">
                    {dayjs(meta.run_date, 'YYYYMMDD').format('YYYY-MM-DD')}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">執行日期</Typography>
                  <Typography variant="body2" fontWeight="medium" color="primary.main">
                    {meta.action_date}
                  </Typography>
                </Box>
                <Divider />
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">資金分份</Typography>
                  <Typography variant="body2" fontWeight="medium">{meta.params.partition} 份</Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">ATR 乘數</Typography>
                  <Typography variant="body2" fontWeight="medium">{meta.params.atr_mult}x</Typography>
                </Box>
              </Stack>
            )}
          </CardContent>
        </Card>

        <Stack spacing={2}>
          <SignalTable title="買入訊號" symbols={buy} snapshot={snapshot} chipColor="success" />
          <SignalTable title="減碼提示" symbols={sell} snapshot={snapshot} chipColor="warning" />
        </Stack>
        </>
      )}
      
      {tab === 1 && (
        <Box sx={{ p: 3 }}>
          <BacktestPanel />
        </Box>
      )}

      {tab === 2 && (
        <Box sx={{ p: 3 }}>
          <ExecutePanel />
        </Box>
      )}
    </Box>
  )
}
