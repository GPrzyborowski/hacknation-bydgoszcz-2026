import { useId, useState, type FormEvent } from 'react'
import { BusyButton } from '../../components/BusyButton'
import { Fact } from '../../components/Fact'
import { Notice } from '../../components/Notice'
import { createLetter, type CaseDetail, type DraftResult } from '../../lib/api'
import { daysBetween, formatIso, parseIso, todayIso } from '../../lib/dates'
import { useAction } from '../../lib/hooks'

/** Przedłużenie terminu (art. 13 ust. 2 u.d.i.p.). Dopuszczalny zakres nowego terminu sprawdza backend. */
export function ExtensionPanel({ data, onDraft }: { data: CaseDetail; onDraft: (result: DraftResult) => void }) {
  const inputId = useId()
  const original = data.original_deadline_date
  const latest = data.max_deadline_date
  const [deadline, setDeadline] = useState(latest ?? '')
  const { busy, error, setError, run } = useAction()
  const originalDay = parseIso(original)
  const chosenDay = parseIso(deadline)
  const extraDays = originalDay && chosenDay ? daysBetween(originalDay, chosenDay) : 0
  const noticeWouldBeLate = !!original && todayIso() > original

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!chosenDay) return setError('Wybierz nowy termin.')
    const result = await run(() => createLetter(data.id, { kind: 'kwerenda', new_deadline: deadline }))
    if (result) onDraft(result)
  }

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
        <Fact term="Termin 14-dniowy" numeric>
          {formatIso(original)}
        </Fact>
        <Fact term="Obecny termin" numeric>
          {formatIso(data.deadline_date)}
          {data.extension_days > 0 && <span className="dd-sub">przedłużony o {data.extension_days} dni</span>}
        </Fact>
        <Fact term="Najpóźniej (2 miesiące od wpływu)" numeric>
          {formatIso(latest)}
        </Fact>
      </dl>

      {noticeWouldBeLate && (
        <Notice tone="warning" title="Termin 14-dniowy już minął">
          <p>
            Powiadomienie o przedłużeniu powinno zostać wysłane przed {formatIso(original)}. Możesz je przygotować, ale
            będzie spóźnione.
          </p>
        </Notice>
      )}

      <form className="status-form" onSubmit={submit}>
        <div className="field">
          <label className="field-label small" htmlFor={inputId}>
            Nowy termin
          </label>
          <input
            id={inputId}
            type="date"
            className="input input-date"
            min={original ?? undefined}
            max={latest ?? undefined}
            value={deadline}
            onChange={(event) => {
              setDeadline(event.target.value)
              setError(null)
            }}
          />
        </div>
        <p className="ext-days num" aria-live="polite">
          {extraDays > 0 && `+${extraDays} dni względem terminu 14-dniowego`}
        </p>
        <BusyButton type="submit" busy={busy !== null} busyLabel="Przygotowywanie…">
          Przedłuż termin i przygotuj zawiadomienie
        </BusyButton>
      </form>
      {error && <p className="field-error">{error}</p>}
    </section>
  )
}
