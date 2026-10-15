/**
 * components/CityMap.jsx
 * ───────────────────────
 * Pure-SVG 2D city grid map. No paid APIs required.
 *
 * Renders:
 *  • Grid lines        – subtle background reference lines
 *  • Route polylines   – dashed lines connecting active task waypoints
 *  • Bin circles       – colour-coded by capacity percentage
 *  • Truck markers     – small rectangles colour-coded by status
 *  • Tooltips          – native SVG <title> on hover
 *
 * Coordinate normalisation:
 *  Lat/Lng → SVG (x, y):
 *    x = (lng - minLng) / (maxLng - minLng) * usableW + PAD
 *    y = (1 - (lat - minLat) / (maxLat - minLat)) * usableH + PAD
 *  Y is inverted because SVG y grows downward, latitude grows upward.
 */

const SVG_W  = 900
const SVG_H  = 480
const PAD    = 44

// Route colours per truck (cycles if > 4 active tasks)
const ROUTE_COLOURS = ['#58a6ff', '#f8934f', '#4ff89e', '#bc8cff', '#f84f9e']

function capColour(pct) {
  if (pct >= 90) return '#f85149'
  if (pct >= 75) return '#db6d28'
  if (pct >= 50) return '#d29922'
  return '#3fb950'
}

function truckColour(status) {
  if (status === 'idle')           return '#3fb950'
  if (status === 'en_route')       return '#58a6ff'
  if (status === 'out_of_service') return '#f85149'
  return '#8b949e'
}

function useCoordNorm(bins, trucks) {
  const allLats = [
    ...(bins   || []).map(b => b.latitude),
    ...(trucks || []).filter(t => t.current_gps_location).map(t => {
      const [la] = t.current_gps_location.split(',').map(Number)
      return la
    }),
  ]
  const allLngs = [
    ...(bins   || []).map(b => b.longitude),
    ...(trucks || []).filter(t => t.current_gps_location).map(t => {
      const [, lo] = t.current_gps_location.split(',').map(Number)
      return lo
    }),
  ]

  if (allLats.length === 0) return null

  const minLat = Math.min(...allLats)
  const maxLat = Math.max(...allLats)
  const minLng = Math.min(...allLngs)
  const maxLng = Math.max(...allLngs)

  const latRange = maxLat - minLat || 0.01
  const lngRange = maxLng - minLng || 0.01

  return (lat, lng) => ({
    x: PAD + ((lng - minLng) / lngRange) * (SVG_W - 2 * PAD),
    y: SVG_H - PAD - ((lat - minLat) / latRange) * (SVG_H - 2 * PAD),
  })
}

