import { useState, type ReactNode } from 'react'
import { BusyButton } from '../../components/BusyButton'
import { ErrorNotice, Notice } from '../../components/Notice'
import {
  anonymizePreview,
  generateDocument,
  markSent,
  type AnonymizationCandidate,
  type AnonymizationItem,
  type Draft,
} from '../../lib/api'
import { saveFile } from '../../lib/dom'
import { isInterimLetter } from '../../lib/domain'
import { useAction } from '../../lib/hooks'

type Props = {
  caseId: number
  draft: Draft
  /** Osoby znane ze sprawy (wnioskodawca) — ich dane są wskazywane do anonimizacji także po edycji treści. */
  knownPeople: string[]
  closed: boolean
  onChanged: () => void
}

type ExportFormat = 'docx' | 'pdf'

const decisionKey = (candidate: AnonymizationCandidate) => `${candidate.quote}|${candidate.category}`

/**
 * Projekt pisma z przeglądem anonimizacji. Szare podświetlenie to propozycja asystenta, czarne — fragment
 * zaakceptowany do zamaskowania. Maski nakłada backend przy eksporcie pliku i przy zapisie wysłanego pisma.
 */
export function DraftEditor({ caseId, draft, knownPeople, closed, onChanged }: Props) {
  const [content, setContent] = useState(closed && draft.final_text ? draft.final_text : draft.draft_text)
  const [candidates, setCandidates] = useState(closed ? [] : draft.anonymization_candidates)
  const [accepted, setAccepted] = useState<ReadonlySet<number>>(new Set())
  const [editText, setEditText] = useState<string | null>(null)
  const [confirmingSend, setConfirmingSend] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const { busy, error, run } = useAction()
  const editing = editText !== null
  const interim = isInterimLetter(draft.kind)

  const items: AnonymizationItem[] = candidates.map((candidate) => ({
    start: candidate.start,
    end: candidate.end,
    mask: candidate.mask,
    active: accepted.has(candidate.id),
  }))

  const act = <T,>(label: string, action: () => Promise<T>) => {
    setMessage(null)
    return run(action, label)
  }

  const toggle = (id: number) =>
    setAccepted((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const saveEdit = async (text: string) => {
    const next = await act('edit', () => anonymizePreview(text, knownPeople))
    if (!next) return
    // Decyzje urzędnika zostają dla fragmentów, które nadal występują w tekście.
    const keptDecisions = new Set(candidates.filter((candidate) => accepted.has(candidate.id)).map(decisionKey))
    setContent(text)
    setCandidates(next)
    setAccepted(new Set(next.filter((candidate) => keptDecisions.has(decisionKey(candidate))).map((candidate) => candidate.id)))
    setEditText(null)
  }

  const exportFile = async (format: ExportFormat) => {
    const file = await act(format, () =>
      generateDocument({ draft_id: draft.id, content, format, anonymization_items: items }),
    )
    if (!file) return
    saveFile(file.blob, file.filename)
    setMessage(`Pobrano ${file.filename}. Sprawdź pismo merytorycznie przed wysłaniem.`)
    onChanged()
  }

  const send = async () => {
    if (!(await act('send', () => markSent(caseId, draft.id, content, items)))) return
    setConfirmingSend(false)
    onChanged()
  }

  return (
    <div className="draft">
      <p className="field-hint">
        {draft.llm_used
          ? 'Projekt przygotowany przez model Gemini na podstawie materiałów wydziału. Sprawdź fakty, kwoty i daty.'
          : 'Projekt z szablonu pisma BKS — uzupełnij miejsca oznaczone [DO UZUPEŁNIENIA].'}
      </p>

      <div className="draft-grid">
        <div>
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
                onChange={(event) => setEditText(event.target.value)}
              />
              <div className="actions">
                <BusyButton type="button" busy={busy === 'edit'} busyLabel="Zapisywanie…" onClick={() => saveEdit(editText)}>
                  Zapisz zmiany
                </BusyButton>
                <button type="button" className="link-button" onClick={() => setEditText(null)}>
                  Anuluj
                </button>
              </div>
              <p className="field-hint">Po zapisaniu asystent ponownie wskaże dane do anonimizacji.</p>
            </>
          ) : (
            <div className="letter" aria-label="Treść pisma">
              {highlight(content, candidates, (candidate) => {
                const on = accepted.has(candidate.id)
                return (
                  <button
                    key={candidate.id}
                    type="button"
                    className={`anon ${on ? 'anon-on' : 'anon-off'}`}
                    aria-pressed={on}
                    title={`${candidate.category} — ${on ? 'kliknij, aby przywrócić' : 'kliknij, aby zaczernić'}`}
                    onClick={() => toggle(candidate.id)}
                  >
                    {content.slice(candidate.start, candidate.end)}
                  </button>
                )
              })}
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
                    onClick={() => setAccepted(new Set(candidates.filter((candidate) => candidate.active).map((candidate) => candidate.id)))}
                  >
                    Zaczernij propozycje
                  </button>
                  <button type="button" className="link-button" disabled={editing} onClick={() => setAccepted(new Set())}>
                    Odznacz wszystko
                  </button>
                </div>
                <ul className="anon-list">
                  {candidates.map((candidate) => (
                    <li key={candidate.id}>
                      <label className="choice">
                        <input
                          type="checkbox"
                          checked={accepted.has(candidate.id)}
                          disabled={editing}
                          onChange={() => toggle(candidate.id)}
                        />
                        <span>
                          <strong className="anon-quote">{candidate.quote}</strong>
                          <span className="choice-hint">{candidate.category}</span>
                          {!candidate.active && <span className="choice-hint">{candidate.reason}</span>}
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

      {error && <ErrorNotice message={error} />}
      {message && (
        <Notice tone="success">
          <p>{message}</p>
        </Notice>
      )}

      {!closed && !editing && (
        <div className="actions draft-actions">
          <BusyButton type="button" busy={busy === 'docx'} busyLabel="Generowanie…" disabled={busy !== null} onClick={() => exportFile('docx')}>
            Pobierz DOCX
          </BusyButton>
          <BusyButton
            type="button"
            variant="secondary"
            busy={busy === 'pdf'}
            busyLabel="Generowanie…"
            disabled={busy !== null}
            onClick={() => exportFile('pdf')}
          >
            Pobierz PDF
          </BusyButton>
          <button type="button" className="link-button" onClick={() => setEditText(content)}>
            Edytuj treść
          </button>
          {confirmingSend ? (
            <div className="confirm-send">
              <Notice tone="warning">
                <p>
                  {interim
                    ? 'Potwierdź, że pismo zostało wysłane do wnioskodawcy. Trafi do akt sprawy, sprawa pozostaje w toku.'
                    : 'Potwierdź, że odpowiedź została wysłana do wnioskodawcy. Sprawa zostanie zamknięta, a zanonimizowana treść trafi do archiwum podobnych spraw.'}
                </p>
                <div className="actions compact">
                  <BusyButton type="button" busy={busy === 'send'} busyLabel="Zapisywanie…" onClick={send}>
                    Tak, wysłano
                  </BusyButton>
                  <button type="button" className="link-button" onClick={() => setConfirmingSend(false)}>
                    Anuluj
                  </button>
                </div>
              </Notice>
            </div>
          ) : (
            <button type="button" className="link-button" onClick={() => setConfirmingSend(true)}>
              {interim ? 'Oznacz pismo jako wysłane' : 'Oznacz odpowiedź jako wysłaną'}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

/** Tekst pisma z wyróżnionymi propozycjami anonimizacji; z nakładających się propozycji pokazuje pierwszą. */
function highlight(
  content: string,
  candidates: AnonymizationCandidate[],
  render: (candidate: AnonymizationCandidate) => ReactNode,
): ReactNode[] {
  const nodes: ReactNode[] = []
  let position = 0
  for (const candidate of candidates.toSorted((a, b) => a.start - b.start)) {
    if (candidate.start < position) continue
    nodes.push(content.slice(position, candidate.start), render(candidate))
    position = candidate.end
  }
  nodes.push(content.slice(position))
  return nodes
}
