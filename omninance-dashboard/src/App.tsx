import CssBaseline from '@mui/material/CssBaseline'
import { createTheme, ThemeProvider } from '@mui/material/styles'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ToastContainer } from 'react-toastify'
import 'react-toastify/dist/ReactToastify.css'
import { AppShell } from './components/Layout/AppShell'
import { Dashboard } from './pages/Dashboard'

const theme = createTheme({ palette: { mode: 'dark' } })

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <AppShell>
          <Routes>
            <Route path="/" element={<Dashboard />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
      <ToastContainer position="bottom-right" theme="dark" />
    </ThemeProvider>
  )
}
