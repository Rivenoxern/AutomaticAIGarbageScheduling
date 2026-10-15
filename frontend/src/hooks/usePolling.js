/**
 * hooks/usePolling.js
 * ────────────────────
 * Generic polling hook: calls fetchFn immediately, then every `interval` ms.
 * Returns { data, loading, error, refetch }.
 *
 * Usage:
 *   const { data: bins, loading } = usePolling(() => binsApi.list(), 5000)
 */
import { useState, useEffect, useCallback, useRef } from 'react'

export function usePolling(fetchFn, interval = 5000) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  // Keep fetchFn stable across renders without going stale
  const fetchRef = useRef(fetchFn)
  useEffect(() => { fetchRef.current = fetchFn }, [fetchFn])

  const run = useCallback(async () => {
    try {
      const result = await fetchRef.current()
      setData(result)
      setError(null)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Network error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    run()
    const id = setInterval(run, interval)
    return () => clearInterval(id)
  }, [run, interval])

  return { data, loading, error, refetch: run }
}
