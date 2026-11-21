import { useEffect, useMemo, useState } from 'react'
import { ApiError, STATUS_SHORT, listCases, type CaseItem } from '../lib/api'
import { addDays, formatIso, isNonWorkingDay, parseIso, todayIso } from '../lib/deadline'

const WEEKDAYS = ['Pon', 'Wt', 'Śr', 'Czw', 'Pt', 'Sob', 'Nd']
const monthName = new Intl.DateTimeFormat('pl-PL', { month: 'long', year: 'numeric' })

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

/** Siatka miesiąca od poniedziałku, 6 tygodni. */
function monthGrid(year: number, month: number): Date[] {
  const first = new Date(year, month, 1)
  const offset = (first.getDay() + 6) % 7
  const start = addDays(first, -offset)
  return Array.from({ length: 42 }, (_, i) => addDays(start, i))
}

export function CalendarView() {
  const today = todayIso()
  const now = parseIso(today)!
  const [cursor, setCursor] = useState({ year: now.getFullYear(), month: now.getMonth() })
  const [cases, setCases] = useState<CaseItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [onlyOpen, setOnlyOpen] = useState(true)

  useEffect(() => {
    let alive = true
    listCases({})
      .then((data) => alive && setCases(data))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : 'Nie udało się pobrać spraw.'))
    return () => {
      alive = false
    }
  }, [])

  const byDay = useMemo(() => {
    const map = new Map<string, CaseItem[]>()
    for (const c of cases ?? []) {
      if (!c.deadline_date) continue
      if (onlyOpen && c.status === 'odpowiedz_wyslana') continue
      const list = map.get(c.deadline_date) ?? []
      list.push(c)
      map.set(c.deadline_date, list)
    }
    return map
  }, [cases, onlyOpen])

  const days = monthGrid(cursor.year, cursor.month)
  const move = (delta: number) =>
    setCursor(({ year, month }) => {
      const d = new Date(year, month + delta, 1)
      return { year: d.getFullYear(), month: d.getMonth() }
    })

  const open = (cases ?? []).filter((c) => c.status !== 'odpowiedz_wyslana')
  const overdue = open.filter((c) => c.urgency === 'overdue')
  const upcoming = open
    .filter((c) => c.deadline_date && c.urgency !== 'overdue')
    .sort((a, b) => (a.deadline_date ?? '').localeCompare(b.deadline_date ?? ''))
    .slice(0, 8)

  return (
    <>
      <section className="intro">
        <h1>Kalendarium terminów</h1>
        <p className="lead">
          Terminy odpowiedzi na wnioski. Podświetlone są sprawy z terminem dziś i jutro oraz po terminie.
        </p>
      </section>

      {error && (
        <div className="notice notice-error" role="alert">
          <p>
            <strong>Nie udało się pobrać spraw.</strong> {error}
          </p>
        </div>
      )}

      {overdue.length > 0 && (
        <div className="notice notice-error">
          <strong>Po terminie: {overdue.length}</strong>
          <p>
            {overdue.map((c, i) => (
              <span key={c.id}>
                {i > 0 && ', '}
                <a href={`#/sprawa/${c.id}`} className="num">
                  {c.case_number}
                </a>{' '}
                (termin {formatIso(c.deadline_date)})
              </span>
            ))}
          </p>
        </div>
      )}

      <div className="cal-toolbar">
        <div className="cal-nav">
          <button type="button" className="secondary-button" onClick={() => move(-1)}>
            Poprzedni miesiąc
          </button>
          <h2 className="cal-month" aria-live="polite">
            {monthName.format(new Date(cursor.year, cursor.month, 1))}
          </h2>
          <button type="button" className="secondary-button" onClick={() => move(1)}>
            Następny miesiąc
          </button>
          <button
            type="button"
            className="link-button"
            onClick={() => setCursor({ year: now.getFullYear(), month: now.getMonth() })}
          >
            Dziś
          </button>
        </div>
        <label className="choice">
          <input type="checkbox" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} />
          <span>Tylko sprawy w toku</span>
        </label>
      </div>

      <div className="cal-legend" aria-hidden="true">
        <span className="cal-key key-overdue">po terminie</span>
        <span className="cal-key key-today">termin dziś / jutro</span>
        <span className="cal-key key-normal">w toku</span>
        <span className="cal-key key-done">zakończona</span>
        <span className="cal-key key-free">dzień wolny</span>
      </div>

      <table className="calendar">
        <caption className="visually-hidden">Terminy odpowiedzi — {monthName.format(new Date(cursor.year, cursor.month, 1))}</caption>
        <thead>
          <tr>
            {WEEKDAYS.map((d) => (
              <th key={d} scope="col">
                {d}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: 6 }, (_, w) => (
            <tr key={w}>
              {days.slice(w * 7, w * 7 + 7).map((d) => {
                const key = iso(d)
                const items = byDay.get(key) ?? []
                const inMonth = d.getMonth() === cursor.month
                const isToday = key === today
                const cls = [
                  'cal-day',
                  inMonth ? '' : 'is-outside',
                  isToday ? 'is-today' : '',
                  isNonWorkingDay(d) ? 'is-free' : '',
                ]
                  .filter(Boolean)
                  .join(' ')
                return (
                  <td key={key} className={cls}>
                    <span className="cal-date num">
                      {d.getDate()}
                      {isToday && <span className="visually-hidden"> (dziś)</span>}
                    </span>
                    <ul className="cal-items">
                      {items.map((c) => (
                        <li key={c.id}>
                          <a
                            href={`#/sprawa/${c.id}`}
                            className={`cal-item urgency-${c.urgency}`}
                            title={`${c.case_number} — ${c.subject} (${STATUS_SHORT[c.status]})`}
                          >
                            <span className="num">{c.case_number.replace('BKS.IV.1431.', '')}</span>
                            <span className="cal-item-subject">{c.subject}</span>
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
        {!cases ? (
          <p className="field-hint">Wczytywanie…</p>
        ) : upcoming.length === 0 ? (
          <p className="field-hint">Brak spraw w toku z nadchodzącym terminem.</p>
        ) : (
          <ul className="doc-list">
            {upcoming.map((c) => (
              <li key={c.id} className={`upcoming urgency-${c.urgency}`}>
                <span className="num upcoming-date">{formatIso(c.deadline_date)}</span>
                <a href={`#/sprawa/${c.id}`} className="num">
                  {c.case_number}
                </a>
                <span>{c.subject}</span>
                <span className="similar-meta">
                  {c.days_remaining === 0 ? 'dziś' : `za ${c.days_remaining} dni`} · {STATUS_SHORT[c.status]}
                  {c.dept_total > 0 && ` · wydziały ${c.dept_answered}/${c.dept_total}`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
