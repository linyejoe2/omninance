import { useCallback, useEffect, useRef, useState } from 'react'

interface TraderDataState<T> {
  data: T | null
  loading: boolean
  error: string | null
  lastUpdated: Date | null
  refresh: () => void
}

export function useTraderData<T>(
  fetcher: () => Promise<T>,
  intervalMs = 30_000
): TraderDataState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetcherRef.current()
      setData(result)
      setLastUpdated(new Date())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    if (intervalMs > 0) {
      const id = setInterval(refresh, intervalMs)
      return () => clearInterval(id)
    }
  }, [refresh, intervalMs])

  return { data, loading, error, lastUpdated, refresh }
}
