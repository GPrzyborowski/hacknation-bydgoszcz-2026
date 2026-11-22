import { useId, useState, type FormEvent } from 'react'
import { BusyButton } from '../../components/BusyButton'
import { FileDropzone } from '../../components/FileDropzone'
import { ErrorNotice, Notice } from '../../components/Notice'
import { analyzeRequest, errorMessage, type IntakeAnalysis } from '../../lib/api'
import { useFileRules } from '../../lib/config'
import { parseIso, todayIso } from '../../lib/dates'
import { focusById } from '../../lib/dom'
import { extensionOf, formatSize, validateFile } from '../../lib/files'
import { AnalysisPanel } from './AnalysisPanel'
import { DeadlineReadout } from './DeadlineReadout'

type Rejection = { fileName?: string; reason: string }

type Status =
  | { kind: 'idle' }
  | { kind: 'uploading' }
  | { kind: 'analyzed'; analysis: IntakeAnalysis; file: File; receivedAt: string }
  | { kind: 'error'; message: string }

const STEPS = [
  { title: 'Wgraj wniosek', text: 'Dodaj plik PDF, Word lub skan z wnioskiem o udostępnienie informacji publicznej.' },
  { title: 'Analiza i podobne sprawy', text: 'Asystent odczyta treść, wskaże podobne wnioski z archiwum i właściwe wydziały.' },
  { title: 'Termin w kalendarzu', text: 'Wniosek trafi do rejestru z terminem odpowiedzi liczonym od daty wpływu.' },
  { title: 'Projekt odpowiedzi', text: 'Po wgraniu odpowiedzi z wydziałów powstanie projekt pisma z propozycją anonimizacji.' },
]

export function IntakeView() {
  const rules = useFileRules('request')
  const [file, setFile] = useState<File | null>(null)
  const [rejection, setRejection] = useState<Rejection | null>(null)
  const [receivedAt, setReceivedAt] = useState(todayIso)
  const [status, setStatus] = useState<Status>({ kind: 'idle' })
  const [missingFile, setMissingFile] = useState(false)
  const ids = { date: useId(), dateHint: useId(), dateError: useId(), drop: useId(), dropHint: useId(), fileError: useId() }

  const today = todayIso()
  const dateError = !parseIso(receivedAt)
    ? 'Podaj datę wpływu wniosku.'
    : receivedAt > today
      ? 'Data wpływu nie może być późniejsza niż dzisiejsza.'
      : null
  const uploading = status.kind === 'uploading'
  const fileMissing = missingFile && !file

  const addFiles = (files: File[]) => {
    setStatus({ kind: 'idle' })
    if (files.length > 1) {
      setRejection({ reason: 'Wybrano kilka plików naraz — dodaj tylko jeden plik wniosku.' })
      return
    }
    const [next] = files
    const reason = validateFile(next, rules)
    if (reason) {
      setRejection({ fileName: next.name, reason })
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
    requestAnimationFrame(() => focusById(ids.drop))
  }

  const restart = () => {
    setFile(null)
    setRejection(null)
    setMissingFile(false)
    setStatus({ kind: 'idle' })
    setReceivedAt(todayIso())
  }

  // Wzorzec gov.pl: przycisk zawsze aktywny, a błędy pojawiają się przy polach po próbie wysłania.
  const submit = async (event?: FormEvent) => {
    event?.preventDefault()
    if (uploading) return
    if (dateError) return focusById(ids.date)
    if (!file) {
      setMissingFile(true)
      return focusById(ids.drop)
    }
    setStatus({ kind: 'uploading' })
    try {
      setStatus({ kind: 'analyzed', analysis: await analyzeRequest(file, receivedAt), file, receivedAt })
    } catch (failure) {
      setStatus({ kind: 'error', message: errorMessage(failure) })
    }
  }

  /** Ponowna analiza z treścią przepisaną przez urzędnika, gdy skan jest nieczytelny dla OCR. */
  const reanalyze = async (manualText: string) => {
    if (status.kind !== 'analyzed') return
    const analysis = await analyzeRequest(status.file, status.receivedAt, manualText)
    setStatus({ ...status, analysis })
  }

  const currentStep = status.kind === 'analyzed' ? 2 : 1

  return (
    <>
      <section className="intro">
        <h1>Nowy wniosek o informację publiczną</h1>
        <p className="lead">
          Wgraj wniosek, a asystent przygotuje analizę, propozycję wydziałów i termin odpowiedzi. Ostateczną decyzję
          zawsze podejmuje urzędnik.
        </p>
      </section>

      <nav className="stepper" aria-label="Etapy obsługi wniosku">
        <p className="stepper-label">
          Krok {currentStep} z {STEPS.length}: <strong>{STEPS[currentStep - 1].title}</strong>
        </p>
        <ol>
          {STEPS.map((step, index) => {
            const state = index + 1 < currentStep ? 'done' : index + 1 === currentStep ? 'current' : 'todo'
            return (
              <li key={step.title} className={`stepper-item is-${state}`} aria-current={state === 'current' ? 'step' : undefined}>
                <span className="visually-hidden">
                  {step.title}
                  {state === 'done' && ' (zakończony)'}
                </span>
              </li>
            )
          })}
        </ol>
      </nav>

      {status.kind === 'analyzed' ? (
        <AnalysisPanel
          key={status.analysis.intake_id}
          analysis={status.analysis}
          fileName={status.file.name}
          receivedAt={status.receivedAt}
          onReanalyze={reanalyze}
          onRestart={restart}
        />
      ) : (
        <form className="form" onSubmit={submit} aria-busy={uploading} noValidate>
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
                aria-describedby={dateError ? `${ids.dateHint} ${ids.dateError}` : ids.dateHint}
                onChange={(event) => {
                  setReceivedAt(event.target.value)
                  if (status.kind === 'error') setStatus({ kind: 'idle' })
                }}
              />
              <DeadlineReadout receivedAt={dateError ? null : receivedAt} />
            </div>
          </div>

          <section className={`field${fileMissing ? ' has-error' : ''}`} aria-labelledby={`${ids.drop}-heading`}>
            <h2 id={`${ids.drop}-heading`} className="field-label">
              Plik wniosku
            </h2>
            <p id={ids.dropHint} className="field-hint">
              Jeden plik: dokument albo skan pisma.
            </p>

            {fileMissing && (
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
                itemName="wniosek"
                rules={rules}
                onFiles={addFiles}
                disabled={uploading}
                invalid={missingFile}
                describedBy={fileMissing ? `${ids.dropHint} ${ids.fileError}` : ids.dropHint}
              />
            )}

            <div aria-live="polite">
              {rejection && (
                <Notice tone="warning" title="Nie dodano pliku.">
                  <p>
                    {rejection.fileName && <span className="notice-file">{rejection.fileName} — </span>}
                    {rejection.reason}
                  </p>
                </Notice>
              )}
            </div>
          </section>

          {status.kind === 'error' ? (
            <ErrorNotice title="Nie udało się przeanalizować wniosku." message={status.message}>
              <p>Plik pozostał w formularzu — możesz spróbować ponownie.</p>
              <button type="button" className="secondary-button" onClick={() => submit()}>
                Spróbuj ponownie
              </button>
            </ErrorNotice>
          ) : (
            <div className="actions">
              <BusyButton type="submit" busy={uploading} busyLabel="Analizowanie…">
                Analizuj wniosek
              </BusyButton>
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
            {STEPS.map((step, index) => (
              <li key={step.title} className="step">
                <span className="step-num" aria-hidden="true">
                  {index + 1}
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
