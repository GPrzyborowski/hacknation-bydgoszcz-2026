import { previewDeadline } from '../../lib/api'
import { useConfig } from '../../lib/config'
import { formatLong, formatWeekday, parseIso } from '../../lib/dates'
import { remainingText } from '../../lib/domain'
import { useQuery } from '../../lib/hooks'

/** Termin odpowiedzi dla wpisanej daty wpływu — wyliczony przez backend tak samo jak przy rejestracji. */
export function DeadlineReadout({ receivedAt }: { receivedAt: string | null }) {
  const { answer_days } = useConfig()
  const { data } = useQuery(() => (receivedAt ? previewDeadline(receivedAt) : Promise.resolve(null)), receivedAt)
  const preview = data?.received_date === receivedAt ? data : null
  const deadline = parseIso(preview?.deadline_date)

  if (!preview || !deadline) {
    return (
      <div className="deadline is-empty" aria-live="polite">
        <span className="deadline-label">Termin odpowiedzi</span>
        <span className="deadline-date">—</span>
      </div>
    )
  }

  return (
    <div className={`deadline urgency-${preview.urgency}`} aria-live="polite">
      <span className="deadline-label">Termin odpowiedzi</span>
      <span className="deadline-date">
        {formatLong(deadline)}, {formatWeekday(deadline)}
      </span>
      <span className="deadline-meta">
        {answer_days} dni od daty wpływu (art. 13 ust. 1 u.d.i.p.) ·{' '}
        <span className={`remaining urgency-${preview.urgency}`}>{remainingText(preview.days_remaining)}</span>
      </span>
      {preview.note && <span className="deadline-note">{preview.note}</span>}
    </div>
  )
}
