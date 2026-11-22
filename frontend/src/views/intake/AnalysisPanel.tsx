import { useEffect, useId, useRef, useState } from 'react'
import { BusyButton } from '../../components/BusyButton'
import { Notice } from '../../components/Notice'
import type { IntakeAnalysis, ParsedRequest, RegisterResult } from '../../lib/api'
import { formatIso } from '../../lib/dates'
import { useAction } from '../../lib/hooks'
import { Registered } from './Registered'
import { RegistrationForm } from './RegistrationForm'
import { SimilarCases } from './SimilarCases'

type Props = {
  analysis: IntakeAnalysis
  fileName: string
  receivedAt: string
  onReanalyze: (manualText: string) => Promise<void>
  onRestart: () => void
}

export function AnalysisPanel({ analysis, fileName, receivedAt, onReanalyze, onRestart }: Props) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [registered, setRegistered] = useState<RegisterResult | null>(null)

  useEffect(() => headingRef.current?.focus(), [])

  if (registered) return <Registered result={registered} onNext={onRestart} />

  const { extraction } = analysis
  return (
    <div className="analysis">
      <div className="analysis-head">
        <h2 ref={headingRef} tabIndex={-1} className="section-title">
          Analiza wniosku
        </h2>
        <p className="field-hint">
          {fileName} · {extraction.used_ocr ? 'odczyt OCR ze skanu' : 'odczyt tekstu dokumentu'} ·{' '}
          {analysis.llm_used ? 'analiza modelu Gemini' : 'analiza regułowa (bez modelu)'}. Sprawdź dane przed rejestracją.
        </p>
      </div>

      {extraction.warning && <ManualText warning={extraction.warning} onSubmit={onReanalyze} />}
      <RequestSummary parsed={analysis.parsed_request} />
      <RegistrationForm analysis={analysis} receivedAt={receivedAt} onRegistered={setRegistered} onCancel={onRestart} />
      <SimilarCases cases={analysis.similar_cases} />
    </div>
  )
}

function RequestSummary({ parsed }: { parsed: ParsedRequest }) {
  return (
    <section className="panel" aria-labelledby="request-summary-heading">
      <h3 id="request-summary-heading">Czego dotyczy wniosek</h3>
      <dl className="facts">
        <div>
          <dt>Kategoria</dt>
          <dd>{parsed.kategoria}</dd>
        </div>
        <div>
          <dt>Tryb</dt>
          <dd>{parsed.czy_to_wniosek_udip ? 'Wniosek o informację publiczną (u.d.i.p.)' : 'Prawdopodobnie inny tryb — sprawdź'}</dd>
        </div>
        <div>
          <dt>Forma odpowiedzi</dt>
          <dd>{parsed.forma_odpowiedzi ?? '—'}</dd>
        </div>
        {parsed.data_na_pismie && (
          <div>
            <dt>Data na piśmie</dt>
            <dd className="num">{formatIso(parsed.data_na_pismie)}</dd>
          </div>
        )}
      </dl>
      {parsed.pytania.length > 0 && (
        <>
          <h4 className="subhead">Pytania wnioskodawcy ({parsed.pytania.length})</h4>
          <ol className="questions">
            {parsed.pytania.map((question, index) => (
              <li key={index}>{question}</li>
            ))}
          </ol>
        </>
      )}
      {parsed.uwagi && (
        <Notice tone="info" title="Uwagi asystenta">
          <p>{parsed.uwagi}</p>
        </Notice>
      )}
    </section>
  )
}

/** Skan nieczytelny dla OCR (np. pismo odręczne): urzędnik przepisuje treść i analiza rusza ponownie. */
function ManualText({ warning, onSubmit }: { warning: string; onSubmit: (text: string) => Promise<void> }) {
  const id = useId()
  const [text, setText] = useState('')
  const { busy, error, run } = useAction()

  return (
    <Notice tone="warning" title="Dokument jest trudny do odczytania">
      <p>{warning}</p>
      <label className="field-label small" htmlFor={id}>
        Treść wniosku
      </label>
      <textarea id={id} className="input textarea" rows={5} value={text} onChange={(event) => setText(event.target.value)} />
      {error && <p className="field-error">{error}</p>}
      <BusyButton
        type="button"
        variant="secondary"
        busy={busy !== null}
        busyLabel="Analizowanie…"
        disabled={!text.trim()}
        onClick={() => run(() => onSubmit(text))}
      >
        Analizuj wpisaną treść
      </BusyButton>
    </Notice>
  )
}
