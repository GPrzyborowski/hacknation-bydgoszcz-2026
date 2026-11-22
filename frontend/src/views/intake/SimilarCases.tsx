import type { SimilarCase } from '../../lib/api'
import { formatIso } from '../../lib/dates'
import { caseHref } from '../../lib/router'

export function SimilarCases({ cases }: { cases: SimilarCase[] }) {
  return (
    <section className="panel" aria-labelledby="similar-heading">
      <h3 id="similar-heading">Podobne sprawy z archiwum</h3>
      {cases.length === 0 ? (
        <p className="field-hint">Nie znaleziono podobnych spraw. Archiwum uzupełnisz w zakładce Baza wiedzy.</p>
      ) : (
        <ul className="similar-list">
          {cases.map((item) => (
            <li key={item.id}>
              <div className="similar-head">
                <a className="num" href={caseHref(item.id)}>
                  {item.case_number}
                </a>
                <span className="meta num">
                  wpływ {formatIso(item.received_date)} · odpowiedź {formatIso(item.response_date)}
                  {item.departments.length > 0 && ` · ${item.departments.join(', ')}`}
                  {item.procedure_mode === 'nie_dysponent' && ' · UMB nie był dysponentem'}
                </span>
              </div>
              <p>{item.subject}</p>
              {item.response_text && (
                <details>
                  <summary>Udzielona odpowiedź</summary>
                  <p className="prewrap">{item.response_text}</p>
                </details>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
