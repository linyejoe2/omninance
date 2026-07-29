import Box from '@mui/material/Box'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import { useState } from 'react'
import { BacktestPanel } from '../components/Strategy/BacktestPanel'
import { ExecutePanel } from '../components/Strategy/ExecutePanel'
import { OverviewPanel } from '../components/Strategy/OverviewPanel'

export function Strategy() {
  const [tab, setTab] = useState(0)

  return (
    <Box>
      <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 3 }}>
        <Tabs value={tab} onChange={(_, v: number) => setTab(v)}>
          <Tab label="Overview" />
          <Tab label="Backtest" />
          <Tab label="Execute" />
        </Tabs>
      </Box>

      {tab === 0 && (
        <Box sx={{ p: 3 }}>
          <OverviewPanel />
        </Box>
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
