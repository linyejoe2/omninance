import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import AppBar from '@mui/material/AppBar'
import BottomNavigation from '@mui/material/BottomNavigation'
import BottomNavigationAction from '@mui/material/BottomNavigationAction'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Paper from '@mui/material/Paper'
import Toolbar from '@mui/material/Toolbar'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import dayjs from 'dayjs'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'
import { ReactNode, useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useTraderData } from '../../hooks/useTraderData'
import { traderApi } from '../../services/traderApi'

dayjs.extend(utc)
dayjs.extend(timezone)

type MarketState = '盤前' | '盤中' | '盤後' | '收市'

const STATE_COLOR: Record<MarketState, 'warning' | 'success' | 'info' | 'default'> = {
  '盤前': 'warning',
  '盤中': 'success',
  '盤後': 'info',
  '收市': 'default',
}

function getMarketState(isTradingDay: boolean): MarketState {
  if (!isTradingDay) return '收市'
  const now = dayjs().tz('Asia/Taipei')
  const m = now.hour() * 60 + now.minute()
  if (m >= 510 && m < 540) return '盤前'   // 08:30–09:00
  if (m >= 540 && m < 810) return '盤中'   // 09:00–13:30
  if (m >= 810 && m < 870) return '盤後'   // 13:30–14:30
  return '收市'
}

const NAV_ROUTES = ['/account', '/strategy']

interface AppShellProps {
  children: ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const { data: market } = useTraderData(traderApi.marketStatus, 300_000)
  const [state, setState] = useState<MarketState>('收市')
  const location = useLocation()
  const navigate = useNavigate()

  const navValue = NAV_ROUTES.indexOf(location.pathname) === -1 ? 0 : NAV_ROUTES.indexOf(location.pathname)

  useEffect(() => {
    const isTradingDay = market?.['is_trading_day'] === true
    setState(getMarketState(isTradingDay))
    const id = setInterval(() => setState(getMarketState(isTradingDay)), 60_000)
    return () => clearInterval(id)
  }, [market])

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar position="static" elevation={0} sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Toolbar>
          <Typography variant="h6" fontWeight="bold" sx={{ flexGrow: 1, letterSpacing: 1 }}>
            OmniTrader
          </Typography>
          {market && (
            <Tooltip
              title={<img src="/img/market-time.png" alt="Market hours" style={{ display: 'block', width: 360 }} />}
              placement="bottom-end"
              slotProps={{
                tooltip: { sx: { maxWidth: 'none' } },
                popper: {
                  modifiers: [{ name: 'preventOverflow', options: { boundary: 'viewport', padding: 8 } }],
                },
              }}
            >
              <Chip
                label={state}
                color={STATE_COLOR[state]}
                size="small"
                variant="outlined"
                sx={{ cursor: 'default' }}
              />
            </Tooltip>
          )}
        </Toolbar>
      </AppBar>

      <Box component="main" sx={{ flexGrow: 1, pb: 7 }}>
        {children}
      </Box>

      <Paper elevation={3} sx={{ position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 1100 }}>
        <BottomNavigation
          value={navValue}
          onChange={(_, v: number) => navigate(NAV_ROUTES[v])}
          showLabels
        >
          <BottomNavigationAction label="帳戶" icon={<AccountBalanceWalletIcon />} />
          <BottomNavigationAction label="策略" icon={<TrendingUpIcon />} />
        </BottomNavigation>
      </Paper>
    </Box>
  )
}
