import { useEffect, useId, useRef } from 'react'
import { CopyableText } from '../../components/CopyableText'
import type { RegisterResult } from '../../lib/api'
import { formatIso } from '../../lib/dates'
import { deptLabel } from '../../lib/domain'
import { useDepartments } from '../../lib/hooks'
import { caseHref } from '../../lib/router'

export function Registered({ result, onNext }: { result: RegisterResult; onNext: () => void }) {
  const headingId = useId()
  const headingRef = useRef<HTMLHeadingElement>(null)
  const { nameOf } = useDepartments()
  const templates = Object.entries(result.request_templates)

  useEffect(() => headingRef.current?.focus(), [])

  return (
    <section className="confirmation" aria-labelledby={headingId}>
      <div className="confirmation-head">
        <svg className="confirmation-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <div>
          <h2 id={headingId} ref={headingRef} tabIndex={-1}>
            Wniosek zarejestrowany
          </h2>
          <p role="status">
            Znak sprawy <strong className="num">{result.case_number}</strong>, termin odpowiedzi{' '}
            <strong className="num">{formatIso(result.deadline_date)}</strong>.
          </p>
        </div>
      </div>

      {templates.length > 0 && (
        <div className="templates">
          <h3 className="subhead">Treść prośby do wydziałów</h3>
          <p className="field-hint">Skopiuj i wyślij samodzielnie — system niczego nie wysyła.</p>
          {templates.map(([code, text]) => (
            <CopyableText key={code} label={deptLabel(code, nameOf(code))} text={text} />
          ))}
        </div>
      )}

      <div className="actions">
        <a className="primary-button" href={caseHref(result.id)}>
          Przejdź do sprawy
        </a>
        <button type="button" className="secondary-button" onClick={onNext}>
          Dodaj kolejny wniosek
        </button>
      </div>
    </section>
  )
}
