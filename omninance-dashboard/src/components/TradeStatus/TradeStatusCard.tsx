import RefreshIcon from '@mui/icons-material/Refresh'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import CardHeader from '@mui/material/CardHeader'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import dayjs from 'dayjs'
import { useTraderData } from '../../hooks/useTraderData'
import { traderApi } from '../../services/traderApi'

export function TradeStatusCard() {
  const { data, loading, error, lastUpdated, refresh } = useTraderData(traderApi.tradeStatus)

  return (
    <Card variant="outlined">
      <CardHeader
        title="Trade Status"
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
        {data && (
          <Stack spacing={1.5}>
            {Object.entries(data).map(([key, value]) => (
              <Box key={key} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'capitalize' }}>
                  {key.replace(/_/g, ' ')}
                </Typography>
                <Typography variant="body2" fontWeight="medium">
                  {String(value ?? '—')}
                </Typography>
              </Box>
            ))}
          </Stack>
        )}
      </CardContent>
    </Card>
  )
}
