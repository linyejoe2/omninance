import RefreshIcon from '@mui/icons-material/Refresh'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import IconButton from '@mui/material/IconButton'
import InputAdornment from '@mui/material/InputAdornment'
import Paper from '@mui/material/Paper'
import SearchIcon from '@mui/icons-material/Search'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TablePagination from '@mui/material/TablePagination'
import TableRow from '@mui/material/TableRow'
import TableSortLabel from '@mui/material/TableSortLabel'
import TextField from '@mui/material/TextField'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import { useMemo, useState } from 'react'
import { StockDetailDrawer } from '../components/Data/StockDetailDrawer'
import { useTraderData } from '../hooks/useTraderData'
import { StockListItem, traderApi } from '../services/traderApi'

type SortKey = keyof StockListItem
type Order = 'asc' | 'desc'

interface Column {
  key: SortKey
  label: string
  align?: 'right'
  format?: (row: StockListItem) => React.ReactNode
}

const COLUMNS: Column[] = [
  { key: 'rank', label: '排名', align: 'right', format: (r) => r.rank ?? '—' },
  { key: 'symbol', label: '代號' },
  { key: 'name', label: '名稱', format: (r) => r.name ?? '—' },
  { key: 'close', label: '收盤價', align: 'right', format: (r) => (r.close != null ? r.close.toFixed(2) : '—') },
  { key: 'mkt_val', label: '市值 (百萬)', align: 'right', format: (r) => (r.mkt_val != null ? r.mkt_val.toLocaleString() : '—') },
  { key: 'mkt_val_ratio', label: '大盤佔比', align: 'right', format: (r) => (r.mkt_val_ratio != null ? `${(r.mkt_val_ratio * 100).toFixed(2)}%` : '—') },
  { key: 'tag', label: '標籤', format: (r) => (r.tag ? <Chip label={r.tag} size="small" variant="outlined" /> : '—') },
  { key: 'date', label: '資料日期', format: (r) => r.date ?? '—' },
]

function compare(a: StockListItem, b: StockListItem, key: SortKey): number {
  const av = a[key]
  const bv = b[key]
  if (av == null && bv == null) return 0
  if (av == null) return 1
  if (bv == null) return -1
  if (typeof av === 'number' && typeof bv === 'number') return av - bv
  return String(av).localeCompare(String(bv))
}

export function Data() {
  const { data, loading, error, refresh } = useTraderData(traderApi.listStockList, 0)
  const [search, setSearch] = useState('')
  const [orderBy, setOrderBy] = useState<SortKey>('rank')
  const [order, setOrder] = useState<Order>('asc')
  const [page, setPage] = useState(0)
  const [rowsPerPage, setRowsPerPage] = useState(25)
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)

  const rows = data ?? []

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return rows
    return rows.filter(
      (r) => r.symbol.toLowerCase().includes(q) || (r.name?.toLowerCase().includes(q) ?? false)
    )
  }, [rows, search])

  const sorted = useMemo(() => {
    const copy = [...filtered]
    copy.sort((a, b) => (order === 'asc' ? compare(a, b, orderBy) : -compare(a, b, orderBy)))
    return copy
  }, [filtered, orderBy, order])

  const paged = sorted.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)

  const handleSort = (key: SortKey) => {
    if (orderBy === key) {
      setOrder((o) => (o === 'asc' ? 'desc' : 'asc'))
    } else {
      setOrderBy(key)
      setOrder('asc')
    }
    setPage(0)
  }

  return (
    <Box sx={{ p: 3 }}>
      <Paper variant="outlined">
        <Toolbar sx={{ gap: 2, flexWrap: 'wrap' }}>
          <Typography variant="h6" fontWeight="bold" sx={{ flexGrow: 1 }}>
            股票清單
          </Typography>
          <TextField
            size="small"
            placeholder="搜尋代號或名稱"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(0)
            }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
          <IconButton size="small" onClick={refresh} disabled={loading}>
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Toolbar>

        {error && (
          <Typography color="error" variant="body2" sx={{ px: 2, pb: 1 }}>
            {error}
          </Typography>
        )}

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                {COLUMNS.map((col) => (
                  <TableCell key={col.key} align={col.align} sx={{ fontWeight: 'bold' }}>
                    <TableSortLabel
                      active={orderBy === col.key}
                      direction={orderBy === col.key ? order : 'asc'}
                      onClick={() => handleSort(col.key)}
                    >
                      {col.label}
                    </TableSortLabel>
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {loading && (
                <TableRow>
                  <TableCell colSpan={COLUMNS.length} align="center" sx={{ py: 4 }}>
                    <CircularProgress size={20} />
                  </TableCell>
                </TableRow>
              )}
              {!loading && paged.length === 0 && (
                <TableRow>
                  <TableCell colSpan={COLUMNS.length} align="center" sx={{ py: 4 }}>
                    <Typography variant="body2" color="text.secondary">查無資料</Typography>
                  </TableCell>
                </TableRow>
              )}
              {!loading &&
                paged.map((row) => (
                  <TableRow
                    key={row.symbol}
                    hover
                    onClick={() => setSelectedSymbol(row.symbol)}
                    sx={{ cursor: 'pointer' }}
                  >
                    {COLUMNS.map((col) => (
                      <TableCell key={col.key} align={col.align}>
                        {col.format ? col.format(row) : String(row[col.key] ?? '—')}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
            </TableBody>
          </Table>
        </TableContainer>

        <TablePagination
          component="div"
          count={sorted.length}
          page={page}
          onPageChange={(_, p) => setPage(p)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={(e) => {
            setRowsPerPage(parseInt(e.target.value, 10))
            setPage(0)
          }}
          rowsPerPageOptions={[10, 25, 50, 100]}
        />
      </Paper>

      <StockDetailDrawer symbol={selectedSymbol} onClose={() => setSelectedSymbol(null)} />
    </Box>
  )
}
