import { useState, type FormEvent } from 'react'
import { ErrorNotice } from '../components/Notice'
import { listCases, listYears, type CaseItem, type CaseStatus } from '../lib/api'
import { useConfig } from '../lib/config'
import { formatIso } from '../lib/dates'
import { STATUS_LABELS, STATUS_SHORT, isClosed, isUrgent, remainingLabel, urgencyLabel } from '../lib/domain'
import { useQuery } from '../lib/hooks'
import { caseHref, hrefFor, navigate } from '../lib/router'

type StageFilter = '' | 'w_toku' | CaseStatus

const matchesStage = (item: CaseItem, stage: StageFilter) =>
  stage === '' || (stage === 'w_toku' ? !isClosed(item.status) : item.status === stage)

export function RegisterView() {
  const { soon_days, case_number_prefix } = useConfig()
  const currentYear = new Date().getFullYear()
  const [year, setYear] = useState(currentYear)
  const [query, setQuery] = useState('')
  const [appliedQuery, setAppliedQuery] = useState('')
  const [stage, setStage] = useState<StageFilter>('')
  const years = useQuery(listYears)
  const cases = useQuery(() => listCases({ year, query: appliedQuery }), `${year}|${appliedQuery}`)

  const yearOptions = [...new Set([currentYear, ...(years.data ?? [])])].sort((a, b) => b - a)
  const all = cases.data
  const open = all?.filter((item) => !isClosed(item.status)) ?? []
  const urgentCount = open.filter((item) => isUrgent(item.urgency)).length
  const shown = all?.filter((item) => matchesStage(item, stage)) ?? []

  const search = (event: FormEvent) => {
    event.preventDefault()
    setAppliedQuery(query)
  }

  return (
    <>
      <section className="intro">
        <h1>Rejestr wniosków</h1>
        <p className="lead">
          Wnioski od najstarszych. Podświetlone są sprawy z terminem dziś lub jutro oraz po terminie — te obsłuż w pierwszej
          kolejności.
        </p>
      </section>

      <form className="filters" onSubmit={search}>
        <div className="field">
          <label className="field-label small" htmlFor="register-year">
            Rok
          </label>
          <select
            id="register-year"
            className="input select num"
            value={year}
            onChange={(event) => setYear(Number(event.target.value))}
          >
            {yearOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
        <div className="field grow">
          <label className="field-label small" htmlFor="register-search">
            Szukaj w sprawach i odpowiedziach
          </label>
          <input
            id="register-search"
            className="input"
            type="search"
            value={query}
            placeholder={`np. uczniowie, Astoria, ${case_number_prefix}.590`}
            onChange={(event) => {
              setQuery(event.target.value)
              if (!event.target.value) setAppliedQuery('')
            }}
          />
        </div>
        <button type="submit" className="secondary-button">
          Szukaj
        </button>
        <div className="field">
          <label className="field-label small" htmlFor="register-stage">
            Etap
          </label>
          <select
            id="register-stage"
            className="input select"
            value={stage}
            onChange={(event) => setStage(event.target.value as StageFilter)}
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

      {all && (
        <p className="register-summary" role="status">
          {all.length === 0
            ? 'Brak spraw.'
            : `${all.length} spraw · w toku ${open.length}${urgentCount ? ` · wymaga uwagi ${urgentCount}` : ''}`}
        </p>
      )}

      {cases.error && <ErrorNotice title="Nie udało się pobrać rejestru." message={cases.error} />}
      {!all && !cases.error && <p className="field-hint">Wczytywanie rejestru…</p>}

      {all?.length === 0 && (
        <div className="empty">
          <p>
            {appliedQuery
              ? 'Żadna sprawa nie pasuje do wyszukiwania.'
              : `W roku ${year} nie ma jeszcze spraw. Dodaj wniosek albo zaimportuj rejestr z Excela w Bazie wiedzy.`}
          </p>
          <a className="primary-button" href={hrefFor({ name: 'intake' })}>
            Dodaj wniosek
          </a>
        </div>
      )}

      {all && all.length > 0 && shown.length === 0 && (
        <p className="register-summary">Żadna sprawa nie jest na wybranym etapie.</p>
      )}

      {shown.length > 0 && (
        <div className="table-wrap">
          <table className="data-table is-clickable">
            <thead>
              <tr>
                <th scope="col" className="num">
                  Lp.
                </th>
                <th scope="col">Numer sprawy / osoba</th>
                <th scope="col">Wnioskodawca</th>
                <th scope="col">Przedmiot</th>
                <th scope="col">Data wpływu</th>
                <th scope="col">Termin</th>
                <th scope="col" className="num">
                  Pozostało dni
                </th>
                <th scope="col">Data odpowiedzi</th>
                <th scope="col">Etap</th>
                <th scope="col">Wydziały</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((item, index) => {
                const label = urgencyLabel(item.urgency, soon_days)
                return (
                  <tr key={item.id} className={`urgency-${item.urgency}`} onClick={() => navigate({ name: 'case', id: item.id })}>
                    <td className="num">{item.ordinal ?? index + 1}</td>
                    <td className="nowrap">
                      <a className="num" href={caseHref(item.id)} onClick={(event) => event.stopPropagation()}>
                        {item.case_number}
                      </a>
                      {item.initials && <span className="cell-note">{item.initials}</span>}
                    </td>
                    <td>{item.applicant || '—'}</td>
                    <td className="subject-cell">
                      {item.subject}
                      {item.date_parse_warning && (
                        <span className="cell-warning" title={item.date_parse_warning}>
                          Uwaga do dat: {item.date_parse_warning}
                        </span>
                      )}
                    </td>
                    <td className="num nowrap">{formatIso(item.received_date)}</td>
                    <td className="num nowrap">
                      {formatIso(item.deadline_date)}
                      {label && <span className="urgency-label">{label}</span>}
                      {item.extension_days > 0 && (
                        <span className="cell-note" title={`Pierwotny termin ${formatIso(item.original_deadline_date)}`}>
                          przedłużony +{item.extension_days} dni
                        </span>
                      )}
                    </td>
                    <td className="num">{remainingLabel(item)}</td>
                    <td className="num nowrap">{formatIso(item.response_date)}</td>
                    <td>
                      <span className={isClosed(item.status) ? 'tag is-success' : 'tag'} title={STATUS_LABELS[item.status]}>
                        {STATUS_SHORT[item.status]}
                      </span>
                    </td>
                    <td>
                      <DepartmentsCell item={item} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function DepartmentsCell({ item }: { item: CaseItem }) {
  if (item.dept_total === 0) return <span className="muted-cell">—</span>
  const allAnswered = item.dept_answered === item.dept_total
  return (
    <span className="dept-cell">
      <span className={allAnswered ? 'num dept-done' : 'num'}>
        {item.dept_answered}/{item.dept_total} odp.
      </span>
      {item.dept_waiting.length > 0 && <span className="cell-note">czekamy: {item.dept_waiting.join(', ')}</span>}
      {item.dept_clarification.length > 0 && (
        <span className="cell-note">uszczegółowienie: {item.dept_clarification.join(', ')}</span>
      )}
    </span>
  )
}
