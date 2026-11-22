import { useId, useState, type FormEvent } from 'react'
import { BusyButton } from '../../components/BusyButton'
import { CopyableText } from '../../components/CopyableText'
import { addCaseDepartment, requestClarification, setDepartmentStatus, type CaseDetail, type DeptStatus } from '../../lib/api'
import { formatIso } from '../../lib/dates'
import { DEPT_STATUS_TAG, deptLabel, isClosed } from '../../lib/domain'
import { useAction, useDepartments } from '../../lib/hooks'

type ClarificationLetter = { code: string; text: string }

/** Odpowiedzi wydziałów: kto odpowiedział, na kogo czekamy, prośby o uszczegółowienie, zapytanie kolejnej komórki. */
export function DepartmentsPanel({ data, onChanged }: { data: CaseDetail; onChanged: () => void }) {
  const rows = data.department_status
  const closed = isClosed(data.status)
  const { departments } = useDepartments()
  const { busy, error, run } = useAction()
  const [newDepartment, setNewDepartment] = useState('')
  const [clarifyFor, setClarifyFor] = useState<string | null>(null)
  const [details, setDetails] = useState('')
  const [letter, setLetter] = useState<ClarificationLetter | null>(null)
  const ids = { newDepartment: useId(), details: useId() }
  const answered = rows.filter((row) => row.status === 'odpowiedzial').length
  const working = busy !== null

  const change = async (action: () => Promise<unknown>) => {
    if ((await run(action)) !== undefined) onChanged()
  }
  const markAs = (code: string, status: DeptStatus) => change(() => setDepartmentStatus(data.id, code, status))

  const addDepartment = () => {
    const code = newDepartment
    setNewDepartment('')
    change(() => addCaseDepartment(data.id, code))
  }

  const openClarification = (code: string) => {
    setClarifyFor(code)
    setDetails('')
    setLetter(null)
  }

  const closeClarification = () => {
    setClarifyFor(null)
    setLetter(null)
  }

  const submitClarification = async (event: FormEvent) => {
    event.preventDefault()
    if (!clarifyFor) return
    const result = await run(() => requestClarification(data.id, clarifyFor, details))
    if (!result) return
    setLetter({ code: result.code, text: result.text })
    onChanged()
  }

  return (
    <section className="panel" aria-labelledby="departments-heading">
      <h2 id="departments-heading" className="panel-title">
        Odpowiedzi wydziałów{' '}
        {rows.length > 0 && (
          <span className="meta num">
            ({answered} z {rows.length} odpowiedziało)
          </span>
        )}
      </h2>
      <p className="field-hint">
        Wydziały przygotowują projekt odpowiedzi w terminie wyznaczonym przez koordynatora (§ 11 Zarządzenia nr 535/2024).
        Odpowiedź wgrana w sekcji niżej oznacza wydział jako „odpowiedział”.
      </p>

      {rows.length === 0 ? (
        <p className="field-hint">Do sprawy nie przypisano jeszcze wydziałów.</p>
      ) : (
        <table className="data-table compact-table dept-table">
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
            {rows.map((row) => (
              <tr key={row.code}>
                <td>
                  <strong>{row.code}</strong> — {row.name}
                </td>
                <td>
                  <span className={DEPT_STATUS_TAG[row.status]}>{row.status_label}</span>
                  {row.clarification_count > 0 && row.note && <span className="cell-note">{row.note}</span>}
                </td>
                <td className="num nowrap">{formatIso(row.requested_at)}</td>
                <td className="num nowrap">{formatIso(row.answered_at)}</td>
                {!closed && (
                  <td>
                    <div className="row-actions">
                      {row.status !== 'odpowiedzial' && (
                        <button type="button" className="link-button" disabled={working} onClick={() => markAs(row.code, 'odpowiedzial')}>
                          Oznacz: odpowiedział
                        </button>
                      )}
                      <button type="button" className="link-button" disabled={working} onClick={() => openClarification(row.code)}>
                        Poproś o uszczegółowienie
                      </button>
                      {row.status !== 'oczekuje' && (
                        <button type="button" className="link-button" disabled={working} onClick={() => markAs(row.code, 'oczekuje')}>
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
        <form className="stack clarify-form" onSubmit={submitClarification}>
          <div className="field">
            <label className="field-label small" htmlFor={ids.details}>
              Czego brakuje w odpowiedzi wydziału {clarifyFor}?
            </label>
            <textarea
              id={ids.details}
              className="input textarea"
              rows={3}
              value={details}
              onChange={(event) => setDetails(event.target.value)}
            />
          </div>
          <div className="actions compact">
            <BusyButton type="submit" busy={working} busyLabel="Przygotowywanie…">
              Przygotuj prośbę
            </BusyButton>
            <button type="button" className="link-button" onClick={closeClarification}>
              Anuluj
            </button>
          </div>
        </form>
      )}

      {letter && (
        <div className="stack clarify-form">
          <CopyableText label={`Prośba do wydziału ${letter.code} — skopiuj i wyślij samodzielnie`} text={letter.text} rows={10} />
          <div className="actions compact">
            <button type="button" className="link-button" onClick={closeClarification}>
              Zamknij
            </button>
          </div>
        </div>
      )}

      {!closed && (
        <div className="inline-add">
          <label className="visually-hidden" htmlFor={ids.newDepartment}>
            Dodaj wydział do sprawy
          </label>
          <select
            id={ids.newDepartment}
            className="input select"
            value={newDepartment}
            onChange={(event) => setNewDepartment(event.target.value)}
          >
            <option value="">Zapytaj kolejny wydział…</option>
            {departments
              .filter((department) => !rows.some((row) => row.code === department.code))
              .map((department) => (
                <option key={department.code} value={department.code}>
                  {deptLabel(department.code, department.name)}
                </option>
              ))}
          </select>
          <button type="button" className="secondary-button" disabled={!newDepartment || working} onClick={addDepartment}>
            Dodaj wydział
          </button>
        </div>
      )}

      {error && <p className="field-error">{error}</p>}
    </section>
  )
}
