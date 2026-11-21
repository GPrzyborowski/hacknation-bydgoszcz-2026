import { useEffect, useId, useRef, useState } from 'react'
import {
  ApiError,
  listDepartments,
  registerCase,
  type Department,
  type IntakeAnalysis,
  type RegisterResult,
} from '../lib/api'
import { formatIso } from '../lib/deadline'
import { navigate } from '../lib/router'

type Props = {
  analysis: IntakeAnalysis
  fileName: string
  receivedAt: string
  onReanalyze: (manualText: string) => Promise<void>
  onCancel: () => void
}

const errorText = (err: unknown) => (err instanceof ApiError || err instanceof Error ? err.message : 'Nieznany błąd.')

export function AnalysisPanel({ analysis, fileName, receivedAt, onReanalyze, onCancel }: Props) {
  const parsed = analysis.parsed_request
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [departments, setDepartments] = useState<Department[]>([])
  const [form, setForm] = useState(() => ({
    applicant: parsed.wnioskodawca ?? '',
    contact: parsed.adres_do_odpowiedzi ?? '',
    subject: parsed.temat_skrot ?? '',
    deadline: analysis.suggested_deadline?.deadline_date ?? '',
    caseNumber: '',
    initials: '',
    templates: true,
  }))
  const [selected, setSelected] = useState<string[]>(() => analysis.suggested_departments.map((d) => d.code))
  const [extra, setExtra] = useState('')
  const [errors, setErrors] = useState<{ applicant?: string; subject?: string }>({})
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [registered, setRegistered] = useState<RegisterResult | null>(null)
  const ids = { applicant: useId(), contact: useId(), subject: useId(), deadline: useId(), number: useId(), initials: useId() }

  useEffect(() => {
    headingRef.current?.focus()
    let alive = true
    listDepartments()
      .then((d) => alive && setDepartments(d.filter((x) => x.is_active)))
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [])

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }))
  const toggle = (code: string) => setSelected((s) => (s.includes(code) ? s.filter((c) => c !== code) : [...s, code]))
  const nameOf = (code: string) => departments.find((d) => d.code === code)?.name ?? code

  const submit = async (e: { preventDefault: () => void }) => {
    e.preventDefault()
    const next: typeof errors = {}
    if (!form.applicant.trim()) next.applicant = 'Podaj wnioskodawcę (imię i nazwisko, nazwę lub adres e-mail).'
    if (!form.subject.trim()) next.subject = 'Podaj przedmiot wniosku.'
    setErrors(next)
    if (next.applicant) return document.getElementById(ids.applicant)?.focus()
    if (next.subject) return document.getElementById(ids.subject)?.focus()
    setSaving(true)
    setSaveError(null)
    try {
      const result = await registerCase({
        case_number: form.caseNumber.trim() || null,
        applicant: form.applicant.trim(),
        applicant_contact: form.contact.trim() || null,
        subject: form.subject.trim(),
        received_date: receivedAt,
        deadline_date: form.deadline || null,
        departments: selected,
        initials: form.initials.trim() || null,
        intake_id: analysis.intake_id,
        parsed_request: { ...parsed, wnioskodawca: form.applicant.trim(), temat_skrot: form.subject.trim() },
        generate_dept_request_template: form.templates,
      })
      setRegistered(result)
    } catch (err) {
      setSaveError(errorText(err))
    } finally {
      setSaving(false)
    }
  }

  if (registered) {
    return <Registered result={registered} nameOf={nameOf} onNext={onCancel} />
  }

  return (
    <div className="analysis">
      <div className="analysis-head">
        <h2 ref={headingRef} tabIndex={-1} className="section-title">
          Analiza wniosku
        </h2>
        <p className="field-hint">
          {fileName} · {analysis.extraction.used_ocr ? 'odczyt OCR ze skanu' : 'odczyt tekstu dokumentu'} ·{' '}
          {analysis.llm_used ? 'analiza modelu Gemini' : 'analiza regułowa (bez modelu)'}. Sprawdź dane przed
          rejestracją.
        </p>
      </div>

      {analysis.extraction.warning && <ManualText warning={analysis.extraction.warning} onSubmit={onReanalyze} />}

      <section className="panel" aria-labelledby="questions-heading">
        <h3 id="questions-heading">Czego dotyczy wniosek</h3>
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
              {parsed.pytania.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ol>
          </>
        )}
        {parsed.uwagi && (
          <div className="notice notice-info">
            <strong>Uwagi asystenta</strong>
            <p>{parsed.uwagi}</p>
          </div>
        )}
      </section>

      <form className="intake" onSubmit={submit} noValidate aria-busy={saving}>
        <h3 className="form-title">Dane do rejestru</h3>

        <div className={`field${errors.applicant ? ' has-error' : ''}`}>
          <label className="field-label" htmlFor={ids.applicant}>
            Wnioskodawca
          </label>
          {errors.applicant && <p className="field-error">{errors.applicant}</p>}
          <input
            id={ids.applicant}
            className="input"
            value={form.applicant}
            onChange={(e) => set('applicant', e.target.value)}
            aria-invalid={!!errors.applicant}
          />
        </div>

        <div className="field">
          <label className="field-label" htmlFor={ids.contact}>
            Adres do odpowiedzi <span className="optional">(opcjonalnie)</span>
          </label>
          <input id={ids.contact} className="input" value={form.contact} onChange={(e) => set('contact', e.target.value)} />
        </div>

        <div className={`field${errors.subject ? ' has-error' : ''}`}>
          <label className="field-label" htmlFor={ids.subject}>
            Przedmiot wniosku
          </label>
          <p className="field-hint">Skrócony opis tematu, widoczny w rejestrze.</p>
          {errors.subject && <p className="field-error">{errors.subject}</p>}
          <textarea
            id={ids.subject}
            className="input textarea"
            rows={2}
            value={form.subject}
            onChange={(e) => set('subject', e.target.value)}
            aria-invalid={!!errors.subject}
          />
        </div>

        <div className="field-row">
          <div className="field">
            <span className="field-label">Data wpływu</span>
            <span className="readonly num">{formatIso(receivedAt)}</span>
          </div>
          <div className="field">
            <label className="field-label" htmlFor={ids.deadline}>
              Termin odpowiedzi
            </label>
            <input
              id={ids.deadline}
              type="date"
              className="input input-date"
              value={form.deadline}
              max={analysis.suggested_deadline?.max_extended_deadline}
              onChange={(e) => set('deadline', e.target.value)}
            />
          </div>
        </div>
        {analysis.suggested_deadline?.note && <p className="field-hint">{analysis.suggested_deadline.note}</p>}

        <div className="field-row">
          <div className="field">
            <label className="field-label" htmlFor={ids.number}>
              Znak sprawy <span className="optional">(opcjonalnie)</span>
            </label>
            <p className="field-hint">Puste — nadany kolejny numer BKS.IV.1431.</p>
            <input
              id={ids.number}
              className="input num"
              value={form.caseNumber}
              placeholder="BKS.IV.1431.…"
              onChange={(e) => set('caseNumber', e.target.value)}
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor={ids.initials}>
              Osoba odpowiedzialna <span className="optional">(opcjonalnie)</span>
            </label>
            <p className="field-hint">Inicjały lub nazwa, jak w rejestrze.</p>
            <input id={ids.initials} className="input" value={form.initials} onChange={(e) => set('initials', e.target.value)} />
          </div>
        </div>

        <fieldset className="field">
          <legend className="field-label">Wydziały do zapytania</legend>
          <p className="field-hint">Propozycje asystenta są zaznaczone. Zapytań nikt nie wysyła automatycznie.</p>
          <ul className="choice-list">
            {analysis.suggested_departments.map((d) => (
              <li key={d.code}>
                <label className="choice">
                  <input type="checkbox" checked={selected.includes(d.code)} onChange={() => toggle(d.code)} />
                  <span>
                    <strong>
                      {d.code} — {d.name}
                    </strong>
                    <span className="choice-hint">{d.reason}</span>
                  </span>
                </label>
              </li>
            ))}
            {selected
              .filter((c) => !analysis.suggested_departments.some((d) => d.code === c))
              .map((code) => (
                <li key={code}>
                  <label className="choice">
                    <input type="checkbox" checked onChange={() => toggle(code)} />
                    <span>
                      <strong>
                        {code} — {nameOf(code)}
                      </strong>
                      <span className="choice-hint">Dodane przez urzędnika</span>
                    </span>
                  </label>
                </li>
              ))}
          </ul>
          <div className="inline-add">
            <label className="visually-hidden" htmlFor="extra-dept">
              Dodaj komórkę
            </label>
            <select id="extra-dept" className="input select" value={extra} onChange={(e) => setExtra(e.target.value)}>
              <option value="">Dodaj inną komórkę…</option>
              {departments
                .filter((d) => !selected.includes(d.code))
                .map((d) => (
                  <option key={d.code} value={d.code}>
                    {d.code} — {d.name}
                  </option>
                ))}
            </select>
            <button
              type="button"
              className="secondary-button"
              disabled={!extra}
              onClick={() => {
                if (extra) setSelected((s) => [...s, extra])
                setExtra('')
              }}
            >
              Dodaj
            </button>
          </div>
          {analysis.suggested_external_entities.length > 0 && (
            <div className="notice notice-info">
              <strong>Możliwe, że urząd nie jest dysponentem informacji</strong>
              <p>
                Wniosek może dotyczyć:{' '}
                {analysis.suggested_external_entities.map((e) => e.name).join('; ')}. Pismo wskazujące właściwy podmiot
                przygotujesz w karcie sprawy.
              </p>
            </div>
          )}
        </fieldset>

        <label className="choice">
          <input type="checkbox" checked={form.templates} onChange={(e) => set('templates', e.target.checked)} />
          <span>Przygotuj treść prośby do wydziałów (do skopiowania)</span>
        </label>

        {saveError && (
          <div className="notice notice-error" role="alert">
            <p>
              <strong>Nie zarejestrowano wniosku.</strong> {saveError}
            </p>
          </div>
        )}

        <div className="actions">
          <button type="submit" className="primary-button" disabled={saving}>
            {saving && <span className="spinner" aria-hidden="true" />}
            {saving ? 'Rejestrowanie…' : 'Zarejestruj wniosek'}
          </button>
          <button type="button" className="link-button" onClick={onCancel}>
            Anuluj i wgraj inny wniosek
          </button>
        </div>
      </form>

      <SimilarCases analysis={analysis} />
    </div>
  )
}

