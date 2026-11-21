import { useState, type ReactNode } from 'react'
import {
  ApiError,
  anonymizePreview,
  generateDocument,
  markSent,
  type AnonymizationCandidate,
  type Draft,
} from '../lib/api'

type Props = {
  caseId: number
  draft: Draft
  knownPeople: string[]
  closed: boolean
  onChanged: () => void
}

const errorText = (err: unknown) => (err instanceof ApiError || err instanceof Error ? err.message : 'Nieznany błąd.')

/** Nakłada zaakceptowane maski (od końca, żeby nie przesuwać indeksów) — ta sama zasada co w backendzie. */
function redact(text: string, items: AnonymizationCandidate[], accepted: Set<number>): string {
  return [...items]
    .filter((c) => accepted.has(c.id))
    .sort((a, b) => b.start - a.start)
    .reduce((out, c) => out.slice(0, c.start) + c.mask + out.slice(c.end), text)
}

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function DraftEditor({ caseId, draft, knownPeople, closed, onChanged }: Props) {
  const [content, setContent] = useState(draft.final_text && closed ? draft.final_text : draft.draft_text)
  const [candidates, setCandidates] = useState<AnonymizationCandidate[]>(closed ? [] : draft.anonymization_candidates)
  // Szare = propozycja asystenta, czarne = zaakceptowane przez urzędnika. Na starcie wszystko szare.
  const [accepted, setAccepted] = useState<Set<number>>(new Set())
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [confirmSend, setConfirmSend] = useState(false)

  const toggle = (id: number) =>
    setAccepted((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const recommended = candidates.filter((c) => c.active)
  const isLetterInProgress = draft.kind === 'kwerenda' || draft.kind === 'doprecyzowanie'

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label)
    setError(null)
    setMessage(null)
    try {
      await fn()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  const saveEdit = () =>
    run('edit', async () => {
      const next = await anonymizePreview(editText, knownPeople)
      // Zachowujemy decyzje urzędnika dla fragmentów, które nadal występują w tekście.
      const acceptedQuotes = new Set(candidates.filter((c) => accepted.has(c.id)).map((c) => `${c.quote}|${c.category}`))
      setContent(editText)
      setCandidates(next)
      setAccepted(new Set(next.filter((c) => acceptedQuotes.has(`${c.quote}|${c.category}`)).map((c) => c.id)))
      setEditing(false)
    })

  const exportFile = (format: 'docx' | 'pdf') =>
    run(format, async () => {
      const { blob, filename } = await generateDocument({
        draft_id: draft.id,
        content,
        format,
        anonymization_items: candidates.map((c) => ({ start: c.start, end: c.end, mask: c.mask, active: accepted.has(c.id) })),
      })
      download(blob, filename)
      setMessage(`Pobrano ${filename}. Sprawdź pismo merytorycznie przed wysłaniem.`)
      onChanged()
    })

  const send = () =>
    run('send', async () => {
      await markSent(caseId, draft.id, redact(content, candidates, accepted))
      setConfirmSend(false)
      onChanged()
    })

  // Tekst z zaznaczeniami: szare tło = propozycja, czarne = zaakceptowana anonimizacja.
  const nodes: ReactNode[] = []
  let pos = 0
  for (const c of [...candidates].sort((a, b) => a.start - b.start)) {
    if (c.start < pos) continue
    nodes.push(content.slice(pos, c.start))
    const on = accepted.has(c.id)
    nodes.push(
      <button
        key={c.id}
        type="button"
        className={`anon ${on ? 'anon-on' : 'anon-off'}`}
        aria-pressed={on}
        title={`${c.category} — ${on ? 'kliknij, aby przywrócić' : 'kliknij, aby zaczernić'}`}
        disabled={closed || editing}
        onClick={() => toggle(c.id)}
      >
        {c.quote}
      </button>,
    )
    pos = c.end
  }
  nodes.push(content.slice(pos))

  return (
    <div className="draft">
      {draft.llm_used ? (
        <p className="field-hint">Projekt przygotowany przez model Gemini na podstawie materiałów wydziału. Sprawdź fakty, kwoty i daty.</p>
      ) : (
        <p className="field-hint">Projekt z szablonu pisma BKS — uzupełnij miejsca oznaczone [DO UZUPEŁNIENIA].</p>
      )}

      <div className="draft-grid">
        <div className="draft-text-col">
          {editing ? (
            <>
              <label className="visually-hidden" htmlFor="draft-edit">
                Treść pisma
              </label>
              <textarea
                id="draft-edit"
                className="input textarea draft-textarea"
                rows={18}
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
              />
              <div className="actions">
                <button type="button" className="primary-button" onClick={saveEdit} disabled={busy === 'edit'}>
                  {busy === 'edit' ? 'Zapisywanie…' : 'Zapisz zmiany'}
                </button>
                <button type="button" className="link-button" onClick={() => setEditing(false)}>
                  Anuluj
                </button>
              </div>
              <p className="field-hint">Po zapisaniu asystent ponownie wskaże dane do anonimizacji.</p>
            </>
          ) : (
            <div className="letter" aria-label="Treść pisma">
              {nodes}
            </div>
          )}
        </div>

        {!closed && (
          <aside className="anon-panel" aria-labelledby="anon-heading">
            <h3 id="anon-heading" className="subhead">
              Anonimizacja ({accepted.size} z {candidates.length})
            </h3>
            <p className="field-hint">
              <span className="anon anon-off legend">szare</span> — propozycja,{' '}
              <span className="anon anon-on legend">czarne</span> — zostanie ukryte w piśmie.
            </p>
            {candidates.length === 0 ? (
              <p className="field-hint">Asystent nie znalazł danych do anonimizacji.</p>
            ) : (
              <>
                <div className="actions compact">
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={editing}
                    onClick={() => setAccepted(new Set(recommended.map((c) => c.id)))}
                  >
                    Zaczernij propozycje
                  </button>
                  <button type="button" className="link-button" disabled={editing} onClick={() => setAccepted(new Set())}>
                    Odznacz wszystko
                  </button>
                </div>
                <ul className="anon-list">
                  {candidates.map((c) => (
                    <li key={c.id}>
                      <label className="choice">
                        <input type="checkbox" checked={accepted.has(c.id)} disabled={editing} onChange={() => toggle(c.id)} />
                        <span>
                          <strong className="anon-quote">{c.quote}</strong>
                          <span className="choice-hint">{c.category}</span>
                          {!c.active && <span className="choice-hint">{c.reason}</span>}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </aside>
        )}
      </div>

      {error && (
        <div className="notice notice-error" role="alert">
          <p>{error}</p>
        </div>
      )}
      {message && (
        <p className="notice notice-success" role="status">
          {message}
        </p>
      )}

      {!closed && !editing && (
        <div className="actions draft-actions">
          <button type="button" className="primary-button" onClick={() => exportFile('docx')} disabled={!!busy}>
            {busy === 'docx' && <span className="spinner" aria-hidden="true" />}
            Pobierz DOCX
          </button>
          <button type="button" className="secondary-button" onClick={() => exportFile('pdf')} disabled={!!busy}>
            {busy === 'pdf' ? 'Generowanie…' : 'Pobierz PDF'}
          </button>
          <button
            type="button"
            className="link-button"
            onClick={() => {
              setEditText(content)
              setEditing(true)
            }}
          >
            Edytuj treść
          </button>
          {!confirmSend ? (
            <button type="button" className="link-button" onClick={() => setConfirmSend(true)}>
              {isLetterInProgress ? 'Oznacz pismo jako wysłane' : 'Oznacz odpowiedź jako wysłaną'}
            </button>
          ) : (
            <div className="notice notice-warning confirm-send">
              <p>
                {isLetterInProgress
                  ? 'Potwierdź, że pismo zostało wysłane do wnioskodawcy. Trafi do akt sprawy, sprawa pozostaje w toku.'
                  : 'Potwierdź, że odpowiedź została wysłana do wnioskodawcy. Sprawa zostanie zamknięta, a zanonimizowana treść trafi do archiwum podobnych spraw.'}
              </p>
              <div className="actions compact">
                <button type="button" className="primary-button" onClick={send} disabled={busy === 'send'}>
                  {busy === 'send' ? 'Zapisywanie…' : 'Tak, wysłano'}
                </button>
                <button type="button" className="link-button" onClick={() => setConfirmSend(false)}>
                  Anuluj
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
