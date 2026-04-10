import RefreshIcon from '@mui/icons-material/Refresh'
import Box from '@mui/material/Box'
import CircularProgress from '@mui/material/CircularProgress'
import IconButton from '@mui/material/IconButton'
import Paper from '@mui/material/Paper'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import dayjs from 'dayjs'
import { useTraderData } from '../../hooks/useTraderData'
import { traderApi } from '../../services/traderApi'

const COLUMN_LABELS: Record<string, string> = {
  stk_no:        '股票代碼',
  stk_na:        '股票名稱',
  s_type:        '市場別',
  ap_code:       '盤別',
  trade:         '交易類別',
  price_now:     '即時價格',
  price_mkt:     '即時價格(無權息)',
  price_avg:     '成交均價',
  price_evn:     '損益平衡價',
  qty_l:         '昨餘額(股)',
  cost_qty:      '成本股數',
  qty_b:         '今委買(股)',
  qty_bm:        '今委買成交(股)',
  qty_s:         '今委賣(股)',
  qty_sm:        '今委賣成交(股)',
  qty_c:         '調整股數',
  make_a_sum:    '未實現損益',
  make_a_per:    '獲利率(%)',
  cost_sum:      '成本總計',
  rec_va_sum:    '未實現收入',
  price_qty_sum: '價金總計',
  value_now:     '市值',
  value_mkt:     '市值(無權息)',
}

// Display order — excludes nested stk_dats
const COLUMNS = [
  'stk_no', 'stk_na', 's_type',
  'price_now', 'price_avg', 'price_evn',
  'qty_l', 'cost_qty',
  'make_a_sum', 'make_a_per',
  'value_now', 'cost_sum',
]

const S_TYPE: Record<string, string> = { H: '上市', O: '上櫃', R: '興櫃' }

function cellColor(col: string, value: string): string | undefined {
  if (col !== 'make_a_sum' && col !== 'make_a_per') return undefined
  const n = parseFloat(value)
  if (n > 0) return 'success.main'
  if (n < 0) return 'error.main'
  return undefined
}

export function InventoriesTable() {
  const { data, loading, error, lastUpdated, refresh } = useTraderData(traderApi.inventories)

  return (
    <Paper variant="outlined">
      <Toolbar sx={{ pl: 2, pr: 1 }}>
        <Typography variant="subtitle1" fontWeight="bold" sx={{ flexGrow: 1 }}>
          庫存
        </Typography>
        {lastUpdated && (
          <Typography variant="caption" color="text.secondary" sx={{ mr: 1 }}>
            {dayjs(lastUpdated).format('HH:mm:ss')}
          </Typography>
        )}
        <IconButton size="small" onClick={refresh} disabled={loading}>
          <RefreshIcon fontSize="small" />
        </IconButton>
      </Toolbar>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              {COLUMNS.map((col) => (
                <TableCell key={col} sx={{ fontWeight: 'bold', whiteSpace: 'nowrap' }}>
                  {COLUMN_LABELS[col] ?? col}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {loading && (
              <TableRow>
                <TableCell colSpan={COLUMNS.length} align="center">
                  <CircularProgress size={20} />
                </TableCell>
              </TableRow>
            )}
            {error && (
              <TableRow>
                <TableCell colSpan={COLUMNS.length}>
                  <Typography color="error" variant="body2">{error}</Typography>
                </TableCell>
              </TableRow>
            )}
            {data?.length === 0 && (
              <TableRow>
                <TableCell colSpan={COLUMNS.length} align="center">
                  <Typography variant="body2" color="text.secondary">無庫存資料</Typography>
                </TableCell>
              </TableRow>
            )}
            {data?.map((row, i) => (
              <TableRow key={i} hover>
                {COLUMNS.map((col) => {
                  const raw = col === 's_type'
                    ? (S_TYPE[String(row[col])] ?? String(row[col] ?? '—'))
                    : String(row[col] ?? '—')
                  return (
                    <TableCell key={col} sx={{ whiteSpace: 'nowrap', color: cellColor(col, raw) }}>
                      {raw}
                    </TableCell>
                  )
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <Box sx={{ p: 1, display: 'flex', justifyContent: 'flex-end' }}>
        <Typography variant="caption" color="text.secondary">
          {data ? `${data.length} 檔` : ''}
        </Typography>
      </Box>
    </Paper>
  )
}
