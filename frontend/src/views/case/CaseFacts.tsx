import { useId, useState, type FormEvent } from 'react'
import { BusyButton } from '../../components/BusyButton'
import { Fact } from '../../components/Fact'
import { updateStatus, type CaseDetail, type CaseStatus } from '../../lib/api'
import { formatIso } from '../../lib/dates'
import { STATUS_LABELS, deptLabel, isClosed, remainingText } from '../../lib/domain'
import { useAction, useDepartments } from '../../lib/hooks'

export function CaseFacts({ data, onSaved }: { data: CaseDetail; onSaved: () => void }) {
  const { nameOf } = useDepartments()
  const closed = isClosed(data.status)

  return (
    <section className="panel case-facts" aria-label="Dane sprawy">
      <dl className="facts">
        <Fact term="Wnioskodawca">
          {data.applicant || '—'}
          {data.applicant_contact && <span className="dd-sub">{data.applicant_contact}</span>}
        </Fact>
        <Fact term="Data wpływu" numeric>
          {formatIso(data.received_date)}
        </Fact>
        <Fact term="Termin odpowiedzi" numeric>
          <strong>{formatIso(data.deadline_date)}</strong>
          {!closed && data.days_remaining !== null && (
            <span className={`dd-sub remaining urgency-${data.urgency}`}>{remainingText(data.days_remaining)}</span>
          )}
          {data.deadline_note && <span className="dd-sub">{data.deadline_note}</span>}
        </Fact>
        {data.response_date && (
          <Fact term="Data odpowiedzi" numeric>
            {formatIso(data.response_date)}
            {data.answered_on_time === false && <span className="dd-sub remaining urgency-overdue">po terminie</span>}
          </Fact>
        )}
        <Fact term="Wydziały">{data.departments.map((code) => deptLabel(code, nameOf(code))).join('; ') || '—'}</Fact>
        <Fact term="Osoba odpowiedzialna">{data.initials || '—'}</Fact>
        {data.notes && <Fact term="Adnotacje">{data.notes}</Fact>}
      </dl>
      <StatusForm key={`${data.status}|${data.deadline_date}`} data={data} onSaved={onSaved} />
    </section>
  )
}

function StatusForm({ data, onSaved }: { data: CaseDetail; onSaved: () => void }) {
  const ids = { status: useId(), deadline: useId() }
  const [status, setStatus] = useState<CaseStatus>(data.status)
  const [deadline, setDeadline] = useState('')
  const { busy, error, run } = useAction()
  const setsNewDeadline = status === 'kwerenda' || status === 'doprecyzowanie'
  const changed = status !== data.status || (setsNewDeadline && deadline !== '')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (await run(() => updateStatus(data.id, status, setsNewDeadline ? deadline : null))) onSaved()
  }

  return (
    <form className="status-form" onSubmit={submit}>
      <div className="field">
        <label className="field-label small" htmlFor={ids.status}>
          Status sprawy
        </label>
        <select
          id={ids.status}
          className="input select"
          value={status}
          onChange={(event) => setStatus(event.target.value as CaseStatus)}
        >
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      {setsNewDeadline && (
        <div className="field">
          <label className="field-label small" htmlFor={ids.deadline}>
            Nowy termin <span className="optional">(maks. 2 miesiące od wpływu)</span>
          </label>
          <input
            id={ids.deadline}
            type="date"
            className="input input-date"
            value={deadline}
            onChange={(event) => setDeadline(event.target.value)}
          />
        </div>
      )}
      <BusyButton type="submit" variant="secondary" busy={busy !== null} busyLabel="Zapisywanie…" disabled={!changed}>
        Zapisz status
      </BusyButton>
      {error && <p className="field-error">{error}</p>}
    </form>
  )
}
