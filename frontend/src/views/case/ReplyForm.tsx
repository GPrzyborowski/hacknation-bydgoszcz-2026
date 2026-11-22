import { useId, useState, type FormEvent } from 'react'
import { BusyButton } from '../../components/BusyButton'
import { FileDropzone } from '../../components/FileDropzone'
import { ErrorNotice } from '../../components/Notice'
import { departmentReply, type DraftResult } from '../../lib/api'
import { useFileRules } from '../../lib/config'
import { deptLabel } from '../../lib/domain'
import { validateFile } from '../../lib/files'
import { useAction, useDepartments } from '../../lib/hooks'

type Props = { caseId: number; caseDepartments: string[]; onDraft: (result: DraftResult) => void }

/** Materiał z wydziału (plik lub wklejona treść) → projekt odpowiedzi w układzie pism urzędu. */
export function ReplyForm({ caseId, caseDepartments, onDraft }: Props) {
  const rules = useFileRules('request')
  const { departments } = useDepartments()
  const [department, setDepartment] = useState(caseDepartments[0] ?? '')
  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState('')
  const [fileError, setFileError] = useState<string | null>(null)
  const { busy, error, setError, run } = useAction()
  const ids = { department: useId(), drop: useId(), fileLabel: useId(), text: useId() }
  const ordered = departments.toSorted(
    (a, b) => Number(caseDepartments.includes(b.code)) - Number(caseDepartments.includes(a.code)),
  )

  const pickFile = ([first]: File[]) => {
    const reason = validateFile(first, rules)
    setFileError(reason)
    if (!reason) setFile(first)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!file && !text.trim()) return setError('Dołącz plik z odpowiedzią wydziału albo wklej jej treść.')
    const result = await run(() => departmentReply(caseId, { file, text, department }))
    if (!result) return
    setFile(null)
    setText('')
    onDraft(result)
  }

  return (
    <section className="panel" aria-labelledby="reply-heading">
      <h2 id="reply-heading" className="panel-title">
        Odpowiedź z wydziału
      </h2>
      <p className="field-hint">
        Wgraj materiał przekazany przez wydział albo wklej jego treść. Asystent przygotuje projekt pisma w układzie BKS
        i wskaże dane do anonimizacji.
      </p>
      <form className="stack" onSubmit={submit}>
        <div className="field">
          <label className="field-label small" htmlFor={ids.department}>
            Wydział
          </label>
          <select
            id={ids.department}
            className="input select"
            value={department}
            onChange={(event) => setDepartment(event.target.value)}
          >
            <option value="">— nie wskazano —</option>
            {ordered.map((item) => (
              <option key={item.code} value={item.code}>
                {deptLabel(item.code, item.name)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <span className="field-label small" id={ids.fileLabel}>
            Plik odpowiedzi
          </span>
          {file ? (
            <div className="file-row">
              <span className="file-name">{file.name}</span>
              <button type="button" className="link-button" onClick={() => setFile(null)} aria-label={`Usuń plik ${file.name}`}>
                Usuń
              </button>
            </div>
          ) : (
            <FileDropzone
              id={ids.drop}
              itemName="odpowiedź wydziału"
              rules={rules}
              onFiles={pickFile}
              disabled={busy !== null}
              invalid={!!fileError}
              describedBy={ids.fileLabel}
            />
          )}
          {fileError && <p className="field-error">{fileError}</p>}
        </div>
        <div className="field">
          <label className="field-label small" htmlFor={ids.text}>
            lub treść odpowiedzi
          </label>
          <textarea id={ids.text} className="input textarea" rows={5} value={text} onChange={(event) => setText(event.target.value)} />
        </div>
        {error && <ErrorNotice message={error} />}
        <div className="actions">
          <BusyButton type="submit" busy={busy !== null} busyLabel="Przygotowywanie projektu…">
            Przygotuj projekt odpowiedzi
          </BusyButton>
        </div>
      </form>
    </section>
  )
}
