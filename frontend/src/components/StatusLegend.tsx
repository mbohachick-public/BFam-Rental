const ITEMS: { status: string; label: string }[] = [
  { status: 'open_for_booking', label: 'Open for booking' },
  { status: 'booked', label: 'Booked' },
  { status: 'out_for_use', label: 'Out for use' },
  { status: 'readying_for_use', label: 'Readying for use' },
  { status: 'none', label: 'No data' },
]

export function StatusLegend() {
  return (
    <ul className="legend" aria-label="Availability legend">
      {ITEMS.map(({ status, label }) => (
        <li key={status} className="legend-item">
          <span className={`legend-swatch cal-cell cal-${status}`} aria-hidden />
          <span>{label}</span>
        </li>
      ))}
    </ul>
  )
}