export default function CityMap({ bins = [], trucks = [], tasks = [] }) {
  const norm = useCoordNorm(bins, trucks)

  const activeTasks = tasks.filter(t => t.status === 'active')

  // Grid lines
  const gridLines = []
  const GRID_COUNT = 6
  for (let i = 0; i <= GRID_COUNT; i++) {
    const x = PAD + (i / GRID_COUNT) * (SVG_W - 2 * PAD)
    const y = PAD + (i / GRID_COUNT) * (SVG_H - 2 * PAD)
    gridLines.push(
      <line key={`gx${i}`} x1={x} y1={PAD} x2={x} y2={SVG_H - PAD}
        stroke="#1e2530" strokeWidth="1" />,
      <line key={`gy${i}`} x1={PAD} y1={y} x2={SVG_W - PAD} y2={y}
        stroke="#1e2530" strokeWidth="1" />,
    )
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">🗺️ City Grid Map</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          Auto-normalized · {bins.length} bins · {trucks.length} trucks
        </span>
      </div>

      <div className="city-map-wrap">
        <svg viewBox={`0 0 ${SVG_W} ${SVG_H}`} xmlns="http://www.w3.org/2000/svg">
          {/* Background */}
          <rect width={SVG_W} height={SVG_H} fill="#0a0e14" />

          {/* Grid */}
          {gridLines}

          {/* Route polylines for active tasks */}
          {norm && activeTasks.map((task, ti) => {
            const colour = ROUTE_COLOURS[ti % ROUTE_COLOURS.length]
            const pts = (task.waypoints || []).map(wp => {
              const { x, y } = norm(wp.latitude, wp.longitude)
              return `${x},${y}`
            }).join(' ')
            return pts ? (
              <polyline
                key={task.id}
                points={pts}
                fill="none"
                stroke={colour}
                strokeWidth="2"
                strokeDasharray="7,4"
                strokeOpacity="0.7"
              />
            ) : null
          })}

          {/* Waypoint sequence numbers */}
          {norm && activeTasks.map((task, ti) => {
            const colour = ROUTE_COLOURS[ti % ROUTE_COLOURS.length]
            return (task.waypoints || []).map((wp, wi) => {
              const { x, y } = norm(wp.latitude, wp.longitude)
              return (
                <text key={`${task.id}-${wi}`}
                  x={x} y={y - 13}
                  textAnchor="middle"
                  fontSize="9"
                  fill={colour}
                  fontWeight="700"
                >
                  {wi + 1}
                </text>
              )
            })
          })}

          {/* Bin circles */}
          {norm && bins.map(bin => {
            const { x, y } = norm(bin.latitude, bin.longitude)
            const r = 9
            const col = capColour(bin.current_capacity_pct)
            return (
              <g key={bin.id}>
                <circle cx={x} cy={y} r={r + 3} fill={col} fillOpacity="0.12" />
                <circle cx={x} cy={y} r={r} fill={col} fillOpacity="0.85" stroke="#0a0e14" strokeWidth="1.5" />
                <text x={x} y={y + 3.5} textAnchor="middle" fontSize="8" fill="#000" fontWeight="700">
                  {Math.round(bin.current_capacity_pct)}
                </text>
                <title>
                  {`Bin #${bin.id}: ${bin.location_name}\nCapacity: ${bin.current_capacity_pct.toFixed(1)}%`}
                </title>
              </g>
            )
          })}

          {/* Truck markers */}
          {norm && trucks.map(truck => {
            if (!truck.current_gps_location) return null
            const [lat, lng] = truck.current_gps_location.split(',').map(Number)
            const { x, y } = norm(lat, lng)
            const col = truckColour(truck.status)
            return (
              <g key={truck.id}>
                <rect
                  x={x - 10} y={y - 8}
                  width={20} height={14}
                  rx="3"
                  fill={col}
                  fillOpacity="0.9"
                  stroke="#0a0e14"
                  strokeWidth="1.5"
                />
                <text x={x} y={y + 3} textAnchor="middle" fontSize="8" fill="#000" fontWeight="700">
                  🚛
                </text>
                <title>
                  {`Truck ${truck.plate_number}\nStatus: ${truck.status}\nGPS: ${truck.current_gps_location}`}
                </title>
              </g>
            )
          })}

          {/* Axis labels */}
          <text x={SVG_W / 2} y={SVG_H - 6} textAnchor="middle" fontSize="10" fill="#30363d">
            Longitude →
          </text>
          <text x={10} y={SVG_H / 2} textAnchor="middle" fontSize="10" fill="#30363d"
            transform={`rotate(-90, 10, ${SVG_H / 2})`}>
            Latitude →
          </text>
        </svg>
      </div>

      {/* Legend */}
      <div className="map-legend">
        <span className="legend-item">
          <span className="legend-dot" style={{ background: '#3fb950' }} /> Bin &lt;50%
        </span>
        <span className="legend-item">
          <span className="legend-dot" style={{ background: '#d29922' }} /> Bin 50–75%
        </span>
        <span className="legend-item">
          <span className="legend-dot" style={{ background: '#db6d28' }} /> Bin 75–90%
        </span>
        <span className="legend-item">
          <span className="legend-dot" style={{ background: '#f85149' }} /> Bin ≥90%
        </span>
        <span className="legend-item" style={{ marginLeft: 8 }}>
          <span className="legend-sq" style={{ background: '#3fb950' }} /> Idle
        </span>
        <span className="legend-item">
          <span className="legend-sq" style={{ background: '#58a6ff' }} /> En Route
        </span>
        <span className="legend-item">
          <span className="legend-sq" style={{ background: '#f85149' }} /> OOS
        </span>
        <span className="legend-item" style={{ marginLeft: 8 }}>
          <span style={{ borderTop: '2px dashed #58a6ff', width: 20, display: 'inline-block' }} /> Route
        </span>
      </div>
    </div>
  )
}
