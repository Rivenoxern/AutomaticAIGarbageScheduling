/**
 * components/Header.jsx
 * ──────────────────────
 * Sticky top navigation bar showing brand, live clock, and connection status.
 */
import { useState, useEffect } from 'react'

export default function Header({ lastUpdated }) {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  const fmtTime = t =>
    t.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  return (
    <header className="app-header">
      <div className="header-brand">
        <span className="header-logo">🗑️</span>
        <div>
          <div className="header-title">WasteWay</div>
          <div className="header-subtitle">Agentic AI Garbage Truck Scheduling</div>
        </div>
      </div>

      <div className="header-meta">
        {lastUpdated && (
          <span>
            Last sync:{' '}
            <span style={{ color: 'var(--text-primary)' }}>
              {new Date(lastUpdated).toLocaleTimeString('id-ID')}
            </span>
          </span>
        )}
        <span>
          <span className="pulse-dot" />
          Live · {fmtTime(time)}
        </span>
      </div>
    </header>
  )
}
