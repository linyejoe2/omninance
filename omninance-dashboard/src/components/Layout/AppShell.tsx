import AppBar from '@mui/material/AppBar'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import { ReactNode } from 'react'
import { useTraderData } from '../../hooks/useTraderData'
import { traderApi } from '../../services/traderApi'

interface AppShellProps {
  children: ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const { data: market } = useTraderData(traderApi.marketStatus, 60_000)

  const isOpen = Boolean(market?.['is_open'] || market?.['status'] === 'open')

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar position="static" elevation={0} sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Toolbar>
          <Typography variant="h6" fontWeight="bold" sx={{ flexGrow: 1, letterSpacing: 1 }}>
            OmniTrader
          </Typography>
          {market && (
            <Chip
              label={isOpen ? 'Market Open' : 'Market Closed'}
              color={isOpen ? 'success' : 'default'}
              size="small"
              variant="outlined"
            />
          )}
        </Toolbar>
      </AppBar>
      <Box component="main" sx={{ flexGrow: 1, bgcolor: 'background.default' }}>
        {children}
      </Box>
    </Box>
  )
}
