import type { CaseDetail, CaseDocument, DepartmentReply } from '../../lib/api'
import { formatIso, formatTimestamp } from '../../lib/dates'
import { DOCUMENT_LABELS, deptLabel } from '../../lib/domain'
import { useDepartments } from '../../lib/hooks'

// Akta sprawy tylko do odczytu: dokumenty, materiały z wydziałów i historia zdarzeń.

export function CaseDocuments({ documents }: { documents: CaseDocument[] }) {
  if (documents.length === 0) return null
  return (
    <section className="panel" aria-labelledby="documents-heading">
      <h2 id="documents-heading" className="panel-title">
        Dokumenty sprawy
      </h2>
      <ul className="doc-list">
        {documents.map((item) => (
          <li key={item.id}>
            <details>
              <summary>
                {DOCUMENT_LABELS[item.kind]}{' '}
                <span className="meta num">
                  {formatIso(item.document_date)}
                  {item.filename && ` · ${item.filename}`}
                </span>
              </summary>
              <p className="prewrap">{item.text}</p>
            </details>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function DepartmentMaterials({ replies }: { replies: DepartmentReply[] }) {
  const { nameOf } = useDepartments()
  if (replies.length === 0) return null
  return (
    <section className="panel" aria-labelledby="materials-heading">
      <h2 id="materials-heading" className="panel-title">
        Materiały z wydziałów ({replies.length})
      </h2>
      <ul className="doc-list">
        {replies.map((reply) => (
          <li key={reply.id}>
            <details>
              <summary>
                {reply.department ? deptLabel(reply.department, nameOf(reply.department)) : 'Wydział'}
                {reply.filename && <span className="meta"> · {reply.filename}</span>}
              </summary>
              <p className="prewrap">{reply.text}</p>
            </details>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function CaseHistory({ events }: { events: CaseDetail['events'] }) {
  if (events.length === 0) return null
  return (
    <section className="panel" aria-labelledby="history-heading">
      <h2 id="history-heading" className="panel-title">
        Historia sprawy
      </h2>
      <ol className="events">
        {events.map((event, index) => (
          <li key={index}>
            <span className="num">{formatTimestamp(event.created_at)}</span> {event.event.replaceAll('_', ' ')}
            {event.detail && <span className="meta"> — {event.detail}</span>}
          </li>
        ))}
      </ol>
    </section>
  )
}
