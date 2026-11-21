import { useEffect, useId, useState } from 'react'
import { FileDropzone } from '../components/FileDropzone'
import { DepartmentsPanel, ExtensionPanel, StageTracker } from '../components/CaseParts'
import { DraftEditor } from '../components/DraftEditor'
import {
  ApiError,
  STATUS_LABELS,
  createLetter,
  departmentReply,
  getCase,
  listDepartments,
  listExternalEntities,
  updateStatus,
  type CaseDetail,
  type CaseStatus,
  type Department,
  type DraftResult,
  type ExternalEntity,
  type LetterKind,
} from '../lib/api'
import { formatIso, todayIso } from '../lib/deadline'
import { validateFile } from '../lib/files'

const errorText = (err: unknown) => (err instanceof ApiError || err instanceof Error ? err.message : 'Nieznany błąd.')

const DOC_LABELS: Record<string, string> = {
  wniosek: 'Wniosek',
  odpowiedz: 'Odpowiedź',
  kwerenda: 'Pismo — kwerenda',
  doprecyzowanie: 'Wezwanie do doprecyzowania',
  nie_dysponent: 'Pismo — brak dysponenta',
}

const URGENCY_TEXT: Record<string, string> = {
  overdue: 'Termin minął',
  today: 'Termin upływa dziś',
  tomorrow: 'Termin upływa jutro',
  soon: 'Termin w ciągu 3 dni',
}

