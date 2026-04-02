import type { DayAvailability, DayStatus } from '../types'
import { getCalendarWeeks, toISODate } from '../lib/calendar'

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function statusMap(days: DayAvailability[]): Map<string, DayStatus | null> {
  const m = new Map<string, DayStatus | null>()
  for (const d of days) {
    m.set(d.day, d.status)
  }
  return m
}

function cellClass(status: DayStatus | null | undefined): string {
  if (status == null) return 'cal-cell cal-none'
  return `cal-cell cal-${status}`
}

type Props = {
  year: number
  month: number
  days: DayAvailability[]
}

export function MonthCalendar({ year, month, days }: Props) {
  const map = statusMap(days)
  const weeks = getCalendarWeeks(year, month)
  const title = new Date(year, month - 1, 1).toLocaleString(undefined, {
    month: 'long',
    year: 'numeric',
  })

  return (
    <div className="month-cal">
      <div className="month-cal-title">{title}</div>
      <div className="month-cal-grid" role="grid" aria-label={`Availability for ${title}`}>
        <div className="month-cal-row month-cal-head" role="row">
          {WEEKDAYS.map((d) => (
            <div key={d} className="month-cal-cell month-cal-dow" role="columnheader">
              {d}
            </div>
          ))}
        </div>
        {weeks.map((week, wi) => (
          <div key={wi} className="month-cal-row" role="row">
            {week.map((cell, ci) => {
              if (!cell) {
                return <div key={`e-${wi}-${ci}`} className="month-cal-cell month-cal-empty" />
              }
              const iso = toISODate(cell)
              const st = map.get(iso) ?? null
              return (
                <div
                  key={iso}
                  className={`month-cal-cell ${cellClass(st)}`}
                  role="gridcell"
                  title={iso}
                >
                  <span className="month-cal-daynum">{cell.getDate()}</span>
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
