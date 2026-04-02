/** Local calendar grid: Sunday-first weeks. */
export function getCalendarWeeks(year: number, month: number): (Date | null)[][] {
  const first = new Date(year, month - 1, 1)
  const last = new Date(year, month, 0)
  const pad = first.getDay()
  const daysInMonth = last.getDate()
  const cells: (Date | null)[] = []
  for (let i = 0; i < pad; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push(new Date(year, month - 1, d))
  }
  while (cells.length % 7 !== 0) cells.push(null)
  const weeks: (Date | null)[][] = []
  for (let i = 0; i < cells.length; i += 7) {
    weeks.push(cells.slice(i, i + 7))
  }
  return weeks
}

export function toISODate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function firstOfMonth(year: number, month: number): string {
  return toISODate(new Date(year, month - 1, 1))
}

export function lastOfMonth(year: number, month: number): string {
  return toISODate(new Date(year, month, 0))
}

/** ISO date strings for each day in the month. */
export function iterDaysInMonth(year: number, month: number): string[] {
  const last = new Date(year, month, 0).getDate()
  const out: string[] = []
  for (let d = 1; d <= last; d++) {
    out.push(toISODate(new Date(year, month - 1, d)))
  }
  return out
}
