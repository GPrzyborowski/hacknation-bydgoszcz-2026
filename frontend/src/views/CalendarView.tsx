import { useState } from 'react'
import { ErrorNotice, Notice } from '../components/Notice'
import { listCases, listNonWorkingDays, type CaseItem } from '../lib/api'
import { useConfig } from '../lib/config'
import { addDays, formatIso, formatMonth, formatWeekday, parseIso, toIso, todayIso } from '../lib/dates'
import { cx } from '../lib/dom'
import { STATUS_LABELS, STATUS_SHORT, inDaysText, isClosed, remainingLabel, shortCaseNumber } from '../lib/domain'
import { useQuery } from '../lib/hooks'
import { caseHref, navigate } from '../lib/router'

const WEEKDAYS = ['Pon', 'Wt', 'Śr', 'Czw', 'Pt', 'Sob', 'Nd']
const GRID_WEEKS = 6
const UPCOMING_LIMIT = 8
const VIEW_STORAGE_KEY = 'kalendarium.widok'

type CalendarMode = 'grid' | 'table'

const VIEW_MODES: { mode: CalendarMode; label: string }[] = [
  { mode: 'grid', label: 'Kalendarz' },
  { mode: 'table', label: 'Tabela' },
]

const savedMode = (): CalendarMode => (localStorage.getItem(VIEW_STORAGE_KEY) === 'table' ? 'table' : 'grid')

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
  const [mode, setMode] = useState<CalendarMode>(savedMode)
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

  const monthKey = toIso(month).slice(0, 7)
  const monthCases = (cases.data ?? [])
    .filter((item) => item.deadline_date?.startsWith(monthKey))
    .toSorted((a, b) => (a.deadline_date ?? '').localeCompare(b.deadline_date ?? '') || a.id - b.id)

  const switchMode = (next: CalendarMode) => {
    setMode(next)
    localStorage.setItem(VIEW_STORAGE_KEY, next)
  }
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
        <div className="view-switch" role="group" aria-label="Widok kalendarium">
          {VIEW_MODES.map((option) => (
            <button
              key={option.mode}
              type="button"
              className={cx('view-switch-option', mode === option.mode && 'is-active')}
              aria-pressed={mode === option.mode}
              onClick={() => switchMode(option.mode)}
            >
              {option.label}
            </button>
          ))}
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

      {mode === 'grid' ? (
        <MonthGrid month={month} days={days} today={today} nonWorking={nonWorking} byDeadline={byDeadline} prefix={case_number_prefix} />
      ) : (
        <DeadlineTable cases={monthCases} monthLabel={monthLabel} today={today} nonWorking={nonWorking} loading={!cases.data} />
      )}

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

type GridProps = {
  month: Date
  days: Date[]
  today: string
  nonWorking: Set<string>
  byDeadline: Map<string, CaseItem[]>
  prefix: string
}

function MonthGrid({ month, days, today, nonWorking, byDeadline, prefix }: GridProps) {
  return (
  <table className="calendar">
    <caption className="visually-hidden">Terminy odpowiedzi — {formatMonth(month)}</caption>
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
                        <span className="num">{shortCaseNumber(item.case_number, prefix)}</span>
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
  )
}

type TableProps = { cases: CaseItem[]; monthLabel: string; today: string; nonWorking: Set<string>; loading: boolean }

/** Terminy wybranego miesiąca w kolejności od najwcześniejszego — z tymi samymi oznaczeniami pilności co rejestr. */
function DeadlineTable({ cases, monthLabel, today, nonWorking, loading }: TableProps) {
  if (loading) return <p className="field-hint cal-table-empty">Wczytywanie…</p>
  if (cases.length === 0) return <p className="field-hint cal-table-empty">Brak terminów w miesiącu: {monthLabel}.</p>

  return (
    <div className="table-wrap">
      <table className="data-table is-clickable">
        <caption className="visually-hidden">Terminy odpowiedzi — {monthLabel}</caption>
        <thead>
          <tr>
            <th scope="col">Termin</th>
            <th scope="col">Pozostało dni</th>
            <th scope="col">Numer sprawy</th>
            <th scope="col">Przedmiot</th>
            <th scope="col">Wnioskodawca</th>
            <th scope="col">Etap</th>
            <th scope="col">Wydziały</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((item) => {
            const deadline = item.deadline_date ?? ''
            const day = parseIso(deadline)
            return (
              <tr key={item.id} className={`urgency-${item.urgency}`} onClick={() => navigate({ name: 'case', id: item.id })}>
                <td className="nowrap">
                  <strong className="num">{formatIso(deadline)}</strong>
                  {day && (
                    <span className="cell-note">
                      {formatWeekday(day)}
                      {deadline === today && ' · dziś'}
                      {nonWorking.has(deadline) && ' · dzień wolny'}
                    </span>
                  )}
                </td>
                <td className="num">{remainingLabel(item)}</td>
                <td className="nowrap">
                  <a className="num" href={caseHref(item.id)} onClick={(event) => event.stopPropagation()}>
                    {item.case_number}
                  </a>
                </td>
                <td className="subject-cell">{item.subject}</td>
                <td>{item.applicant || '—'}</td>
                <td>
                  <span className={isClosed(item.status) ? 'tag is-success' : 'tag'} title={STATUS_LABELS[item.status]}>
                    {STATUS_SHORT[item.status]}
                  </span>
                </td>
                <td className="num nowrap">{item.dept_total > 0 ? `${item.dept_answered}/${item.dept_total} odp.` : '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
