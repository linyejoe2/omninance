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

function InfoSection({ title, data }: { title: string; data: Record<string, unknown> }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" fontWeight="bold" sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
        {title}
      </Typography>
      <Stack spacing={1} sx={{ mt: 1 }}>
        {Object.entries(data).map(([key, value]) => (
          <Box key={key} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'capitalize' }}>
              {key.replace(/_/g, ' ')}
            </Typography>
            <Typography variant="body2" fontWeight="medium" sx={{ ml: 2, wordBreak: 'break-all', textAlign: 'right', maxWidth: '60%' }}>
              {String(value ?? '—')}
            </Typography>
          </Box>
        ))}
      </Stack>
    </Box>
  )
}

export function CertInfoCard() {
  const cert = useTraderData(traderApi.certInfo, 0)
  const key = useTraderData(traderApi.keyInfo, 0)

  const loading = cert.loading || key.loading
  const error = cert.error || key.error
  const lastUpdated = cert.lastUpdated ?? key.lastUpdated

  function refresh() {
    cert.refresh()
    key.refresh()
  }

  return (
    <Card variant="outlined">
      <CardHeader
        title="Cert & Key Info"
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
        <Stack spacing={3} divider={<Divider />}>
          {cert.data && <InfoSection title="Certificate" data={cert.data} />}
          {key.data && <InfoSection title="API Key" data={key.data} />}
        </Stack>
      </CardContent>
    </Card>
  )
}
