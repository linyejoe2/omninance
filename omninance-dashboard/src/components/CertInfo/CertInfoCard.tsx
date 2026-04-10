import RefreshIcon from '@mui/icons-material/Refresh'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import CardHeader from '@mui/material/CardHeader'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import dayjs from 'dayjs'
import { useTraderData } from '../../hooks/useTraderData'
import { traderApi } from '../../services/traderApi'

interface CertInfo {
  serial: string
  is_valid: boolean
  not_after: number         // Unix timestamp (seconds)
  cn: string
}

interface KeyInfo {
  api_key: string
  api_key_memo: string
  api_key_name: string
  created_at: { seconds: number; nanos: number }
  scope: string
  status: number
}

const STATUS_LABEL: Record<number, string> = { 1: '啟用', 0: '停用' }

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <Typography variant="body2" color="text.secondary">{label}</Typography>
      <Box sx={{ ml: 2, textAlign: 'right' }}>{children}</Box>
    </Box>
  )
}

function CertSection({ data }: { data: CertInfo }) {
  const expiry = dayjs.unix(data.not_after).format('YYYY-MM-DD HH:mm:ss')
  const isExpired = dayjs.unix(data.not_after).isBefore(dayjs())

  return (
    <Stack spacing={1.5}>
      <Typography variant="caption" color="text.secondary" fontWeight="bold" sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
        Certificate
      </Typography>
      <Row label="序號">{data.serial}</Row>
      <Row label="狀態">
        <Chip
          label={data.is_valid && !isExpired ? '有效' : '無效'}
          color={data.is_valid && !isExpired ? 'success' : 'error'}
          size="small"
          variant="outlined"
        />
      </Row>
      <Row label="到期日">
        <Typography variant="body2" color={isExpired ? 'error.main' : 'text.primary'}>
          {expiry}
        </Typography>
      </Row>
      <Row label="憑證名稱">
        <Typography variant="body2" sx={{ wordBreak: 'break-all', maxWidth: 260, textAlign: 'right' }}>
          {data.cn}
        </Typography>
      </Row>
    </Stack>
  )
}

function KeySection({ data }: { data: KeyInfo }) {
  const createdAt = dayjs.unix(data.created_at.seconds).format('YYYY-MM-DD HH:mm:ss')

  return (
    <Stack spacing={1.5}>
      <Typography variant="caption" color="text.secondary" fontWeight="bold" sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
        API Key
      </Typography>
      <Row label="Key">{data.api_key}</Row>
      <Row label="備註">{data.api_key_memo || '—'}</Row>
      <Row label="名稱">{data.api_key_name || '—'}</Row>
      <Row label="建立時間">{createdAt}</Row>
      <Row label="權限範圍">{data.scope}</Row>
      <Row label="狀態">
        <Chip
          label={STATUS_LABEL[data.status] ?? data.status}
          color={data.status === 1 ? 'success' : 'default'}
          size="small"
          variant="outlined"
        />
      </Row>
    </Stack>
  )
}

export function CertInfoCard() {
  const cert = useTraderData(traderApi.certInfo as unknown as () => Promise<CertInfo>, 0)
  const key = useTraderData(traderApi.keyInfo as unknown as () => Promise<KeyInfo>, 0)

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
        title="憑證 & API Key"
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
          {cert.data && <CertSection data={cert.data} />}
          {key.data && <KeySection data={key.data} />}
        </Stack>
      </CardContent>
    </Card>
  )
}