export function CaseView({ id }: { id: number }) {
  const [data, setData] = useState<CaseDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)
  const [departments, setDepartments] = useState<Department[]>([])
  const [entities, setEntities] = useState<ExternalEntity[]>([])
  const [activeDraftId, setActiveDraftId] = useState<number | null>(null)
  const [draftWarning, setDraftWarning] = useState<string | null>(null)
  const reload = () => setVersion((v) => v + 1)

  useEffect(() => {
    let alive = true
    getCase(id)
      .then((d) => {
        if (!alive) return
        setData(d)
        setError(null)
      })
      .catch((err) => alive && setError(errorText(err)))
    return () => {
      alive = false
    }
  }, [id, version])

  useEffect(() => {
    let alive = true
    Promise.all([listDepartments(), listExternalEntities()])
      .then(([d, e]) => {
        if (!alive) return
        setDepartments(d.filter((x) => x.is_active))
        setEntities(e.filter((x) => x.is_active))
      })
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [])

  if (error) {
    return (
      <div className="notice notice-error" role="alert">
        <p>
          <strong>Nie udało się wczytać sprawy.</strong> {error}
        </p>
        <a href="#/rejestr">Wróć do rejestru</a>
      </div>
    )
  }
  if (!data) return <p className="field-hint">Wczytywanie sprawy…</p>

  const onDraft = (result: DraftResult) => {
    setActiveDraftId(result.draft_id)
    setDraftWarning(result.warning)
    reload()
    // Projekt pisma pojawia się niżej — przewijamy do niego.
    setTimeout(() => document.getElementById('draft-heading')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300)
  }
  const draft = data.drafts.find((d) => d.id === activeDraftId) ?? data.drafts[0] ?? null
  const nameOf = (code: string) => departments.find((d) => d.code === code)?.name ?? code
  const closed = data.status === 'odpowiedz_wyslana'

  return (
    <>
      <p className="breadcrumb">
        <a href="#/rejestr">Rejestr wniosków</a> / <span className="num">{data.case_number}</span>
      </p>

      <section className="intro">
        <h1 className="num">{data.case_number}</h1>
        <p className="lead">{data.subject}</p>
      </section>

      <StageTracker data={data} />

      {data.date_parse_warning && (
        <div className="notice notice-warning">
          <strong>Uwaga do danych z rejestru</strong>
          <p>{data.date_parse_warning}</p>
        </div>
      )}

      <section className="panel case-facts" aria-label="Dane sprawy">
        <dl className="facts">
          <div>
            <dt>Wnioskodawca</dt>
            <dd>
              {data.applicant || '—'}
              {data.applicant_contact && <span className="dd-sub">{data.applicant_contact}</span>}
            </dd>
          </div>
          <div>
            <dt>Data wpływu</dt>
            <dd className="num">{formatIso(data.received_date)}</dd>
          </div>
          <div>
            <dt>Termin odpowiedzi</dt>
            <dd className="num">
              <strong>{formatIso(data.deadline_date)}</strong>
              {!closed && data.days_remaining !== null && (
                <span className={`dd-sub urgency-text-${data.urgency}`}>
                  {URGENCY_TEXT[data.urgency] ??
                    `Pozostało dni: ${data.days_remaining}`}
                  {data.urgency === 'overdue' && ` (${-(data.days_remaining ?? 0)} dni)`}
                </span>
              )}
              {data.deadline_note && <span className="dd-sub">{data.deadline_note}</span>}
            </dd>
          </div>
          {data.response_date && (
            <div>
              <dt>Data odpowiedzi</dt>
              <dd className="num">
                {formatIso(data.response_date)}
                {data.answered_on_time === false && <span className="dd-sub urgency-text-overdue">po terminie</span>}
              </dd>
            </div>
          )}
          <div>
            <dt>Wydziały</dt>
            <dd>{data.departments.length ? data.departments.map((c) => `${c} — ${nameOf(c)}`).join('; ') : '—'}</dd>
          </div>
          <div>
            <dt>Osoba odpowiedzialna</dt>
            <dd>{data.initials || '—'}</dd>
          </div>
          {data.notes && (
            <div>
              <dt>Adnotacje</dt>
              <dd>{data.notes}</dd>
            </div>
          )}
        </dl>
        <StatusForm key={`${data.status}|${data.deadline_date}`} data={data} onSaved={reload} />
      </section>

      <DepartmentsPanel
        key={data.department_status.map((r) => r.code + r.status).join('|')}
        data={data}
        departments={departments}
        onChanged={reload}
      />

      {data.documents.length > 0 && (
        <section className="panel" aria-labelledby="docs-heading">
          <h2 id="docs-heading" className="panel-title">
            Dokumenty sprawy
          </h2>
          <ul className="doc-list">
            {data.documents.map((doc) => (
              <li key={doc.id}>
                <details>
                  <summary>
                    {DOC_LABELS[doc.kind] ?? doc.kind}
                    <span className="similar-meta num">
                      {' '}
                      {formatIso(doc.document_date)}
                      {doc.filename && ` · ${doc.filename}`}
                    </span>
                  </summary>
                  <p className="prewrap">{doc.text}</p>
                </details>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!closed && (
        <>
          <ReplyForm caseId={data.id} departments={departments} caseDepartments={data.departments} onDraft={onDraft} />
          <ExtensionPanel key={data.deadline_date} data={data} onDraft={onDraft} />
          <LetterForm caseId={data.id} departments={departments} entities={entities} receivedAt={data.received_date} onDraft={onDraft} />
        </>
      )}

      {data.department_replies.length > 0 && (
        <section className="panel" aria-labelledby="replies-heading">
          <h2 id="replies-heading" className="panel-title">
            Materiały z wydziałów ({data.department_replies.length})
          </h2>
          <ul className="doc-list">
            {data.department_replies.map((r) => (
              <li key={r.id}>
                <details>
                  <summary>
                    {r.department ? `${r.department} — ${nameOf(r.department)}` : 'Wydział'}
                    <span className="similar-meta">{r.filename && ` · ${r.filename}`}</span>
                  </summary>
                  <p className="prewrap">{r.text}</p>
                </details>
              </li>
            ))}
          </ul>
        </section>
      )}

      {draft && (
        <section className="panel" aria-labelledby="draft-heading">
          <div className="panel-head">
            <h2 id="draft-heading" className="panel-title">
              Projekt pisma
            </h2>
            {data.drafts.length > 1 && (
              <div className="field inline">
                <label className="field-label small" htmlFor="draft-pick">
                  Wersja
                </label>
                <select
                  id="draft-pick"
                  className="input select"
                  value={draft.id}
                  onChange={(e) => setActiveDraftId(Number(e.target.value))}
                >
                  {data.drafts.map((d) => (
                    <option key={d.id} value={d.id}>
                      {DOC_LABELS[d.kind] ?? d.kind} · {d.created_at.slice(0, 16).replace('T', ' ')}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          {draftWarning && (
            <div className="notice notice-warning">
              <p>{draftWarning}</p>
            </div>
          )}
          <DraftEditor
            key={draft.id}
            caseId={data.id}
            draft={draft}
            knownPeople={[data.applicant]}
            closed={closed}
            onChanged={reload}
          />
        </section>
      )}

      {data.events.length > 0 && (
        <section className="panel" aria-labelledby="events-heading">
          <h2 id="events-heading" className="panel-title">
            Historia sprawy
          </h2>
          <ol className="events">
            {data.events.map((e, i) => (
              <li key={i}>
                <span className="num">{e.created_at.slice(0, 16).replace('T', ' ')}</span> {e.event.replaceAll('_', ' ')}
                {e.detail && <span className="similar-meta"> — {e.detail}</span>}
              </li>
            ))}
          </ol>
        </section>
      )}
    </>
  )
}

function StatusForm({ data, onSaved }: { data: CaseDetail; onSaved: () => void }) {
  const [status, setStatus] = useState<CaseStatus>(data.status)
  const [deadline, setDeadline] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const changed = status !== data.status || !!deadline
  return (
    <form
      className="status-form"
      onSubmit={async (e) => {
        e.preventDefault()
        setBusy(true)
        setError(null)
        try {
          await updateStatus(data.id, status, deadline || null)
          setDeadline('')
          onSaved()
        } catch (err) {
          setError(errorText(err))
        } finally {
          setBusy(false)
        }
      }}
    >
      <div className="field">
        <label className="field-label small" htmlFor="status">
          Status sprawy
        </label>
        <select id="status" className="input select" value={status} onChange={(e) => setStatus(e.target.value as CaseStatus)}>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      {(status === 'kwerenda' || status === 'doprecyzowanie') && (
        <div className="field">
          <label className="field-label small" htmlFor="new-deadline">
            Nowy termin <span className="optional">(maks. 2 miesiące od wpływu)</span>
          </label>
          <input id="new-deadline" type="date" className="input input-date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
        </div>
      )}
      <button type="submit" className="secondary-button" disabled={busy || !changed}>
        {busy ? 'Zapisywanie…' : 'Zapisz status'}
      </button>
      {error && <p className="field-error">{error}</p>}
    </form>
  )
}

function ReplyForm({
  caseId,
  departments,
  caseDepartments,
  onDraft,
}: {
  caseId: number
  departments: Department[]
  caseDepartments: string[]
  onDraft: (r: DraftResult) => void
}) {
  const ids = { drop: useId(), hint: useId() }
  const [department, setDepartment] = useState(caseDepartments[0] ?? '')
  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState('')
  const [fileError, setFileError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const sorted = [...departments].sort((a, b) => Number(caseDepartments.includes(b.code)) - Number(caseDepartments.includes(a.code)))

  return (
    <section className="panel" aria-labelledby="reply-heading">
      <h2 id="reply-heading" className="panel-title">
        Odpowiedź z wydziału
      </h2>
      <p className="field-hint">
        Wgraj materiał przekazany przez wydział albo wklej jego treść. Asystent przygotuje projekt pisma w układzie
        BKS i wskaże dane do anonimizacji.
      </p>
      <form
        className="stack"
        onSubmit={async (e) => {
          e.preventDefault()
          if (!file && !text.trim()) {
            setError('Dołącz plik z odpowiedzią wydziału albo wklej jej treść.')
            return
          }
          setBusy(true)
          setError(null)
          try {
            const result = await departmentReply(caseId, { file, text, department })
            setFile(null)
            setText('')
            onDraft(result)
          } catch (err) {
            setError(errorText(err))
          } finally {
            setBusy(false)
          }
        }}
      >
        <div className="field">
          <label className="field-label small" htmlFor="reply-dept">
            Wydział
          </label>
          <select id="reply-dept" className="input select" value={department} onChange={(e) => setDepartment(e.target.value)}>
            <option value="">— nie wskazano —</option>
            {sorted.map((d) => (
              <option key={d.code} value={d.code}>
                {d.code} — {d.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <span className="field-label small" id={ids.hint}>
            Plik odpowiedzi (PDF, Word, skan)
          </span>
          {file ? (
            <div className="file-row">
              <span className="file-name">{file.name}</span>
              <button type="button" className="link-button" onClick={() => setFile(null)}>
                Usuń
              </button>
            </div>
          ) : (
            <FileDropzone
              id={ids.drop}
              onFiles={(files) => {
                const reason = validateFile(files[0])
                setFileError(reason)
                if (!reason) setFile(files[0])
              }}
              disabled={busy}
              invalid={!!fileError}
              describedBy={ids.hint}
              title="Przeciągnij i upuść odpowiedź wydziału tutaj"
            />
          )}
          {fileError && <p className="field-error">{fileError}</p>}
        </div>
        <div className="field">
          <label className="field-label small" htmlFor="reply-text">
            lub treść odpowiedzi
          </label>
          <textarea id="reply-text" className="input textarea" rows={5} value={text} onChange={(e) => setText(e.target.value)} />
        </div>
        {error && (
          <div className="notice notice-error" role="alert">
            <p>{error}</p>
          </div>
        )}
        <div className="actions">
          <button type="submit" className="primary-button" disabled={busy}>
            {busy && <span className="spinner" aria-hidden="true" />}
            {busy ? 'Przygotowywanie projektu…' : 'Przygotuj projekt odpowiedzi'}
          </button>
        </div>
      </form>
    </section>
  )
}

const LETTERS: { kind: LetterKind; label: string; hint: string }[] = [
  { kind: 'doprecyzowanie', label: 'Wezwanie do doprecyzowania', hint: 'Wnioskodawca ma 7 dni na doprecyzowanie; wyznaczasz nowy termin rozpatrzenia.' },
  { kind: 'nie_dysponent', label: 'Urząd nie jest dysponentem', hint: 'Wskazanie podmiotu, do którego wnioskodawca powinien się zwrócić (art. 4 ust. 3 u.d.i.p.).' },
]

function LetterForm({
  caseId,
  departments,
  entities,
  receivedAt,
  onDraft,
}: {
  caseId: number
  departments: Department[]
  entities: ExternalEntity[]
  receivedAt: string | null
  onDraft: (r: DraftResult) => void
}) {
  const [kind, setKind] = useState<LetterKind>('doprecyzowanie')
  const [deadline, setDeadline] = useState('')
  const [department, setDepartment] = useState('')
  const [details, setDetails] = useState('')
  const [entity, setEntity] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  return (
    <section className="panel" aria-labelledby="letter-heading">
      <h2 id="letter-heading" className="panel-title">
        Inne pisma w sprawie
      </h2>
      <form
        className="stack"
        onSubmit={async (e) => {
          e.preventDefault()
          setBusy(true)
          setError(null)
          try {
            const result = await createLetter(caseId, {
              kind,
              new_deadline: kind === 'nie_dysponent' ? null : deadline || null,
              department: kind === 'doprecyzowanie' ? department || null : null,
              details: kind === 'doprecyzowanie' ? details || null : null,
              external_entity_id: kind === 'nie_dysponent' && entity ? Number(entity) : null,
            })
            onDraft(result)
          } catch (err) {
            setError(errorText(err))
          } finally {
            setBusy(false)
          }
        }}
      >
        <fieldset className="field">
          <legend className="field-label small">Rodzaj pisma</legend>
          <ul className="choice-list">
            {LETTERS.map((l) => (
              <li key={l.kind}>
                <label className="choice">
                  <input type="radio" name="letter-kind" checked={kind === l.kind} onChange={() => setKind(l.kind)} />
                  <span>
                    <strong>{l.label}</strong>
                    <span className="choice-hint">{l.hint}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </fieldset>

        {kind !== 'nie_dysponent' && (
          <div className="field">
            <label className="field-label small" htmlFor="letter-deadline">
              Nowy termin <span className="optional">(puste — za 21 dni, maks. 2 miesiące od wpływu)</span>
            </label>
            <input
              id="letter-deadline"
              type="date"
              className="input input-date"
              min={todayIso()}
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
            />
            {receivedAt && <p className="field-hint">Data wpływu: {formatIso(receivedAt)}.</p>}
          </div>
        )}

        {kind === 'doprecyzowanie' && (
          <>
            <div className="field">
              <label className="field-label small" htmlFor="letter-dept">
                Komórka, która wnosi o doprecyzowanie
              </label>
              <select id="letter-dept" className="input select" value={department} onChange={(e) => setDepartment(e.target.value)}>
                <option value="">— wydział sprawy —</option>
                {departments.map((d) => (
                  <option key={d.code} value={d.code}>
                    {d.code} — {d.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label className="field-label small" htmlFor="letter-details">
                Czego ma dotyczyć doprecyzowanie
              </label>
              <textarea id="letter-details" className="input textarea" rows={3} value={details} onChange={(e) => setDetails(e.target.value)} />
            </div>
          </>
        )}

        {kind === 'nie_dysponent' && (
          <div className="field">
            <label className="field-label small" htmlFor="letter-entity">
              Podmiot właściwy
            </label>
            <select id="letter-entity" className="input select" value={entity} onChange={(e) => setEntity(e.target.value)}>
              <option value="">— uzupełnię w treści pisma —</option>
              {entities.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {error && (
          <div className="notice notice-error" role="alert">
            <p>{error}</p>
          </div>
        )}
        <div className="actions">
          <button type="submit" className="secondary-button" disabled={busy}>
            {busy ? 'Przygotowywanie…' : 'Przygotuj projekt pisma'}
          </button>
        </div>
      </form>
    </section>
  )
}
