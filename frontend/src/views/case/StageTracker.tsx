import type { CaseDetail } from '../../lib/api'
import { STAGES } from '../../lib/domain'

function stageNote(data: CaseDetail): string | null {
  if (data.status === 'kwerenda') {
    return `Kwerenda — termin przedłużony${data.extension_days ? ` o ${data.extension_days} dni` : ''}`
  }
  if (data.status === 'doprecyzowanie') return 'Czekamy na doprecyzowanie wniosku'
  return null
}

export function StageTracker({ data }: { data: CaseDetail }) {
  const current = Math.max(0, STAGES.findIndex((stage) => stage.statuses.includes(data.status)))
  const note = stageNote(data)

  return (
    <nav className="stages" aria-label="Etap sprawy">
      <ol>
        {STAGES.map((stage, index) => {
          const state = index < current ? 'done' : index === current ? 'current' : 'todo'
          return (
            <li key={stage.label} className={`stage is-${state}`} aria-current={state === 'current' ? 'step' : undefined}>
              <span className="stage-num num" aria-hidden="true">
                {index + 1}
              </span>
              <span className="stage-label">
                {stage.label}
                {state === 'current' && note && <span className="stage-flag">{note}</span>}
              </span>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
