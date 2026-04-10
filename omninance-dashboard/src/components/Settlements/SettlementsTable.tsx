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

export function SettlementsTable() {
  const { data, loading, error, lastUpdated, refresh } = useTraderData(traderApi.settlements)

  const columns = data && data.length > 0 ? Object.keys(data[0]) : []

  return (
    <Paper variant="outlined">
      <Toolbar sx={{ pl: 2, pr: 1 }}>
        <Typography variant="subtitle1" fontWeight="bold" sx={{ flexGrow: 1 }}>
          Settlements
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
              {columns.map((col) => (
                <TableCell key={col} sx={{ fontWeight: 'bold', textTransform: 'capitalize' }}>
                  {col.replace(/_/g, ' ')}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {loading && (
              <TableRow>
                <TableCell colSpan={Math.max(columns.length, 1)} align="center">
                  <CircularProgress size={20} />
                </TableCell>
              </TableRow>
            )}
            {error && (
              <TableRow>
                <TableCell colSpan={Math.max(columns.length, 1)}>
                  <Typography color="error" variant="body2">{error}</Typography>
                </TableCell>
              </TableRow>
            )}
            {data && data.length === 0 && (
              <TableRow>
                <TableCell colSpan={1} align="center">
                  <Typography variant="body2" color="text.secondary">No records</Typography>
                </TableCell>
              </TableRow>
            )}
            {data?.map((row, i) => (
              <TableRow key={i} hover>
                {columns.map((col) => (
                  <TableCell key={col}>{String(row[col] ?? '—')}</TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <Box sx={{ p: 1, display: 'flex', justifyContent: 'flex-end' }}>
        <Typography variant="caption" color="text.secondary">
          {data ? `${data.length} record(s)` : ''}
        </Typography>
      </Box>
    </Paper>
  )
}
