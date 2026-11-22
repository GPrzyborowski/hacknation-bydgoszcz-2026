import { useId, useState, type FormEvent } from 'react'
import { BusyButton } from '../../components/BusyButton'
import { ErrorNotice } from '../../components/Notice'
import { createLetter, listExternalEntities, type DraftResult, type LetterInput } from '../../lib/api'
import { useConfig } from '../../lib/config'
import { formatIso, todayIso } from '../../lib/dates'
import { deptLabel } from '../../lib/domain'
import { useAction, useDepartments, useQuery } from '../../lib/hooks'

type Kind = 'doprecyzowanie' | 'nie_dysponent'

type Props = { caseId: number; receivedAt: string | null; onDraft: (result: DraftResult) => void }

/** Pozostałe pisma do wnioskodawcy: wezwanie do doprecyzowania i wskazanie właściwego podmiotu. */
export function LetterForm({ caseId, receivedAt, onDraft }: Props) {
  const config = useConfig()
  const { departments } = useDepartments()
  const { data: entities } = useQuery(listExternalEntities)
  const [kind, setKind] = useState<Kind>('doprecyzowanie')
  const [deadline, setDeadline] = useState('')
  const [department, setDepartment] = useState('')
  const [details, setDetails] = useState('')
  const [entityId, setEntityId] = useState('')
  const { busy, error, run } = useAction()
  const ids = { kind: useId(), deadline: useId(), department: useId(), details: useId(), entity: useId() }

  const kinds: { kind: Kind; label: string; hint: string }[] = [
    {
      kind: 'doprecyzowanie',
      label: 'Wezwanie do doprecyzowania',
      hint: `Wnioskodawca ma ${config.clarification_reply_days} dni na doprecyzowanie; wyznaczasz nowy termin rozpatrzenia.`,
    },
    {
      kind: 'nie_dysponent',
      label: 'Urząd nie jest dysponentem',
      hint: 'Wskazanie podmiotu, do którego wnioskodawca powinien się zwrócić (art. 4 ust. 3 u.d.i.p.).',
    },
  ]

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const input: LetterInput =
      kind === 'doprecyzowanie'
        ? { kind, new_deadline: deadline || null, department: department || null, details: details.trim() || null }
        : { kind, external_entity_id: entityId ? Number(entityId) : null }
    const result = await run(() => createLetter(caseId, input))
    if (result) onDraft(result)
  }

  return (
    <section className="panel" aria-labelledby="letter-heading">
      <h2 id="letter-heading" className="panel-title">
        Inne pisma w sprawie
      </h2>
      <form className="stack" onSubmit={submit}>
        <fieldset className="field">
          <legend className="field-label small">Rodzaj pisma</legend>
          <ul className="choice-list">
            {kinds.map((option) => (
              <li key={option.kind}>
                <label className="choice">
                  <input type="radio" name={ids.kind} checked={kind === option.kind} onChange={() => setKind(option.kind)} />
                  <span>
                    <strong>{option.label}</strong>
                    <span className="choice-hint">{option.hint}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </fieldset>

        {kind === 'doprecyzowanie' ? (
          <>
            <div className="field">
              <label className="field-label small" htmlFor={ids.deadline}>
                Nowy termin{' '}
                <span className="optional">
                  (puste — za {config.clarification_deadline_days} dni, maks. 2 miesiące od wpływu)
                </span>
              </label>
              <input
                id={ids.deadline}
                type="date"
                className="input input-date"
                min={todayIso()}
                value={deadline}
                onChange={(event) => setDeadline(event.target.value)}
              />
              {receivedAt && <p className="field-hint">Data wpływu: {formatIso(receivedAt)}.</p>}
            </div>
            <div className="field">
              <label className="field-label small" htmlFor={ids.department}>
                Komórka, która wnosi o doprecyzowanie
              </label>
              <select
                id={ids.department}
                className="input select"
                value={department}
                onChange={(event) => setDepartment(event.target.value)}
              >
                <option value="">— wydział sprawy —</option>
                {departments.map((item) => (
                  <option key={item.code} value={item.code}>
                    {deptLabel(item.code, item.name)}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label className="field-label small" htmlFor={ids.details}>
                Czego ma dotyczyć doprecyzowanie
              </label>
              <textarea
                id={ids.details}
                className="input textarea"
                rows={3}
                value={details}
                onChange={(event) => setDetails(event.target.value)}
              />
            </div>
          </>
        ) : (
          <div className="field">
            <label className="field-label small" htmlFor={ids.entity}>
              Podmiot właściwy
            </label>
            <select id={ids.entity} className="input select" value={entityId} onChange={(event) => setEntityId(event.target.value)}>
              <option value="">— uzupełnię w treści pisma —</option>
              {(entities ?? [])
                .filter((entity) => entity.is_active)
                .map((entity) => (
                  <option key={entity.id} value={entity.id}>
                    {entity.name}
                  </option>
                ))}
            </select>
          </div>
        )}

        {error && <ErrorNotice message={error} />}
        <div className="actions">
          <BusyButton type="submit" variant="secondary" busy={busy !== null} busyLabel="Przygotowywanie…">
            Przygotuj projekt pisma
          </BusyButton>
        </div>
      </form>
    </section>
  )
}
