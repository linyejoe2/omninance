import BoltIcon from '@mui/icons-material/Bolt'
import RefreshIcon from '@mui/icons-material/Refresh'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import IconButton from '@mui/material/IconButton'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemText from '@mui/material/ListItemText'
import Paper from '@mui/material/Paper'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import dayjs from 'dayjs'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'
import { useCallback, useEffect, useState } from 'react'
import { useTraderData } from '../hooks/useTraderData'
import { ScheduleLogRow, traderApi } from '../services/traderApi'

dayjs.extend(utc)
dayjs.extend(timezone)

function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  return dayjs.utc(value).tz('Asia/Taipei').format('YYYY-MM-DD HH:mm:ss')
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

function StatusChip({ status }: { status: string }) {
  return (
    <Chip
      label={status === 'success' ? '成功' : '失敗'}
      color={status === 'success' ? 'success' : 'error'}
      size="small"
      variant="outlined"
    />
  )
}

export function Schedule() {
  const { data: schedules, loading, error, refresh } = useTraderData(traderApi.listSchedules, 60_000)
  const [selectedJob, setSelectedJob] = useState<string | null>(null)
  const [logs, setLogs] = useState<ScheduleLogRow[] | null>(null)
  const [logsLoading, setLogsLoading] = useState(false)
  const [logsError, setLogsError] = useState<string | null>(null)
  const [triggering, setTriggering] = useState(false)
  const [triggerError, setTriggerError] = useState<string | null>(null)

  // Auto-select the first schedule once the list arrives
  useEffect(() => {
    if (!selectedJob && schedules && schedules.length > 0) {
      setSelectedJob(schedules[0].job)
    }
  }, [schedules, selectedJob])

  const loadLogs = useCallback(async (job: string) => {
    setLogsLoading(true)
    setLogsError(null)
    try {
      setLogs(await traderApi.getScheduleLogs(job))
    } catch (e) {
      setLogsError(e instanceof Error ? e.message : 'Unknown error')
      setLogs(null)
    } finally {
      setLogsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (selectedJob) loadLogs(selectedJob)
  }, [selectedJob, loadLogs])

  const handleRefresh = () => {
    refresh()
    if (selectedJob) loadLogs(selectedJob)
  }

  const handleForceExecute = async () => {
    if (!selectedJob) return
    setTriggering(true)
    setTriggerError(null)
    try {
      await traderApi.triggerSchedule(selectedJob)
    } catch (e) {
      setTriggerError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setTriggering(false)
      handleRefresh()
    }
  }

  return (
    <Box
      sx={{
        p: 3,
        display: 'flex',
        gap: 2,
        alignItems: 'flex-start',
        flexDirection: { xs: 'column', md: 'row' },
      }}
    >
      {/* Left — schedule list */}
      <Paper variant="outlined" sx={{ width: { xs: '100%', md: 340 }, flexShrink: 0 }}>
        <Toolbar sx={{ gap: 2 }}>
          <Typography variant="h6" fontWeight="bold" sx={{ flexGrow: 1 }}>
            排程
          </Typography>
          <IconButton size="small" onClick={handleRefresh} disabled={loading}>
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Toolbar>

        {error && (
          <Typography color="error" variant="body2" sx={{ px: 2, pb: 1 }}>
            {error}
          </Typography>
        )}

        {loading && !schedules && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={20} />
          </Box>
        )}

        <List disablePadding>
          {(schedules ?? []).map((s) => (
            <ListItemButton
              key={s.job}
              selected={s.job === selectedJob}
              onClick={() => setSelectedJob(s.job)}
              sx={{ borderTop: 1, borderColor: 'divider', alignItems: 'flex-start' }}
            >
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body1" fontWeight="bold" sx={{ flexGrow: 1 }}>
                      {s.job}
                    </Typography>
                    {s.last_run && <StatusChip status={s.last_run.status} />}
                  </Box>
                }
                secondary={
                  <>
                    <Typography variant="caption" component="span" display="block" color="text.secondary">
                      {s.schedule}
                    </Typography>
                    <Typography variant="caption" component="span" display="block" color="text.secondary">
                      上次執行: {formatTime(s.last_run?.started_at)}
                    </Typography>
                  </>
                }
              />
            </ListItemButton>
          ))}
        </List>
      </Paper>

      {/* Right — execution logs of the selected schedule */}
      <Paper variant="outlined" sx={{ flexGrow: 1, minWidth: 0, width: { xs: '100%', md: 'auto' } }}>
        <Toolbar sx={{ gap: 2 }}>
          <Typography variant="h6" fontWeight="bold" sx={{ flexGrow: 1 }}>
            執行紀錄{selectedJob ? ` — ${selectedJob}` : ''}
          </Typography>
          <Button
            size="small"
            variant="outlined"
            startIcon={triggering ? <CircularProgress size={14} /> : <BoltIcon fontSize="small" />}
            onClick={handleForceExecute}
            disabled={!selectedJob || triggering}
          >
            強制執行
          </Button>
        </Toolbar>

        {logsError && (
          <Typography color="error" variant="body2" sx={{ px: 2, pb: 1 }}>
            {logsError}
          </Typography>
        )}

        {triggerError && (
          <Typography color="error" variant="body2" sx={{ px: 2, pb: 1 }}>
            強制執行失敗: {triggerError}
          </Typography>
        )}

        {logsLoading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={20} />
          </Box>
        )}

        {!logsLoading && (logs?.length ?? 0) === 0 && (
          <Typography variant="body2" color="text.secondary" align="center" sx={{ py: 4 }}>
            尚無執行紀錄
          </Typography>
        )}

        {!logsLoading &&
          (logs ?? []).map((log, i) => (
            <Box key={i} sx={{ px: 2, py: 1.5, borderTop: 1, borderColor: 'divider' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                <Typography variant="body2" fontWeight="bold">
                  {formatTime(log.started_at)}
                </Typography>
                <StatusChip status={log.status} />
                <Typography variant="caption" color="text.secondary">
                  耗時 {formatDuration(log.duration_ms)}
                </Typography>
              </Box>
              {log.output != null && (
                <Box
                  component="pre"
                  sx={{
                    m: 0,
                    mt: 1,
                    p: 1.5,
                    bgcolor: 'action.hover',
                    borderRadius: 1,
                    fontSize: 12,
                    fontFamily: 'monospace',
                    overflowX: 'auto',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {JSON.stringify(log.output, null, 2)}
                </Box>
              )}
            </Box>
          ))}
      </Paper>
    </Box>
  )
}
