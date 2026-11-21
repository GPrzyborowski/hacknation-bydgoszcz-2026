import { useEffect, useId, useMemo, useRef, useState, type RefObject } from 'react'
import { FileDropzone } from './components/FileDropzone'
import { UploadError, uploadRequest } from './lib/api'
import {
  ANSWER_DAYS,
  deadlineFor,
  formatLong,
  formatShort,
  formatWeekday,
  remainingText,
  todayIso,
} from './lib/deadline'
import { extensionOf, formatSize, validateFile } from './lib/files'
import './App.css'

type Submitted = {
  fileName: string
  receivedAt: string
  id?: string
}

type Rejection = { name?: string; reason: string }

type Status =
  | { kind: 'idle' }
  | { kind: 'uploading' }
  | { kind: 'success'; result: Submitted }
  | { kind: 'error'; message: string }

const STEPS = [
  {
    title: 'Wgraj wniosek',
    text: 'Dodaj plik PDF, Word lub skan z wnioskiem o udostępnienie informacji publicznej.',
  },
  {
    title: 'Analiza i podobne sprawy',
    text: 'Asystent odczyta treść, wskaże podobne wnioski z archiwum i właściwe wydziały.',
  },
  {
    title: 'Termin w kalendarzu',
    text: 'Wniosek trafi do rejestru z terminem odpowiedzi liczonym od daty wpływu.',
  },
  {
    title: 'Projekt odpowiedzi',
    text: 'Po wgraniu odpowiedzi z wydziałów powstanie projekt pisma z propozycją anonimizacji.',
  },
]

