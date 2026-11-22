import { useState } from 'react'
import { ErrorNotice, Notice } from '../components/Notice'
import { listCases, listNonWorkingDays, type CaseItem } from '../lib/api'
import { useConfig } from '../lib/config'
import { addDays, formatIso, formatMonth, toIso, todayIso } from '../lib/dates'
import { cx } from '../lib/dom'
import { STATUS_SHORT, inDaysText, isClosed, shortCaseNumber } from '../lib/domain'
import { useQuery } from '../lib/hooks'
import { caseHref } from '../lib/router'

const WEEKDAYS = ['Pon', 'Wt', 'Śr', 'Czw', 'Pt', 'Sob', 'Nd']
const GRID_WEEKS = 6
const UPCOMING_LIMIT = 8

const firstOfMonth = (day: Date) => new Date(day.getFullYear(), day.getMonth(), 1)

/** Siatka miesiąca od poniedziałku — zawsze 6 pełnych tygodni, żeby wysokość kalendarza się nie zmieniała. */
function monthGrid(month: Date): Date[] {
  const start = addDays(month, -((month.getDay() + 6) % 7))
  return Array.from({ length: GRID_WEEKS * 7 }, (_, index) => addDays(start, index))
}

function groupByDeadline(cases: CaseItem[]): Map<string, CaseItem[]> {
  const groups = new Map<string, CaseItem[]>()
  for (const item of cases) {
    if (item.deadline_date) groups.set(item.deadline_date, [...(groups.get(item.deadline_date) ?? []), item])
  }
  return groups
}

export function CalendarView() {
  const { case_number_prefix } = useConfig()
  const today = todayIso()
  const [month, setMonth] = useState(() => firstOfMonth(new Date()))
  const [openOnly, setOpenOnly] = useState(true)
  const cases = useQuery(() => listCases({ openOnly }), openOnly)

  const days = monthGrid(month)
  const gridStart = toIso(days[0])
  const gridEnd = toIso(days[days.length - 1])
  const freeDays = useQuery(() => listNonWorkingDays(gridStart, gridEnd), gridStart)
  const nonWorking = new Set(freeDays.data)
  const byDeadline = groupByDeadline(cases.data ?? [])

  const open = (cases.data ?? []).filter((item) => !isClosed(item.status))
  const overdue = open.filter((item) => item.urgency === 'overdue')
  const upcoming = open
    .filter((item) => item.deadline_date && item.urgency !== 'overdue')
    .toSorted((a, b) => (a.deadline_date ?? '').localeCompare(b.deadline_date ?? ''))
    .slice(0, UPCOMING_LIMIT)

  const moveMonth = (delta: number) => setMonth((current) => new Date(current.getFullYear(), current.getMonth() + delta, 1))
  const monthLabel = formatMonth(month)

  return (
    <>
      <section className="intro">
        <h1>Kalendarium terminów</h1>
        <p className="lead">Terminy odpowiedzi na wnioski. Podświetlone są sprawy z terminem dziś i jutro oraz po terminie.</p>
      </section>

      {cases.error && <ErrorNotice title="Nie udało się pobrać spraw." message={cases.error} />}

      {overdue.length > 0 && (
        <Notice tone="error" title={`Po terminie: ${overdue.length}`}>
          <p>
            {overdue.map((item, index) => (
              <span key={item.id}>
                {index > 0 && ', '}
                <a href={caseHref(item.id)} className="num">
                  {item.case_number}
                </a>{' '}
                (termin {formatIso(item.deadline_date)})
              </span>
            ))}
          </p>
        </Notice>
      )}

      <div className="cal-toolbar">
        <div className="cal-nav">
          <button type="button" className="secondary-button" onClick={() => moveMonth(-1)}>
            Poprzedni miesiąc
          </button>
          <h2 className="cal-month" aria-live="polite">
            {monthLabel}
          </h2>
          <button type="button" className="secondary-button" onClick={() => moveMonth(1)}>
            Następny miesiąc
          </button>
          <button type="button" className="link-button" onClick={() => setMonth(firstOfMonth(new Date()))}>
            Dziś
          </button>
        </div>
        <label className="choice">
          <input type="checkbox" checked={openOnly} onChange={(event) => setOpenOnly(event.target.checked)} />
          <span>Tylko sprawy w toku</span>
        </label>
      </div>

      <div className="cal-legend" aria-hidden="true">
        <span className="cal-key urgency-overdue">po terminie</span>
        <span className="cal-key urgency-today">termin dziś / jutro</span>
        <span className="cal-key">w toku</span>
        <span className="cal-key is-done">zakończona</span>
        <span className="cal-key is-free">dzień wolny</span>
      </div>

      <table className="calendar">
        <caption className="visually-hidden">Terminy odpowiedzi — {monthLabel}</caption>
        <thead>
          <tr>
            {WEEKDAYS.map((weekday) => (
              <th key={weekday} scope="col">
                {weekday}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: GRID_WEEKS }, (_, week) => (
            <tr key={week}>
              {days.slice(week * 7, week * 7 + 7).map((day) => {
                const iso = toIso(day)
                const isToday = iso === today
                return (
                  <td
                    key={iso}
                    className={cx(
                      'cal-day',
                      day.getMonth() !== month.getMonth() && 'is-outside',
                      isToday && 'is-today',
                      nonWorking.has(iso) && 'is-free',
                    )}
                  >
                    <span className="cal-date num">
                      {day.getDate()}
                      {isToday && <span className="visually-hidden"> (dziś)</span>}
                    </span>
                    <ul className="cal-items">
                      {(byDeadline.get(iso) ?? []).map((item) => (
                        <li key={item.id}>
                          <a
                            href={caseHref(item.id)}
                            className={`cal-item urgency-${item.urgency}`}
                            title={`${item.case_number} — ${item.subject} (${STATUS_SHORT[item.status]})`}
                          >
                            <span className="num">{shortCaseNumber(item.case_number, case_number_prefix)}</span>
                            <span className="cal-item-subject">{item.subject}</span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>

      <section className="panel" aria-labelledby="upcoming-heading">
        <h2 id="upcoming-heading" className="panel-title">
          Najbliższe terminy
        </h2>
        {!cases.data ? (
          <p className="field-hint">Wczytywanie…</p>
        ) : upcoming.length === 0 ? (
          <p className="field-hint">Brak spraw w toku z nadchodzącym terminem.</p>
        ) : (
          <ul className="doc-list">
            {upcoming.map((item) => (
              <li key={item.id} className={`upcoming urgency-${item.urgency}`}>
                <span className="num upcoming-date">{formatIso(item.deadline_date)}</span>
                <a href={caseHref(item.id)} className="num">
                  {item.case_number}
                </a>
                <span>{item.subject}</span>
                <span className="meta">
                  {inDaysText(item.days_remaining ?? 0)} · {STATUS_SHORT[item.status]}
                  {item.dept_total > 0 && ` · wydziały ${item.dept_answered}/${item.dept_total}`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
