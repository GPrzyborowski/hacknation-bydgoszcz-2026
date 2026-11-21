import { useEffect, useState } from 'react'
import { ApiError, STATUS_LABELS, STATUS_SHORT, listCases, listYears, type CaseItem, type CaseStatus, type Urgency } from '../lib/api'
import { formatIso } from '../lib/deadline'
import { navigate } from '../lib/router'

const URGENCY_LABEL: Partial<Record<Urgency, string>> = {
  overdue: 'po terminie',
  today: 'termin dziś',
  tomorrow: 'termin jutro',
  soon: 'termin w ciągu 3 dni',
}

function remaining(c: CaseItem): string {
  if (c.status === 'odpowiedz_wyslana') return c.answered_on_time === false ? 'po terminie' : '—'
  if (c.days_remaining === null) return '—'
  if (c.days_remaining < 0) return `${-c.days_remaining} po terminie`
  if (c.days_remaining === 0) return 'dziś'
  return String(c.days_remaining)
}

export function RegisterView() {
  const currentYear = new Date().getFullYear()
  const [years, setYears] = useState<number[]>([currentYear])
  const [year, setYear] = useState(currentYear)
  const [query, setQuery] = useState('')
  const [appliedQuery, setAppliedQuery] = useState('')
  const [cases, setCases] = useState<CaseItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<'' | 'w_toku' | CaseStatus>('')

  useEffect(() => {
    let alive = true
    listYears()
      .then((ys) => {
        if (!alive) return
        const all = Array.from(new Set([currentYear, ...ys])).sort((a, b) => b - a)
        setYears(all)
      })
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [currentYear])

  useEffect(() => {
    let alive = true
    listCases({ year, q: appliedQuery })
      .then((data) => {
        if (!alive) return
        setCases(data)
        setError(null)
      })
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : 'Nie udało się pobrać rejestru.'))
    return () => {
      alive = false
    }
  }, [year, appliedQuery])

  const open = cases?.filter((c) => c.status !== 'odpowiedz_wyslana') ?? []
  const shown =
    cases?.filter((c) =>
      statusFilter === '' ? true : statusFilter === 'w_toku' ? c.status !== 'odpowiedz_wyslana' : c.status === statusFilter,
    ) ?? null
  const urgent = open.filter((c) => c.urgency === 'overdue' || c.urgency === 'today' || c.urgency === 'tomorrow')

  return (
    <>
      <section className="intro">
        <h1>Rejestr wniosków</h1>
        <p className="lead">
          Wnioski od najstarszych. Podświetlone są sprawy z terminem dziś lub jutro oraz po terminie — te obsłuż w
          pierwszej kolejności.
        </p>
      </section>

      <form
        className="filters"
        onSubmit={(e) => {
          e.preventDefault()
          setAppliedQuery(query)
        }}
      >
        <div className="field">
          <label className="field-label small" htmlFor="year">
            Rok
          </label>
          <select id="year" className="input select num" value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>
        <div className="field grow">
          <label className="field-label small" htmlFor="search">
            Szukaj w sprawach i odpowiedziach
          </label>
          <input
            id="search"
            className="input"
            type="search"
            value={query}
            placeholder="np. uczniowie, Astoria, BKS.IV.1431.590"
            onChange={(e) => {
              setQuery(e.target.value)
              if (!e.target.value) setAppliedQuery('')
            }}
          />
        </div>
        <button type="submit" className="secondary-button">
          Szukaj
        </button>
        <div className="field">
          <label className="field-label small" htmlFor="status-filter">
            Etap
          </label>
          <select
            id="status-filter"
            className="input select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
          >
            <option value="">Wszystkie sprawy</option>
            <option value="w_toku">Tylko w toku</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </form>

      {cases && (
        <p className="register-summary" role="status">
          {cases.length === 0
            ? 'Brak spraw.'
            : `${cases.length} spraw · w toku ${open.length}${urgent.length ? ` · wymaga uwagi ${urgent.length}` : ''}`}
        </p>
      )}

      {error && (
        <div className="notice notice-error" role="alert">
          <p>
            <strong>Nie udało się pobrać rejestru.</strong> {error}
          </p>
        </div>
      )}

      {!cases && !error && <p className="field-hint">Wczytywanie rejestru…</p>}

      {cases && cases.length === 0 && (
        <div className="empty">
          <p>
            {appliedQuery
              ? 'Żadna sprawa nie pasuje do wyszukiwania.'
              : `W roku ${year} nie ma jeszcze spraw. Dodaj wniosek albo zaimportuj rejestr z Excela w Bazie wiedzy.`}
          </p>
          <a className="primary-button" href="#/">
            Dodaj wniosek
          </a>
        </div>
      )}

      {cases && cases.length > 0 && shown?.length === 0 && (
        <p className="register-summary">Żadna sprawa nie jest na wybranym etapie.</p>
      )}

      {shown && shown.length > 0 && (
        <div className="table-wrap">
          <table className="register">
            <thead>
              <tr>
                <th scope="col" className="num">Lp.</th>
                <th scope="col">Numer sprawy / osoba</th>
                <th scope="col">Wnioskodawca</th>
                <th scope="col">Przedmiot</th>
                <th scope="col">Data wpływu</th>
                <th scope="col">Termin</th>
                <th scope="col" className="num">Pozostało dni</th>
                <th scope="col">Data odpowiedzi</th>
                <th scope="col">Etap</th>
                <th scope="col">Wydziały</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((c, i) => (
                <tr
                  key={c.id}
                  className={`urgency-${c.urgency}`}
                  onClick={() => navigate({ name: 'case', id: c.id })}
                >
                  <td className="num">{c.ordinal ?? i + 1}</td>
                  <td className="nowrap">
                    <a className="num" href={`#/sprawa/${c.id}`} onClick={(e) => e.stopPropagation()}>
                      {c.case_number}
                    </a>
                    {c.initials && <span className="cell-note">{c.initials}</span>}
                  </td>
                  <td>{c.applicant || '—'}</td>
                  <td className="subject-cell">
                    {c.subject}
                    {c.date_parse_warning && (
                      <span className="cell-warning" title={c.date_parse_warning}>
                        Uwaga do dat: {c.date_parse_warning}
                      </span>
                    )}
                  </td>
                  <td className="num nowrap">{formatIso(c.received_date)}</td>
                  <td className="num nowrap">
                    {formatIso(c.deadline_date)}
                    {URGENCY_LABEL[c.urgency] && <span className="urgency-label">{URGENCY_LABEL[c.urgency]}</span>}
                    {c.extension_days > 0 && (
                      <span className="cell-note" title={`Pierwotny termin ${formatIso(c.original_deadline_date)}`}>
                        przedłużony +{c.extension_days} dni
                      </span>
                    )}
                  </td>
                  <td className="num">{remaining(c)}</td>
                  <td className="num nowrap">{formatIso(c.response_date)}</td>
                  <td>
                    <span className={`status status-${c.status}`} title={STATUS_LABELS[c.status]}>{STATUS_SHORT[c.status]}</span>
                  </td>
                  <td>
                    <DeptCell c={c} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function DeptCell({ c }: { c: CaseItem }) {
  if (c.dept_total === 0) return <span className="muted-cell">—</span>
  const done = c.dept_answered === c.dept_total
  return (
    <span className="dept-cell">
      <span className={`num${done ? ' dept-done' : ''}`}>
        {c.dept_answered}/{c.dept_total} odp.
      </span>
      {c.dept_waiting.length > 0 && <span className="cell-note">czekamy: {c.dept_waiting.join(', ')}</span>}
      {c.dept_clarification.length > 0 && (
        <span className="cell-note">uszczegółowienie: {c.dept_clarification.join(', ')}</span>
      )}
    </span>
  )
}
