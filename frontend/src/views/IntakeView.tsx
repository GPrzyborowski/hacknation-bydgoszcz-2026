import { useEffect, useId, useMemo, useState } from 'react'
import { FileDropzone } from '../components/FileDropzone'
import { ApiError, analyzeRequest, type IntakeAnalysis } from '../lib/api'
import { ANSWER_DAYS, deadlineFor, formatLong, formatWeekday, remainingText, todayIso } from '../lib/deadline'
import { extensionOf, formatSize, validateFile } from '../lib/files'
import { AnalysisPanel } from './AnalysisPanel'
import { ShiftNote } from '../components/ShiftNote'

type Rejection = { name?: string; reason: string }

type Status =
  | { kind: 'idle' }
  | { kind: 'uploading' }
  | { kind: 'analyzed'; analysis: IntakeAnalysis; file: File; receivedAt: string }
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

const errorText = (err: unknown) => (err instanceof ApiError || err instanceof Error ? err.message : 'Nieznany błąd.')

export function IntakeView() {
  const [file, setFile] = useState<File | null>(null)
  const [rejection, setRejection] = useState<Rejection | null>(null)
  const [receivedAt, setReceivedAt] = useState(todayIso)
  const [status, setStatus] = useState<Status>({ kind: 'idle' })
  const [missingFile, setMissingFile] = useState(false)
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
      const analysis = await analyzeRequest({ file, receivedAt })
      setStatus({ kind: 'analyzed', analysis, file, receivedAt })
    } catch (err) {
      setStatus({ kind: 'error', message: errorText(err) })
    }
  }

  /** Ponowna analiza z treścią wpisaną ręcznie (skan nieczytelny dla OCR). */
  const reanalyze = async (manualText: string) => {
    if (status.kind !== 'analyzed') return
    const analysis = await analyzeRequest({ file: status.file, receivedAt: status.receivedAt, manualText })
    setStatus({ ...status, analysis })
  }

  const currentStep = status.kind === 'analyzed' ? 2 : 1

  return (
    <>
      <section className="intro">
        <h1>Nowy wniosek o informację publiczną</h1>
        <p className="lead">
          Wgraj wniosek, a asystent przygotuje analizę, propozycję wydziałów i termin odpowiedzi. Ostateczną
          decyzję zawsze podejmuje urzędnik.
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

      {status.kind === 'analyzed' ? (
        <AnalysisPanel
          analysis={status.analysis}
          fileName={status.file.name}
          receivedAt={status.receivedAt}
          onReanalyze={reanalyze}
          onCancel={startNext}
        />
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

          <section className={`field${missingFile && !file ? ' has-error' : ''}`} aria-labelledby="upload-heading">
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
                <strong>Nie udało się przeanalizować wniosku.</strong> {status.message}
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
                {uploading ? 'Analizowanie…' : 'Analizuj wniosek'}
              </button>
              {uploading && (
                <span className="field-hint">Odczyt dokumentu i analiza trwają zwykle kilka sekund, skan do kilkunastu.</span>
              )}
            </div>
          )}
          <p className="visually-hidden" role="status">
            {uploading ? 'Trwa analiza wniosku.' : ''}
          </p>
        </form>
      )}

      {status.kind !== 'analyzed' && (
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
      )}
    </>
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