function ManualText({ warning, onSubmit }: { warning: string; onSubmit: (text: string) => Promise<void> }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return (
    <div className="notice notice-warning">
      <strong>Dokument jest trudny do odczytania</strong>
      <p>{warning}</p>
      <label className="field-label small" htmlFor="manual-text">
        Treść wniosku
      </label>
      <textarea
        id="manual-text"
        className="input textarea"
        rows={5}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      {error && <p className="field-error">{error}</p>}
      <button
        type="button"
        className="secondary-button"
        disabled={busy || !text.trim()}
        onClick={async () => {
          setBusy(true)
          setError(null)
          try {
            await onSubmit(text)
          } catch (err) {
            setError(errorText(err))
          } finally {
            setBusy(false)
          }
        }}
      >
        {busy ? 'Analizowanie…' : 'Analizuj wpisaną treść'}
      </button>
    </div>
  )
}

function SimilarCases({ analysis }: { analysis: IntakeAnalysis }) {
  return (
    <section className="panel" aria-labelledby="similar-heading">
      <h3 id="similar-heading">Podobne sprawy z archiwum</h3>
      {analysis.similar_cases.length === 0 ? (
        <p className="field-hint">Nie znaleziono podobnych spraw. Archiwum uzupełnisz w zakładce Baza wiedzy.</p>
      ) : (
        <ul className="similar-list">
          {analysis.similar_cases.map((c) => (
            <li key={c.id} className="similar">
              <div className="similar-head">
                <a className="num" href={`#/sprawa/${c.id}`}>
                  {c.case_number}
                </a>
                <span className="similar-meta num">
                  wpływ {formatIso(c.received_date)} · odpowiedź {formatIso(c.response_date)}
                  {c.departments.length > 0 && ` · ${c.departments.join(', ')}`}
                  {c.procedure_mode === 'nie_dysponent' && ' · UMB nie był dysponentem'}
                </span>
              </div>
              <p>{c.subject}</p>
              {c.response_text && (
                <details>
                  <summary>Udzielona odpowiedź</summary>
                  <p className="prewrap">{c.response_text}</p>
                </details>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function Registered({
  result,
  nameOf,
  onNext,
}: {
  result: RegisterResult
  nameOf: (code: string) => string
  onNext: () => void
}) {
  const ref = useRef<HTMLHeadingElement>(null)
  useEffect(() => ref.current?.focus(), [])
  const templates = Object.entries(result.request_templates)
  return (
    <section className="confirmation" aria-labelledby="registered-heading">
      <div className="confirmation-head">
        <svg className="confirmation-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <div>
          <h2 id="registered-heading" ref={ref} tabIndex={-1}>
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
            <div key={code} className="field">
              <label className="field-label small" htmlFor={`tpl-${code}`}>
                {code} — {nameOf(code)}
              </label>
              <textarea id={`tpl-${code}`} className="input textarea" rows={8} defaultValue={text} />
              <button type="button" className="link-button" onClick={() => navigator.clipboard?.writeText(text)}>
                Kopiuj treść
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="actions">
        <button type="button" className="primary-button" onClick={() => navigate({ name: 'case', id: result.id })}>
          Przejdź do sprawy
        </button>
        <button type="button" className="secondary-button" onClick={onNext}>
          Dodaj kolejny wniosek
        </button>
      </div>
    </section>
  )
}
