import { useId, useState, type FormEvent } from 'react'
import { BusyButton } from '../components/BusyButton'
import { ErrorNotice, Notice } from '../components/Notice'
import {
  importExcel,
  importRuleDocument,
  listCategories,
  listDepartments,
  listExternalEntities,
  listRules,
  setRuleActive,
  type Rule,
} from '../lib/api'
import { useFileRules } from '../lib/config'
import { formatsLabel, validateFile, type FileRules } from '../lib/files'
import { useAction, useQuery } from '../lib/hooks'

export function KnowledgeView() {
  const rules = useQuery(listRules)
  const categories = useQuery(listCategories)
  const entities = useQuery(listExternalEntities)
  const departments = useQuery(listDepartments)
  const ruleToggle = useAction()
  const error = rules.error ?? categories.error ?? entities.error ?? departments.error ?? ruleToggle.error

  const toggleRule = async (rule: Rule) => {
    const updated = await ruleToggle.run(() => setRuleActive(rule.id, !rule.is_active))
    if (updated) rules.setData((current) => current?.map((item) => (item.id === updated.id ? updated : item)) ?? null)
  }

  return (
    <>
      <section className="intro">
        <h1>Baza wiedzy</h1>
        <p className="lead">
          Przepisy, zarządzenia, archiwum spraw i zasady anonimizacji, z których korzysta asystent. Zmiany działają od razu
          przy kolejnych wnioskach.
        </p>
      </section>

      {error && <ErrorNotice title="Nie udało się wczytać bazy wiedzy." message={error} />}

      <div className="kb-imports">
        <ExcelImport />
        <RuleImport onImported={rules.reload} />
      </div>

      <section className="panel" aria-labelledby="rules-heading">
        <h2 id="rules-heading" className="panel-title">
          Przepisy i zarządzenia {rules.data && <span className="meta num">({rules.data.length})</span>}
        </h2>
        <p className="field-hint">Wyłączony przepis nie jest brany pod uwagę przy przygotowaniu projektów pism.</p>
        {!rules.data ? (
          <p className="field-hint">Wczytywanie…</p>
        ) : (
          <ul className="doc-list">
            {rules.data.map((rule) => (
              <li key={rule.id} className={rule.is_active ? undefined : 'is-inactive'}>
                <details>
                  <summary>
                    {rule.title}
                    <span className="meta"> · {rule.source}</span>
                    {!rule.is_active && <span className="meta"> · wyłączony</span>}
                  </summary>
                  <p className="prewrap">{rule.content}</p>
                  <button type="button" className="link-button" disabled={ruleToggle.busy !== null} onClick={() => toggleRule(rule)}>
                    {rule.is_active ? 'Wyłącz przepis' : 'Włącz przepis'}
                  </button>
                </details>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel" aria-labelledby="categories-heading">
        <h2 id="categories-heading" className="panel-title">
          Dane podlegające anonimizacji <span className="meta num">({categories.data?.length ?? 0})</span>
        </h2>
        <p className="field-hint">
          Lista według wytycznych urzędu. Kategorie z wzorcem są wykrywane automatycznie, pozostałe wskazuje model.
        </p>
        <table className="data-table compact-table">
          <thead>
            <tr>
              <th scope="col">Kategoria</th>
              <th scope="col">Podstawa</th>
              <th scope="col">Wykrywanie</th>
            </tr>
          </thead>
          <tbody>
            {categories.data?.map((category) => (
              <tr key={category.id}>
                <td>{category.name}</td>
                <td>{category.legal_basis}</td>
                <td>{category.regex ? 'wzorzec + model' : 'model / urzędnik'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel" aria-labelledby="entities-heading">
        <h2 id="entities-heading" className="panel-title">
          Podmioty spoza urzędu
        </h2>
        <p className="field-hint">Używane w piśmie „urząd nie jest dysponentem informacji”.</p>
        <ul className="doc-list">
          {entities.data?.map((entity) => (
            <li key={entity.id}>
              <details>
                <summary>{entity.name}</summary>
                <p className="prewrap">{entity.contact}</p>
              </details>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel" aria-labelledby="departments-heading">
        <h2 id="departments-heading" className="panel-title">
          Wydziały i biura <span className="meta num">({departments.data?.length ?? 0})</span>
        </h2>
        <table className="data-table compact-table">
          <thead>
            <tr>
              <th scope="col">Symbol</th>
              <th scope="col">Nazwa</th>
              <th scope="col">Zakres (słowa kluczowe do podpowiedzi)</th>
            </tr>
          </thead>
          <tbody>
            {departments.data?.map((department) => (
              <tr key={department.code}>
                <td className="nowrap">
                  <strong>{department.code}</strong>
                </td>
                <td>{department.name}</td>
                <td className="muted-cell">{department.keywords}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  )
}

/** Wybór jednego pliku z kontrolą formatu i rozmiaru. */
function FilePicker({ rules, file, onFile }: { rules: FileRules; file: File | null; onFile: (file: File | null) => void }) {
  const id = useId()
  const [problem, setProblem] = useState<string | null>(null)

  return (
    <div className="field">
      <div className="file-pick">
        <input
          id={id}
          type="file"
          accept={rules.extensions.join(',')}
          className="file-input"
          onChange={(event) => {
            const picked = event.target.files?.[0] ?? null
            const reason = picked && validateFile(picked, rules)
            event.target.value = ''
            setProblem(reason)
            onFile(reason ? null : picked)
          }}
        />
        <label htmlFor={id} className="secondary-button">
          Wybierz plik
        </label>
        <span className="file-name">{file ? file.name : 'Nie wybrano pliku'}</span>
      </div>
      {problem && <p className="field-error">{problem}</p>}
    </div>
  )
}

function ExcelImport() {
  const rules = useFileRules('spreadsheet')
  const [file, setFile] = useState<File | null>(null)
  const [summary, setSummary] = useState<{ text: string; warnings: string[] } | null>(null)
  const { busy, error, setError, run } = useAction()

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!file) return setError(`Wybierz plik ${formatsLabel(rules.extensions)}.`)
    const result = await run(() => importExcel(file))
    if (!result) return
    setSummary({
      text: `Dodano ${result.imported}, zaktualizowano ${result.updated}, pominięto ${result.skipped}.`,
      warnings: result.warnings,
    })
  }

  return (
    <section className="panel" aria-labelledby="excel-heading">
      <h2 id="excel-heading" className="panel-title">
        Import rejestru z Excela
      </h2>
      <p className="field-hint">
        Arkusz jak „WNIOSKI O UDOSTĘPNIANIE INFORMACJI PUBLICZNEJ.xlsx”. Kolumny rozpoznawane po nagłówkach.
      </p>
      <form className="stack" onSubmit={submit}>
        <FilePicker rules={rules} file={file} onFile={setFile} />
        {error && <p className="field-error">{error}</p>}
        {summary && (
          <Notice tone="success">
            <p>{summary.text}</p>
            {summary.warnings.length > 0 && (
              <ul>
                {summary.warnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            )}
          </Notice>
        )}
        <div className="actions">
          <BusyButton type="submit" busy={busy !== null} busyLabel="Importowanie…">
            Importuj rejestr
          </BusyButton>
        </div>
      </form>
    </section>
  )
}

function RuleImport({ onImported }: { onImported: () => void }) {
  const rules = useFileRules('knowledge')
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [source, setSource] = useState('')
  const [result, setResult] = useState<string | null>(null)
  const { busy, error, setError, run } = useAction()
  const ids = { title: useId(), source: useId() }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!file) return setError('Wybierz plik z aktem prawnym.')
    const added = await run(() => importRuleDocument(file, title, source))
    if (!added) return
    setResult(`Dodano ${added.length} ${added.length === 1 ? 'wpis' : 'wpisów'} do bazy przepisów.`)
    setFile(null)
    setTitle('')
    setSource('')
    onImported()
  }

  return (
    <section className="panel" aria-labelledby="rule-import-heading">
      <h2 id="rule-import-heading" className="panel-title">
        Nowa ustawa lub zarządzenie
      </h2>
      <p className="field-hint">{formatsLabel(rules.extensions)}. Akt zostanie podzielony na artykuły i paragrafy.</p>
      <form className="stack" onSubmit={submit}>
        <FilePicker rules={rules} file={file} onFile={setFile} />
        <div className="field">
          <label className="field-label small" htmlFor={ids.title}>
            Tytuł <span className="optional">(opcjonalnie)</span>
          </label>
          <input id={ids.title} className="input" value={title} onChange={(event) => setTitle(event.target.value)} />
        </div>
        <div className="field">
          <label className="field-label small" htmlFor={ids.source}>
            Źródło <span className="optional">(np. Dz. U. 2022 poz. 902)</span>
          </label>
          <input id={ids.source} className="input" value={source} onChange={(event) => setSource(event.target.value)} />
        </div>
        {error && <p className="field-error">{error}</p>}
        {result && (
          <Notice tone="success">
            <p>{result}</p>
          </Notice>
        )}
        <div className="actions">
          <BusyButton type="submit" busy={busy !== null} busyLabel="Importowanie…">
            Dodaj do bazy
          </BusyButton>
        </div>
      </form>
    </section>
  )
}
