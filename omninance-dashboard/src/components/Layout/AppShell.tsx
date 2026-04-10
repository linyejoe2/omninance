import AppBar from '@mui/material/AppBar'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Toolbar from '@mui/material/Toolbar'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import dayjs from 'dayjs'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'
import { ReactNode, useEffect, useState } from 'react'
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

interface AppShellProps {
  children: ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const { data: market } = useTraderData(traderApi.marketStatus, 60_000)
  const [state, setState] = useState<MarketState>('收市')

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
              title={<img src="/img/market-time.png" alt="Market hours" style={{
                display: 'block', 
                width: 360,           // 正常寬度
              }} />}
              placement="bottom-end"
              slotProps={{
                tooltip: {
                  sx: {
                    maxWidth: 'none',     // 關鍵：解除 MUI 預設的 300px 限制
                }},
                popper: {
                  modifiers: [
                    {
                      name: 'preventOverflow',
                      options: {
                        boundary: 'viewport', // 以視窗為邊界
                        padding: 8,           // 距離視窗邊緣至少保留 8px
                      },
                    },
                  ],
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
      <Box component="main" sx={{ flexGrow: 1, bgcolor: 'background.default' }}>
        {children}
      </Box>
    </Box>
  )
}
