import CssBaseline from '@mui/material/CssBaseline'
import { createTheme, ThemeProvider } from '@mui/material/styles'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ToastContainer } from 'react-toastify'
import 'react-toastify/dist/ReactToastify.css'
import { AppShell } from './components/Layout/AppShell'
import { Account } from './pages/Account'
import { Strategy } from './pages/Strategy'

const theme = createTheme({ palette: { mode: 'dark' } })

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <AppShell>
          <Routes>
            <Route path="/" element={<Navigate to="/account" replace />} />
            <Route path="/account" element={<Account />} />
            <Route path="/strategy" element={<Strategy />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
      <ToastContainer position="bottom-right" theme="dark" />
    </ThemeProvider>
  )
}
