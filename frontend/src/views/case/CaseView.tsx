import { useEffect, useRef, useState } from 'react'
import { ErrorNotice, Notice } from '../../components/Notice'
import { getCase, type DraftResult } from '../../lib/api'
import { isClosed } from '../../lib/domain'
import { useQuery } from '../../lib/hooks'
import { hrefFor } from '../../lib/router'
import { CaseFacts } from './CaseFacts'
import { CaseDocuments, CaseHistory, DepartmentMaterials } from './CaseRecords'
import { DepartmentsPanel } from './DepartmentsPanel'
import { DraftPanel, type DraftFocus } from './DraftPanel'
import { ExtensionPanel } from './ExtensionPanel'
import { LetterForm } from './LetterForm'
import { ReplyForm } from './ReplyForm'
import { StageTracker } from './StageTracker'

const REGISTER_HREF = hrefFor({ name: 'register' })

export function CaseView({ id }: { id: number }) {
  const { data, error, reload } = useQuery(() => getCase(id), id)
  const [draftFocus, setDraftFocus] = useState<DraftFocus | null>(null)
  const draftPanelRef = useRef<HTMLElement>(null)
  const scrollToDraft = useRef(false)

  useEffect(() => {
    if (!scrollToDraft.current) return
    scrollToDraft.current = false
    draftPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [data])

  if (!data) {
    return error ? (
      <ErrorNotice title="Nie udało się wczytać sprawy." message={error}>
        <a href={REGISTER_HREF}>Wróć do rejestru</a>
      </ErrorNotice>
    ) : (
      <p className="field-hint">Wczytywanie sprawy…</p>
    )
  }

  /** Nowy projekt pisma pojawia się w sekcji „Projekt pisma” — po odświeżeniu sprawy przewijamy do niej. */
  const showDraft = (result: DraftResult) => {
    setDraftFocus({ id: result.draft_id, warning: result.warning })
    scrollToDraft.current = true
    reload()
  }

  return (
    <>
      <p className="breadcrumb">
        <a href={REGISTER_HREF}>Rejestr wniosków</a> / <span className="num">{data.case_number}</span>
      </p>

      <section className="intro">
        <h1 className="num">{data.case_number}</h1>
        <p className="lead">{data.subject}</p>
      </section>

      <StageTracker data={data} />

      {error && <ErrorNotice title="Nie udało się odświeżyć sprawy." message={error} />}
      {data.date_parse_warning && (
        <Notice tone="warning" title="Uwaga do danych z rejestru">
          <p>{data.date_parse_warning}</p>
        </Notice>
      )}

      <CaseFacts data={data} onSaved={reload} />
      <DepartmentsPanel data={data} onChanged={reload} />
      <CaseDocuments documents={data.documents} />

      {!isClosed(data.status) && (
        <>
          <ReplyForm caseId={data.id} caseDepartments={data.departments} onDraft={showDraft} />
          <ExtensionPanel key={data.deadline_date} data={data} onDraft={showDraft} />
          <LetterForm caseId={data.id} receivedAt={data.received_date} onDraft={showDraft} />
        </>
      )}

      <DepartmentMaterials replies={data.department_replies} />
      {data.drafts.length > 0 && (
        <DraftPanel
          ref={draftPanelRef}
          data={data}
          focus={draftFocus}
          onSelect={(draftId) => setDraftFocus({ id: draftId, warning: null })}
          onChanged={reload}
        />
      )}
      <CaseHistory events={data.events} />
    </>
  )
}
