import Box from '@mui/material/Box'
import Grid from '@mui/material/Grid'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import { useState } from 'react'
import { BalanceCard } from '../components/Balance/BalanceCard'
import { CertInfoCard } from '../components/CertInfo/CertInfoCard'
import { InventoriesTable } from '../components/Inventories/InventoriesTable'
import { SettlementsTable } from '../components/Settlements/SettlementsTable'
import { TradeStatusCard } from '../components/TradeStatus/TradeStatusCard'

export function Dashboard() {
  const [tab, setTab] = useState(0)

  return (
    <Box>
      <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 3 }}>
        <Tabs value={tab} onChange={(_, v: number) => setTab(v)}>
          <Tab label="Overview" />
          <Tab label="Inventories" />
          <Tab label="Settlements" />
          <Tab label="System" />
        </Tabs>
      </Box>

      {tab === 0 && (
        <Box sx={{ p: 3 }}>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6} lg={4}>
              <BalanceCard />
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
              <TradeStatusCard />
            </Grid>
          </Grid>
        </Box>
      )}

      {tab === 1 && (
        <Box sx={{ p: 3 }}>
          <InventoriesTable />
        </Box>
      )}

      {tab === 2 && (
        <Box sx={{ p: 3 }}>
          <SettlementsTable />
        </Box>
      )}

      {tab === 3 && (
        <Box sx={{ p: 3 }}>
          <Grid container spacing={3}>
            <Grid item xs={12} md={8} lg={6}>
              <CertInfoCard />
            </Grid>
          </Grid>
        </Box>
      )}
    </Box>
  )
}
