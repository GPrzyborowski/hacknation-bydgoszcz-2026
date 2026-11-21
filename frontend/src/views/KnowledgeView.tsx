import { useEffect, useState } from 'react'
import {
  ApiError,
  importExcel,
  importRuleDocument,
  listCategories,
  listDepartments,
  listExternalEntities,
  listRules,
  setRuleActive,
  type Category,
  type Department,
  type ExternalEntity,
  type Rule,
} from '../lib/api'

const errorText = (err: unknown) => (err instanceof ApiError || err instanceof Error ? err.message : 'Nieznany błąd.')

export function KnowledgeView() {
  const [rules, setRules] = useState<Rule[] | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [entities, setEntities] = useState<ExternalEntity[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [version, setVersion] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    Promise.all([listRules(), listCategories(), listExternalEntities(), listDepartments()])
      .then(([r, c, e, d]) => {
        if (!alive) return
        setRules(r)
        setCategories(c)
        setEntities(e)
        setDepartments(d)
      })
      .catch((err) => alive && setError(errorText(err)))
    return () => {
      alive = false
    }
  }, [version])

  const reload = () => setVersion((v) => v + 1)

  return (
    <>
      <section className="intro">
        <h1>Baza wiedzy</h1>
        <p className="lead">
          Przepisy, zarządzenia, archiwum spraw i zasady anonimizacji, z których korzysta asystent. Zmiany działają od
          razu przy kolejnych wnioskach.
        </p>
      </section>

      {error && (
        <div className="notice notice-error" role="alert">
          <p>
            <strong>Nie udało się wczytać bazy wiedzy.</strong> {error}
          </p>
        </div>
      )}

      <div className="kb-imports">
        <ExcelImport onDone={reload} />
        <RuleImport onDone={reload} />
      </div>

      <section className="panel" aria-labelledby="rules-heading">
        <h2 id="rules-heading" className="panel-title">
          Przepisy i zarządzenia {rules && <span className="similar-meta num">({rules.length})</span>}
        </h2>
        <p className="field-hint">Wyłączony przepis nie jest brany pod uwagę przy przygotowaniu projektów pism.</p>
        {!rules ? (
          <p className="field-hint">Wczytywanie…</p>
        ) : (
          <ul className="doc-list">
            {rules.map((r) => (
              <li key={r.id} className={r.is_active ? '' : 'is-inactive'}>
                <details>
                  <summary>
                    {r.title}
                    <span className="similar-meta"> · {r.source}</span>
                    {!r.is_active && <span className="similar-meta"> · wyłączony</span>}
                  </summary>
                  <p className="prewrap">{r.content}</p>
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => setRuleActive(r.id, !r.is_active).then(reload).catch((err) => setError(errorText(err)))}
                  >
                    {r.is_active ? 'Wyłącz przepis' : 'Włącz przepis'}
                  </button>
                </details>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel" aria-labelledby="cats-heading">
        <h2 id="cats-heading" className="panel-title">
          Dane podlegające anonimizacji <span className="similar-meta num">({categories.length})</span>
        </h2>
        <p className="field-hint">Lista według wytycznych urzędu. Kategorie z wzorcem są wykrywane automatycznie, pozostałe wskazuje model.</p>
        <table className="register compact-table">
          <thead>
            <tr>
              <th scope="col">Kategoria</th>
              <th scope="col">Podstawa</th>
              <th scope="col">Wykrywanie</th>
            </tr>
          </thead>
          <tbody>
            {categories.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.legal_basis}</td>
                <td>{c.regex ? 'wzorzec + model' : 'model / urzędnik'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel" aria-labelledby="ents-heading">
        <h2 id="ents-heading" className="panel-title">
          Podmioty spoza urzędu
        </h2>
        <p className="field-hint">Używane w piśmie „urząd nie jest dysponentem informacji”.</p>
        <ul className="doc-list">
          {entities.map((e) => (
            <li key={e.id}>
              <details>
                <summary>{e.name}</summary>
                <p className="prewrap">{e.contact}</p>
              </details>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel" aria-labelledby="depts-heading">
        <h2 id="depts-heading" className="panel-title">
          Wydziały i biura <span className="similar-meta num">({departments.length})</span>
        </h2>
        <table className="register compact-table">
          <thead>
            <tr>
              <th scope="col">Symbol</th>
              <th scope="col">Nazwa</th>
              <th scope="col">Zakres (słowa kluczowe do podpowiedzi)</th>
            </tr>
          </thead>
          <tbody>
            {departments.map((d) => (
              <tr key={d.code}>
                <td className="nowrap">
                  <strong>{d.code}</strong>
                </td>
                <td>{d.name}</td>
                <td className="muted-cell">{d.keywords}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  )
}

function FilePick({ id, accept, file, onFile }: { id: string; accept: string; file: File | null; onFile: (f: File | null) => void }) {
  return (
    <div className="file-pick">
      <input id={id} type="file" accept={accept} className="file-input" onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
      <label htmlFor={id} className="secondary-button">
        Wybierz plik
      </label>
      <span className="file-name">{file ? file.name : 'Nie wybrano pliku'}</span>
    </div>
  )
}

function ExcelImport({ onDone }: { onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  return (
    <section className="panel" aria-labelledby="xlsx-heading">
      <h2 id="xlsx-heading" className="panel-title">
        Import rejestru z Excela
      </h2>
      <p className="field-hint">Arkusz jak „WNIOSKI O UDOSTĘPNIANIE INFORMACJI PUBLICZNEJ.xlsx”. Kolumny rozpoznawane po nagłówkach.</p>
      <form
        className="stack"
        onSubmit={async (e) => {
          e.preventDefault()
          if (!file) return setError('Wybierz plik .xlsx.')
          setBusy(true)
          setError(null)
          try {
            const r = await importExcel(file)
            setResult(`Dodano ${r.imported}, zaktualizowano ${r.updated}, pominięto ${r.skipped}.`)
            setWarnings(r.warnings)
            onDone()
          } catch (err) {
            setError(errorText(err))
          } finally {
            setBusy(false)
          }
        }}
      >
        <FilePick id="xlsx-file" accept=".xlsx,.xlsm" file={file} onFile={setFile} />
        {error && <p className="field-error">{error}</p>}
        {result && (
          <p className="notice notice-success" role="status">
            {result}
          </p>
        )}
        {warnings.length > 0 && (
          <ul className="field-hint">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        )}
        <div className="actions">
          <button type="submit" className="primary-button" disabled={busy}>
            {busy ? 'Importowanie…' : 'Importuj rejestr'}
          </button>
        </div>
      </form>
    </section>
  )
}

function RuleImport({ onDone }: { onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [source, setSource] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  return (
    <section className="panel" aria-labelledby="rule-heading">
      <h2 id="rule-heading" className="panel-title">
        Nowa ustawa lub zarządzenie
      </h2>
      <p className="field-hint">PDF, Word lub TXT. Akt zostanie podzielony na artykuły i paragrafy.</p>
      <form
        className="stack"
        onSubmit={async (e) => {
          e.preventDefault()
          if (!file) return setError('Wybierz plik z aktem prawnym.')
          setBusy(true)
          setError(null)
          try {
            const r = await importRuleDocument(file, title, source)
            setResult(`Dodano ${r.length} ${r.length === 1 ? 'wpis' : 'wpisów'} do bazy przepisów.`)
            setFile(null)
            setTitle('')
            setSource('')
            onDone()
          } catch (err) {
            setError(errorText(err))
          } finally {
            setBusy(false)
          }
        }}
      >
        <FilePick id="rule-file" accept=".pdf,.docx,.doc,.txt" file={file} onFile={setFile} />
        <div className="field">
          <label className="field-label small" htmlFor="rule-title">
            Tytuł <span className="optional">(opcjonalnie)</span>
          </label>
          <input id="rule-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label small" htmlFor="rule-source">
            Źródło <span className="optional">(np. Dz. U. 2022 poz. 902)</span>
          </label>
          <input id="rule-source" className="input" value={source} onChange={(e) => setSource(e.target.value)} />
        </div>
        {error && <p className="field-error">{error}</p>}
        {result && (
          <p className="notice notice-success" role="status">
            {result}
          </p>
        )}
        <div className="actions">
          <button type="submit" className="primary-button" disabled={busy}>
            {busy ? 'Importowanie…' : 'Dodaj do bazy'}
          </button>
        </div>
      </form>
    </section>
  )
}