function App() {
  const [file, setFile] = useState<File | null>(null)
  const [rejection, setRejection] = useState<Rejection | null>(null)
  const [receivedAt, setReceivedAt] = useState(todayIso)
  const [status, setStatus] = useState<Status>({ kind: 'idle' })
  const [missingFile, setMissingFile] = useState(false)
  const confirmationRef = useRef<HTMLHeadingElement>(null)
  const ids = {
    date: useId(),
    dateHint: useId(),
    dateError: useId(),
    dropHint: useId(),
    drop: useId(),
    fileError: useId(),
  }

  // Upuszczenie pliku poza strefą nie powinno otwierać go w przeglądarce.
  useEffect(() => {
    const block = (e: DragEvent) => e.preventDefault()
    window.addEventListener('dragover', block)
    window.addEventListener('drop', block)
    return () => {
      window.removeEventListener('dragover', block)
      window.removeEventListener('drop', block)
    }
  }, [])

  useEffect(() => {
    if (status.kind === 'success') confirmationRef.current?.focus()
  }, [status.kind])

  const today = todayIso()
  const deadline = useMemo(() => deadlineFor(receivedAt), [receivedAt])
  const dateError = !deadline
    ? 'Podaj datę wpływu wniosku.'
    : receivedAt > today
      ? 'Data wpływu nie może być późniejsza niż dzisiejsza.'
      : null

  // Jeden wniosek = jeden plik.
  const addFiles = (files: File[]) => {
    setStatus({ kind: 'idle' })
    if (files.length > 1) {
      setRejection({ reason: 'Wybrano kilka plików naraz — dodaj tylko jeden plik wniosku.' })
      return
    }
    const [next] = files
    const reason = validateFile(next)
    if (reason) {
      setRejection({ name: next.name, reason })
      return
    }
    setFile(next)
    setRejection(null)
    setMissingFile(false)
  }

  const removeFile = () => {
    setFile(null)
    setRejection(null)
    setStatus({ kind: 'idle' })
    // Po usunięciu pliku fokus wraca do strefy dodawania.
    requestAnimationFrame(() => document.getElementById(ids.drop)?.focus())
  }

  const startNext = () => {
    setFile(null)
    setRejection(null)
    setMissingFile(false)
    setStatus({ kind: 'idle' })
    setReceivedAt(todayIso())
  }

  const uploading = status.kind === 'uploading'

  const submit = async (e?: { preventDefault: () => void }) => {
    e?.preventDefault()
    if (uploading) return
    // Wzorzec gov.pl: przycisk zawsze aktywny, błędy pokazywane przy polach po próbie wysłania.
    if (dateError) {
      document.getElementById(ids.date)?.focus()
      return
    }
    if (!file) {
      setMissingFile(true)
      document.getElementById(ids.drop)?.focus()
      return
    }
    setStatus({ kind: 'uploading' })
    try {
      const { id } = await uploadRequest({ file, receivedAt })
      setStatus({ kind: 'success', result: { fileName: file.name, receivedAt, id } })
      setFile(null)
      setRejection(null)
    } catch (err) {
      const message =
        err instanceof UploadError ? err.message : err instanceof Error ? err.message : 'Nieznany błąd.'
      setStatus({ kind: 'error', message })
    }
  }

  const currentStep = status.kind === 'success' ? 2 : 1

  return (
    <div className="page">
      <a className="skip-link" href="#tresc">
        Przejdź do treści
      </a>

      <header className="topbar">
        <div className="container topbar-inner">
          <div className="brand">
            <span className="brand-name">Asystent UDIP</span>
            <span className="brand-org">Urząd Miasta Bydgoszczy</span>
          </div>
          <span className="badge-local" title="Dane przetwarzane lokalnie w sieci urzędu">
            Tryb lokalny
          </span>
        </div>
      </header>

      <main id="tresc" className="container main">
        <section className="intro">
          <h1>Nowy wniosek o informację publiczną</h1>
          <p className="lead">
            Wgraj wniosek, a asystent przygotuje analizę, propozycję wydziałów i termin
            odpowiedzi. Ostateczną decyzję zawsze podejmuje urzędnik.
          </p>
        </section>

        <nav className="stepper" aria-label="Etapy obsługi wniosku">
          <p className="stepper-label">
            Krok {currentStep} z {STEPS.length}: <strong>{STEPS[currentStep - 1].title}</strong>
          </p>
          <ol>
            {STEPS.map((step, i) => {
              const n = i + 1
              const state = n < currentStep ? 'done' : n === currentStep ? 'current' : 'todo'
              return (
                <li
                  key={step.title}
                  className={`stepper-item is-${state}`}
                  aria-current={state === 'current' ? 'step' : undefined}
                >
                  <span className="visually-hidden">
                    {step.title}
                    {state === 'done' ? ' (zakończony)' : ''}
                  </span>
                </li>
              )
            })}
          </ol>
        </nav>

        {status.kind === 'success' ? (
          <Confirmation result={status.result} headingRef={confirmationRef} onNext={startNext} />
        ) : (
          <form className="intake" onSubmit={submit} aria-busy={uploading} noValidate>
            <div className={`field${dateError ? ' has-error' : ''}`}>
              <label className="field-label" htmlFor={ids.date}>
                Data wpływu
              </label>
              <p id={ids.dateHint} className="field-hint">
                Dzień, w którym wniosek wpłynął do urzędu. Od niego liczony jest termin odpowiedzi.
              </p>
              {dateError && (
                <p id={ids.dateError} className="field-error">
                  <span className="visually-hidden">Błąd: </span>
                  {dateError}
                </p>
              )}
              <div className="date-row">
                <input
                  id={ids.date}
                  className="input input-date"
                  type="date"
                  value={receivedAt}
                  max={today}
                  required
                  disabled={uploading}
                  aria-invalid={!!dateError}
                  aria-describedby={`${ids.dateHint}${dateError ? ` ${ids.dateError}` : ''}`}
                  onChange={(e) => {
                    setReceivedAt(e.target.value)
                    if (status.kind === 'error') setStatus({ kind: 'idle' })
                  }}
                />
                <DeadlineReadout receivedAt={receivedAt} valid={!dateError} />
              </div>
            </div>

            <section
              className={`field${missingFile && !file ? ' has-error' : ''}`}
              aria-labelledby="upload-heading"
            >
              <h2 id="upload-heading" className="field-label">
                Plik wniosku
              </h2>
              <p id={ids.dropHint} className="field-hint">
                Jeden plik: dokument PDF lub Word albo skan pisma (JPG, PNG, TIFF).
              </p>

              {missingFile && !file && (
                <p id={ids.fileError} className="field-error">
                  <span className="visually-hidden">Błąd: </span>
                  Dodaj plik wniosku.
                </p>
              )}

              {file ? (
                <div className="file-row" aria-live="polite">
                  <span className="file-ext">{extensionOf(file.name).slice(1).toUpperCase()}</span>
                  <span className="file-name" title={file.name}>
                    {file.name}
                  </span>
                  <span className="file-size">{formatSize(file.size)}</span>
                  <button
                    type="button"
                    className="link-button"
                    onClick={removeFile}
                    disabled={uploading}
                    aria-label={`Usuń plik ${file.name}`}
                  >
                    Usuń
                  </button>
                </div>
              ) : (
                <FileDropzone
                  id={ids.drop}
                  onFiles={addFiles}
                  disabled={uploading}
                  invalid={missingFile}
                  describedBy={`${ids.dropHint}${missingFile ? ` ${ids.fileError}` : ''}`}
                />
              )}

              <div aria-live="polite">
                {rejection && (
                  <div className="notice notice-warning">
                    <strong>Nie dodano pliku.</strong>
                    <p>
                      {rejection.name && <span className="notice-file">{rejection.name} — </span>}
                      {rejection.reason}
                    </p>
                  </div>
                )}
              </div>
            </section>

            {status.kind === 'error' && (
              <div className="notice notice-error" role="alert">
                <p>
                  <strong>Nie udało się przesłać pliku.</strong> {status.message}
                </p>
                <p>Plik pozostał w formularzu — możesz spróbować ponownie.</p>
                <button type="button" className="secondary-button" onClick={() => submit()}>
                  Spróbuj ponownie
                </button>
              </div>
            )}

            {status.kind !== 'error' && (
              <div className="actions">
                <button type="submit" className="primary-button" disabled={uploading}>
                  {uploading && <span className="spinner" aria-hidden="true" />}
                  {uploading ? 'Przesyłanie…' : 'Analizuj wniosek'}
                </button>
              </div>
            )}
            <p className="visually-hidden" role="status">
              {uploading ? 'Trwa przesyłanie pliku.' : ''}
            </p>
          </form>
        )}

        <section className="steps" aria-labelledby="steps-heading">
          <h2 id="steps-heading" className="section-title">
            Jak to działa
          </h2>
          <ol>
            {STEPS.map((step, i) => (
              <li key={step.title} className="step">
                <span className="step-num" aria-hidden="true">
                  {i + 1}
                </span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="footer">
        <div className="container">
          Narzędzie pomocnicze · nic nie jest wysyłane automatycznie do wydziałów ani wnioskodawców
        </div>
      </footer>
    </div>
  )
}

function DeadlineReadout({ receivedAt, valid }: { receivedAt: string; valid: boolean }) {
  const info = valid ? deadlineFor(receivedAt) : null
  if (!info) {
    return (
      <div className="deadline is-empty" aria-live="polite">
        <span className="deadline-label">Termin odpowiedzi</span>
        <span className="deadline-date">—</span>
      </div>
    )
  }
  const tone = info.remaining < 0 ? 'is-late' : info.remaining <= 3 ? 'is-near' : ''
  return (
    <div className={`deadline ${tone}`} aria-live="polite">
      <span className="deadline-label">Termin odpowiedzi</span>
      <span className="deadline-date">
        {formatLong(info.deadline)}, {formatWeekday(info.deadline)}
      </span>
      <span className="deadline-meta">
        {ANSWER_DAYS} dni od daty wpływu (art. 13 ust. 1 u.d.i.p.) · {remainingText(info.remaining)}
      </span>
      {info.nonWorkingDay && <ShiftNote day14={info.day14} nextWorking={info.nextWorking} />}
    </div>
  )
}

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

function ShiftNote({ day14, nextWorking }: { day14: Date; nextWorking: Date }) {
  return (
    <span className="deadline-shift">
      {capitalize(formatWeekday(day14))}, {formatLong(day14)}, to dzień wolny. Rejestr urzędu liczy termin
      jako 14. dzień od wpływu; według art. 57 § 4 KPA upłynąłby {formatLong(nextWorking)}. Bezpieczniej
      odpowiedzieć wcześniej.
    </span>
  )
}

function Confirmation({
  result,
  headingRef,
  onNext,
}: {
  result: Submitted
  headingRef: RefObject<HTMLHeadingElement | null>
  onNext: () => void
}) {
  const info = deadlineFor(result.receivedAt)
  return (
    <section className="confirmation" aria-labelledby="confirmation-heading">
      <div className="confirmation-head">
        <svg className="confirmation-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M5 12.5l4.5 4.5L19 7.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <div>
          <h2 id="confirmation-heading" ref={headingRef} tabIndex={-1}>
            Wniosek przyjęty do analizy
          </h2>
          <p role="status">Plik wniosku został przesłany do analizy.</p>
        </div>
      </div>

      <dl className="summary">
        {result.id && (
          <div>
            <dt>Numer w rejestrze</dt>
            <dd className="num">{result.id}</dd>
          </div>
        )}
        <div>
          <dt>Wniosek</dt>
          <dd>{result.fileName}</dd>
        </div>
        {info && (
          <>
            <div>
              <dt>Data wpływu</dt>
              <dd className="num">{formatShort(info.received)}</dd>
            </div>
            <div>
              <dt>Termin odpowiedzi</dt>
              <dd>
                <strong>
                  {formatLong(info.deadline)}, {formatWeekday(info.deadline)}
                </strong>
                <span className="summary-meta">{remainingText(info.remaining)}</span>
                {info.nonWorkingDay && <ShiftNote day14={info.day14} nextWorking={info.nextWorking} />}
              </dd>
            </div>
          </>
        )}
      </dl>

      <p className="confirmation-next">
        Asystent odczyta treść, wskaże podobne wnioski z archiwum i właściwe wydziały. Ostateczną
        decyzję zawsze podejmuje urzędnik.
      </p>

      <button type="button" className="primary-button" onClick={onNext}>
        Dodaj kolejny wniosek
      </button>
    </section>
  )
}

export default App
