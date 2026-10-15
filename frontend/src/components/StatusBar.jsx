/**
 * components/StatusBar.jsx
 * ─────────────────────────
 * Top-level KPI summary row: total bins, overflowing, idle/en-route/OOS trucks,
 * active tasks, and open crises.
 */
export default function StatusBar({ bins, trucks, tasks, crises }) {
  const overflowing  = (bins   || []).filter(b => b.current_capacity_pct >= 75).length
  const critical     = (bins   || []).filter(b => b.current_capacity_pct >= 90).length
  const idle         = (trucks || []).filter(t => t.status === 'idle').length
  const enRoute      = (trucks || []).filter(t => t.status === 'en_route').length
  const oos          = (trucks || []).filter(t => t.status === 'out_of_service').length
  const activeTasks  = (tasks  || []).filter(t => t.status === 'active').length
  const openCrises   = (crises || []).filter(c => !c.resolved).length

  const stats = [
    {
      label: 'Total Bins',
      value: (bins || []).length,
      sub: `${overflowing} overflowing · ${critical} critical`,
      color: critical > 0 ? 'var(--accent-red)' : overflowing > 0 ? 'var(--accent-orange)' : 'var(--text-primary)',
    },
    {
      label: 'Idle Trucks',
      value: idle,
      sub: `${(trucks || []).length} total fleet`,
      color: 'var(--accent-green)',
    },
    {
      label: 'En Route',
      value: enRoute,
      sub: `${activeTasks} active task(s)`,
      color: 'var(--accent-blue)',
    },
    {
      label: 'Out of Service',
      value: oos,
      sub: 'breakdown / maintenance',
      color: oos > 0 ? 'var(--accent-red)' : 'var(--text-muted)',
    },
    {
      label: 'Open Crises',
      value: openCrises,
      sub: openCrises > 0 ? '⚠️ requires attention' : 'all clear',
      color: openCrises > 0 ? 'var(--accent-red)' : 'var(--text-muted)',
    },
  ]

  return (
    <div className="status-bar" style={{ gridColumn: '1 / -1' }}>
      {stats.map(s => (
        <div key={s.label} className="stat-card">
          <span className="stat-label">{s.label}</span>
          <span className="stat-value" style={{ color: s.color }}>{s.value}</span>
          <span className="stat-sub">{s.sub}</span>
        </div>
      ))}
    </div>
  )
}
