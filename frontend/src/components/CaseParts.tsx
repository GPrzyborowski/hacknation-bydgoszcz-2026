import { useState } from 'react'
import {
  ApiError,
  addCaseDepartment,
  createLetter,
  requestClarification,
  setDepartmentStatus,
  type CaseDetail,
  type Department,
  type DepartmentStatus,
  type DraftResult,
} from '../lib/api'
import { formatIso, parseIso, todayIso } from '../lib/deadline'

const errorText = (err: unknown) => (err instanceof ApiError || err instanceof Error ? err.message : 'Nieznany błąd.')

// --- Etapy sprawy (wg opisu wyzwania: a) brak działań … e) odpowiedź wysłana) -------------------

const STAGES = [
  { label: 'Brak działań', statuses: ['brak_dzialan'] },
  { label: 'Zapytania do wydziałów', statuses: ['zapytania_wyslane', 'kwerenda', 'doprecyzowanie'] },
  { label: 'Odpowiedź w przygotowaniu', statuses: ['odpowiedz_w_przygotowaniu'] },
  { label: 'Przygotowana odpowiedź', statuses: ['przygotowana_odpowiedz'] },
  { label: 'Odpowiedź wysłana', statuses: ['odpowiedz_wyslana'] },
]

export function StageTracker({ data }: { data: CaseDetail }) {
  const current = Math.max(0, STAGES.findIndex((s) => s.statuses.includes(data.status)))
  const flag =
    data.status === 'kwerenda'
      ? `Kwerenda — termin przedłużony${data.extension_days ? ` o ${data.extension_days} dni` : ''}`
      : data.status === 'doprecyzowanie'
        ? 'Czekamy na doprecyzowanie wniosku'
        : null
  return (
    <nav className="stages" aria-label="Etap sprawy">
      <ol>
        {STAGES.map((s, i) => {
          const state = i < current ? 'done' : i === current ? 'current' : 'todo'
          return (
            <li key={s.label} className={`stage is-${state}`} aria-current={state === 'current' ? 'step' : undefined}>
              <span className="stage-num num" aria-hidden="true">
                {i + 1}
              </span>
              <span className="stage-label">
                {s.label}
                {state === 'current' && flag && <span className="stage-flag">{flag}</span>}
              </span>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

// --- Odpowiedzi wydziałów --------------------------------------------------------------------

const DEPT_TONE: Record<string, string> = {
  oczekuje: 'is-waiting',
  odpowiedzial: 'is-answered',
  uszczegolowienie: 'is-clarification',
}

export function DepartmentsPanel({
  data,
  departments,
  onChanged,
}: {
  data: CaseDetail
  departments: Department[]
  onChanged: () => void
}) {
  const [rows, setRows] = useState<DepartmentStatus[]>(data.department_status)
  const [adding, setAdding] = useState('')
  const [clarifyFor, setClarifyFor] = useState<string | null>(null)
  const [details, setDetails] = useState('')
  const [letter, setLetter] = useState<{ code: string; text: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const closed = data.status === 'odpowiedz_wyslana'

  const run = async (fn: () => Promise<DepartmentStatus[]>) => {
    setBusy(true)
    setError(null)
    try {
      setRows(await fn())
      onChanged()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const answered = rows.filter((r) => r.status === 'odpowiedzial').length

  return (
    <section className="panel" aria-labelledby="depts-status-heading">
      <h2 id="depts-status-heading" className="panel-title">
        Odpowiedzi wydziałów{' '}
        {rows.length > 0 && (
          <span className="similar-meta num">
            ({answered} z {rows.length} odpowiedziało)
          </span>
        )}
      </h2>
      <p className="field-hint">
        Wydziały przygotowują projekt odpowiedzi w terminie wyznaczonym przez koordynatora (§ 11 Zarządzenia nr
        535/2024). Odpowiedź wgrana w sekcji niżej oznacza wydział jako „odpowiedział”.
      </p>

      {rows.length === 0 ? (
        <p className="field-hint">Do sprawy nie przypisano jeszcze wydziałów.</p>
      ) : (
        <table className="register compact-table dept-table">
          <thead>
            <tr>
              <th scope="col">Wydział</th>
              <th scope="col">Status</th>
              <th scope="col">Zapytanie</th>
              <th scope="col">Odpowiedź</th>
              {!closed && <th scope="col">Działania</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.code}>
                <td>
                  <strong>{r.code}</strong> — {r.name}
                </td>
                <td>
                  <span className={`dept-status ${DEPT_TONE[r.status]}`}>{r.status_label}</span>
                  {r.clarification_count > 0 && r.note && <span className="cell-note">{r.note}</span>}
                </td>
                <td className="num nowrap">{formatIso(r.requested_at)}</td>
                <td className="num nowrap">{formatIso(r.answered_at)}</td>
                {!closed && (
                  <td>
                    <div className="row-actions">
                      {r.status !== 'odpowiedzial' && (
                        <button
                          type="button"
                          className="link-button"
                          disabled={busy}
                          onClick={() => run(() => setDepartmentStatus(data.id, r.code, 'odpowiedzial'))}
                        >
                          Oznacz: odpowiedział
                        </button>
                      )}
                      <button
                        type="button"
                        className="link-button"
                        disabled={busy}
                        onClick={() => {
                          setClarifyFor(r.code)
                          setDetails('')
                          setLetter(null)
                        }}
                      >
                        Poproś o uszczegółowienie
                      </button>
                      {r.status !== 'oczekuje' && (
                        <button
                          type="button"
                          className="link-button"
                          disabled={busy}
                          onClick={() => run(() => setDepartmentStatus(data.id, r.code, 'oczekuje'))}
                        >
                          Czekamy ponownie
                        </button>
                      )}
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {clarifyFor && !letter && (
        <form
          className="stack clarify-form"
          onSubmit={(e) => {
            e.preventDefault()
            setBusy(true)
            setError(null)
            requestClarification(data.id, clarifyFor, details)
              .then((res) => {
                setRows(res.departments)
                setLetter({ code: res.code, text: res.text })
                onChanged()
              })
              .catch((err) => setError(errorText(err)))
              .finally(() => setBusy(false))
          }}
        >
          <div className="field">
            <label className="field-label small" htmlFor="clarify-details">
              Czego brakuje w odpowiedzi wydziału {clarifyFor}?
            </label>
            <textarea
              id="clarify-details"
              className="input textarea"
              rows={3}
              value={details}
              onChange={(e) => setDetails(e.target.value)}
            />
          </div>
          <div className="actions compact">
            <button type="submit" className="primary-button" disabled={busy}>
              Przygotuj prośbę
            </button>
            <button type="button" className="link-button" onClick={() => setClarifyFor(null)}>
              Anuluj
            </button>
          </div>
        </form>
      )}

      {letter && (
        <div className="stack clarify-form">
          <label className="field-label small" htmlFor="clarify-letter">
            Prośba do wydziału {letter.code} — skopiuj i wyślij samodzielnie
          </label>
          <textarea id="clarify-letter" className="input textarea" rows={10} defaultValue={letter.text} />
          <div className="actions compact">
            <button type="button" className="secondary-button" onClick={() => navigator.clipboard?.writeText(letter.text)}>
              Kopiuj treść
            </button>
            <button
              type="button"
              className="link-button"
              onClick={() => {
                setLetter(null)
                setClarifyFor(null)
              }}
            >
              Zamknij
            </button>
          </div>
        </div>
      )}

      {!closed && (
        <div className="inline-add">
          <label className="visually-hidden" htmlFor="add-dept">
            Dodaj wydział do sprawy
          </label>
          <select id="add-dept" className="input select" value={adding} onChange={(e) => setAdding(e.target.value)}>
            <option value="">Zapytaj kolejny wydział…</option>
            {departments
              .filter((d) => !rows.some((r) => r.code === d.code))
              .map((d) => (
                <option key={d.code} value={d.code}>
                  {d.code} — {d.name}
                </option>
              ))}
          </select>
          <button
            type="button"
            className="secondary-button"
            disabled={!adding || busy}
            onClick={() => {
              const code = adding
              setAdding('')
              run(() => addCaseDepartment(data.id, code))
            }}
          >
            Dodaj wydział
          </button>
        </div>
      )}

      {error && <p className="field-error">{error}</p>}
    </section>
  )
}

// --- Przedłużenie terminu (art. 13 ust. 2 u.d.i.p.) ----------------------------------------------

const DAY_MS = 24 * 60 * 60 * 1000

export function ExtensionPanel({ data, onDraft }: { data: CaseDetail; onDraft: (r: DraftResult) => void }) {
  const original = data.original_deadline_date
  const max = data.max_deadline_date
  const [deadline, setDeadline] = useState(max ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const today = todayIso()
  const late = !!original && today > original
  const orig = original ? parseIso(original) : null
  const chosen = deadline ? parseIso(deadline) : null
  const extra = orig && chosen ? Math.round((chosen.getTime() - orig.getTime()) / DAY_MS) : null
  const invalid =
    !chosen ? 'Wybierz nowy termin.' : original && deadline <= original ? 'Nowy termin musi być późniejszy niż termin 14-dniowy.' : max && deadline > max ? 'Termin nie może przekraczać 2 miesięcy od dnia złożenia wniosku.' : null

  return (
    <section className="panel" aria-labelledby="extension-heading">
      <h2 id="extension-heading" className="panel-title">
        Przedłużenie terminu (kwerenda)
      </h2>
      <p className="field-hint">
        Art. 13 ust. 2 u.d.i.p.: jeżeli informacji nie można udostępnić w 14 dni, urząd w tym terminie powiadamia
        wnioskodawcę o powodach opóźnienia i nowym terminie — nie dłuższym niż 2 miesiące od dnia złożenia wniosku.
      </p>
      <dl className="facts">
        <div>
          <dt>Termin 14-dniowy</dt>
          <dd className="num">{formatIso(original)}</dd>
        </div>
        <div>
          <dt>Obecny termin</dt>
          <dd className="num">
            {formatIso(data.deadline_date)}
            {data.extension_days > 0 && <span className="dd-sub">przedłużony o {data.extension_days} dni</span>}
          </dd>
        </div>
        <div>
          <dt>Najpóźniej (2 miesiące od wpływu)</dt>
          <dd className="num">{formatIso(max)}</dd>
        </div>
      </dl>

      {late && (
        <div className="notice notice-warning">
          <strong>Termin 14-dniowy już minął</strong>
          <p>
            Powiadomienie o przedłużeniu powinno zostać wysłane przed {formatIso(original)}. Możesz je przygotować, ale
            będzie spóźnione.
          </p>
        </div>
      )}

      <form
        className="status-form"
        onSubmit={async (e) => {
          e.preventDefault()
          if (invalid) return setError(invalid)
          setBusy(true)
          setError(null)
          try {
            onDraft(await createLetter(data.id, { kind: 'kwerenda', new_deadline: deadline }))
          } catch (err) {
            setError(errorText(err))
          } finally {
            setBusy(false)
          }
        }}
      >
        <div className="field">
          <label className="field-label small" htmlFor="ext-deadline">
            Nowy termin
          </label>
          <input
            id="ext-deadline"
            type="date"
            className="input input-date"
            min={original ?? undefined}
            max={max ?? undefined}
            value={deadline}
            onChange={(e) => {
              setDeadline(e.target.value)
              setError(null)
            }}
          />
        </div>
        <p className="ext-days num" aria-live="polite">
          {extra !== null && extra > 0 ? `+${extra} dni względem terminu 14-dniowego` : ''}
        </p>
        <button type="submit" className="primary-button" disabled={busy}>
          {busy ? 'Przygotowywanie…' : 'Przedłuż termin i przygotuj zawiadomienie'}
        </button>
      </form>
      {error && <p className="field-error">{error}</p>}
    </section>
  )
}
