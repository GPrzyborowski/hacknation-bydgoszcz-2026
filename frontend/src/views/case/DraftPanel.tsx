import { useId, type Ref } from 'react'
import { Notice } from '../../components/Notice'
import type { CaseDetail } from '../../lib/api'
import { formatTimestamp } from '../../lib/dates'
import { DOCUMENT_LABELS, isClosed } from '../../lib/domain'
import { DraftEditor } from './DraftEditor'

/** Wybrana wersja projektu i ostrzeżenie zwrócone przy jej przygotowaniu (np. spóźniona kwerenda). */
export type DraftFocus = { id: number; warning: string | null }

type Props = {
  ref: Ref<HTMLElement>
  data: CaseDetail
  focus: DraftFocus | null
  onSelect: (draftId: number) => void
  onChanged: () => void
}

export function DraftPanel({ ref, data, focus, onSelect, onChanged }: Props) {
  const versionId = useId()
  const draft = data.drafts.find((item) => item.id === focus?.id) ?? data.drafts[0]
  const warning = focus?.id === draft.id ? focus.warning : null
  const closed = isClosed(data.status)

  return (
    <section ref={ref} className="panel" aria-labelledby="draft-heading">
      <div className="panel-head">
        <h2 id="draft-heading" className="panel-title">
          Projekt pisma
        </h2>
        {data.drafts.length > 1 && (
          <div className="field inline">
            <label className="field-label small" htmlFor={versionId}>
              Wersja
            </label>
            <select
              id={versionId}
              className="input select"
              value={draft.id}
              onChange={(event) => onSelect(Number(event.target.value))}
            >
              {data.drafts.map((item) => (
                <option key={item.id} value={item.id}>
                  {DOCUMENT_LABELS[item.kind]} · {formatTimestamp(item.created_at)}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      {warning && (
        <Notice tone="warning">
          <p>{warning}</p>
        </Notice>
      )}
      {/* Po zamknięciu sprawy edytor startuje od nowa i pokazuje zapisaną, zanonimizowaną treść pisma. */}
      <DraftEditor
        key={`${draft.id}:${closed}`}
        caseId={data.id}
        draft={draft}
        knownPeople={[data.applicant]}
        closed={closed}
        onChanged={onChanged}
      />
    </section>
  )
}
