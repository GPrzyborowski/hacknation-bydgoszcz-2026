import { useId, useState, type FormEvent } from 'react'
import { BusyButton } from '../../components/BusyButton'
import { ErrorNotice, Notice } from '../../components/Notice'
import { registerCase, type IntakeAnalysis, type RegisterResult } from '../../lib/api'
import { useConfig } from '../../lib/config'
import { formatIso } from '../../lib/dates'
import { focusById } from '../../lib/dom'
import { deptLabel } from '../../lib/domain'
import { useAction, useDepartments } from '../../lib/hooks'

type Props = {
  analysis: IntakeAnalysis
  receivedAt: string
  onRegistered: (result: RegisterResult) => void
  onCancel: () => void
}

type FieldErrors = { applicant?: string; subject?: string }

/** Dane do rejestru wypełnione propozycjami asystenta — sprawa powstaje dopiero po zatwierdzeniu przez urzędnika. */
export function RegistrationForm({ analysis, receivedAt, onRegistered, onCancel }: Props) {
  const parsed = analysis.parsed_request
  const { case_number_prefix } = useConfig()
  const { departments, nameOf } = useDepartments()
  const [form, setForm] = useState({
    applicant: parsed.wnioskodawca ?? '',
    contact: parsed.adres_do_odpowiedzi ?? '',
    subject: parsed.temat_skrot,
    deadline: analysis.suggested_deadline.deadline_date,
    caseNumber: '',
    initials: '',
    withRequestTemplates: true,
  })
  const [selected, setSelected] = useState(() => analysis.suggested_departments.map((department) => department.code))
  const [extraDepartment, setExtraDepartment] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const save = useAction()
  const ids = {
    applicant: useId(),
    contact: useId(),
    subject: useId(),
    deadline: useId(),
    caseNumber: useId(),
    initials: useId(),
    extraDepartment: useId(),
  }

  const update = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((current) => ({ ...current, [key]: value }))
  const toggle = (code: string) =>
    setSelected((codes) => (codes.includes(code) ? codes.filter((other) => other !== code) : [...codes, code]))
  const addedByOfficial = selected.filter((code) => !analysis.suggested_departments.some((department) => department.code === code))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const applicant = form.applicant.trim()
    const subject = form.subject.trim()
    const nextErrors: FieldErrors = {
      applicant: applicant ? undefined : 'Podaj wnioskodawcę (imię i nazwisko, nazwę lub adres e-mail).',
      subject: subject ? undefined : 'Podaj przedmiot wniosku.',
    }
    setErrors(nextErrors)
    if (nextErrors.applicant) return focusById(ids.applicant)
    if (nextErrors.subject) return focusById(ids.subject)

    const result = await save.run(() =>
      registerCase({
        case_number: form.caseNumber.trim() || null,
        applicant,
        applicant_contact: form.contact.trim() || null,
        subject,
        received_date: receivedAt,
        deadline_date: form.deadline || null,
        departments: selected,
        initials: form.initials.trim() || null,
        intake_id: analysis.intake_id,
        parsed_request: { ...parsed, wnioskodawca: applicant, temat_skrot: subject },
        generate_dept_request_template: form.withRequestTemplates,
      }),
    )
    if (result) onRegistered(result)
  }

  return (
    <form className="form" onSubmit={submit} noValidate aria-busy={save.busy !== null}>
      <h3 className="form-title">Dane do rejestru</h3>

      <div className={`field${errors.applicant ? ' has-error' : ''}`}>
        <label className="field-label" htmlFor={ids.applicant}>
          Wnioskodawca
        </label>
        {errors.applicant && <p className="field-error">{errors.applicant}</p>}
        <input
          id={ids.applicant}
          className="input"
          value={form.applicant}
          onChange={(event) => update('applicant', event.target.value)}
          aria-invalid={!!errors.applicant}
        />
      </div>

      <div className="field">
        <label className="field-label" htmlFor={ids.contact}>
          Adres do odpowiedzi <span className="optional">(opcjonalnie)</span>
        </label>
        <input id={ids.contact} className="input" value={form.contact} onChange={(event) => update('contact', event.target.value)} />
      </div>

      <div className={`field${errors.subject ? ' has-error' : ''}`}>
        <label className="field-label" htmlFor={ids.subject}>
          Przedmiot wniosku
        </label>
        <p className="field-hint">Skrócony opis tematu, widoczny w rejestrze.</p>
        {errors.subject && <p className="field-error">{errors.subject}</p>}
        <textarea
          id={ids.subject}
          className="input textarea"
          rows={2}
          value={form.subject}
          onChange={(event) => update('subject', event.target.value)}
          aria-invalid={!!errors.subject}
        />
      </div>

      <div className="field-row">
        <div className="field">
          <span className="field-label">Data wpływu</span>
          <span className="readonly num">{formatIso(receivedAt)}</span>
        </div>
        <div className="field">
          <label className="field-label" htmlFor={ids.deadline}>
            Termin odpowiedzi
          </label>
          <input
            id={ids.deadline}
            type="date"
            className="input input-date"
            value={form.deadline}
            max={analysis.suggested_deadline.max_extended_deadline}
            onChange={(event) => update('deadline', event.target.value)}
          />
        </div>
      </div>
      {analysis.suggested_deadline.note && <p className="field-hint">{analysis.suggested_deadline.note}</p>}

      <div className="field-row">
        <div className="field">
          <label className="field-label" htmlFor={ids.caseNumber}>
            Znak sprawy <span className="optional">(opcjonalnie)</span>
          </label>
          <p className="field-hint">Puste — nadany kolejny numer {case_number_prefix}.</p>
          <input
            id={ids.caseNumber}
            className="input num"
            value={form.caseNumber}
            placeholder={`${case_number_prefix}.…`}
            onChange={(event) => update('caseNumber', event.target.value)}
          />
        </div>
        <div className="field">
          <label className="field-label" htmlFor={ids.initials}>
            Osoba odpowiedzialna <span className="optional">(opcjonalnie)</span>
          </label>
          <p className="field-hint">Inicjały lub nazwa, jak w rejestrze.</p>
          <input id={ids.initials} className="input" value={form.initials} onChange={(event) => update('initials', event.target.value)} />
        </div>
      </div>

      <fieldset className="field">
        <legend className="field-label">Wydziały do zapytania</legend>
        <p className="field-hint">Propozycje asystenta są zaznaczone. Zapytań nikt nie wysyła automatycznie.</p>
        <ul className="choice-list">
          {analysis.suggested_departments.map((department) => (
            <li key={department.code}>
              <DepartmentChoice
                label={deptLabel(department.code, department.name)}
                hint={department.reason}
                checked={selected.includes(department.code)}
                onToggle={() => toggle(department.code)}
              />
            </li>
          ))}
          {addedByOfficial.map((code) => (
            <li key={code}>
              <DepartmentChoice label={deptLabel(code, nameOf(code))} hint="Dodane przez urzędnika" checked onToggle={() => toggle(code)} />
            </li>
          ))}
        </ul>
        <div className="inline-add">
          <label className="visually-hidden" htmlFor={ids.extraDepartment}>
            Dodaj komórkę
          </label>
          <select
            id={ids.extraDepartment}
            className="input select"
            value={extraDepartment}
            onChange={(event) => setExtraDepartment(event.target.value)}
          >
            <option value="">Dodaj inną komórkę…</option>
            {departments
              .filter((department) => !selected.includes(department.code))
              .map((department) => (
                <option key={department.code} value={department.code}>
                  {deptLabel(department.code, department.name)}
                </option>
              ))}
          </select>
          <button
            type="button"
            className="secondary-button"
            disabled={!extraDepartment}
            onClick={() => {
              setSelected((codes) => [...codes, extraDepartment])
              setExtraDepartment('')
            }}
          >
            Dodaj
          </button>
        </div>
        {analysis.suggested_external_entities.length > 0 && (
          <Notice tone="info" title="Możliwe, że urząd nie jest dysponentem informacji">
            <p>
              Wniosek może dotyczyć: {analysis.suggested_external_entities.map((entity) => entity.name).join('; ')}. Pismo
              wskazujące właściwy podmiot przygotujesz w karcie sprawy.
            </p>
          </Notice>
        )}
      </fieldset>

      <label className="choice">
        <input
          type="checkbox"
          checked={form.withRequestTemplates}
          onChange={(event) => update('withRequestTemplates', event.target.checked)}
        />
        <span>Przygotuj treść prośby do wydziałów (do skopiowania)</span>
      </label>

      {save.error && <ErrorNotice title="Nie zarejestrowano wniosku." message={save.error} />}

      <div className="actions">
        <BusyButton type="submit" busy={save.busy !== null} busyLabel="Rejestrowanie…">
          Zarejestruj wniosek
        </BusyButton>
        <button type="button" className="link-button" onClick={onCancel}>
          Anuluj i wgraj inny wniosek
        </button>
      </div>
    </form>
  )
}

function DepartmentChoice({ label, hint, checked, onToggle }: { label: string; hint: string; checked: boolean; onToggle: () => void }) {
  return (
    <label className="choice">
      <input type="checkbox" checked={checked} onChange={onToggle} />
      <span>
        <strong>{label}</strong>
        <span className="choice-hint">{hint}</span>
      </span>
    </label>
  )
}
