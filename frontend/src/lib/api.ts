const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/** Analiza z OCR i modelem Gemini trwa zwykle kilka sekund; po 3 minutach pokazujemy błąd zamiast czekać. */
const TIMEOUT_MS = 3 * 60 * 1000

export class ApiError extends Error {
  status: number
  constructor(message: string, status = 0) {
    super(message)
    this.status = status
  }
}

/** Zachowane dla ekranu wgrywania. */
export { ApiError as UploadError }

function messageForStatus(status: number): string {
  if (status === 413) return 'Plik jest zbyt duży dla serwera.'
  if (status === 400 || status === 415) return 'Serwer nie przyjął danych.'
  if (status === 403) return 'Tryb offline: wysyłka do modelu językowego jest zablokowana.'
  if (status === 404) return 'Nie znaleziono danych na serwerze.'
  if (status === 409) return 'Taki wpis już istnieje.'
  if (status === 422) return 'Nie udało się odczytać dokumentu.'
  if (status === 502) return 'Model językowy nie odpowiedział poprawnie. Spróbuj ponownie.'
  if (status >= 500) return 'Wystąpił błąd po stronie serwera aplikacji.'
  return `Serwer odrzucił żądanie (kod ${status}).`
}

async function detailOf(res: Response): Promise<string | null> {
  const data: unknown = await res.json().catch(() => null)
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : ''))
        .filter(Boolean)
        .join('; ')
    }
  }
  return null
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, signal: controller.signal })
  } catch {
    throw new ApiError(
      controller.signal.aborted
        ? 'Serwer nie odpowiedział w ciągu 3 minut. Sprawdź, czy backend działa.'
        : 'Brak połączenia z serwerem aplikacji. Sprawdź, czy backend działa (port 8000).',
    )
  } finally {
    clearTimeout(timer)
  }
  if (!res.ok) {
    const detail = await detailOf(res)
    throw new ApiError(detail ?? messageForStatus(res.status), res.status)
  }
  return res
}

async function json<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await request(path, init)
  return (await res.json()) as T
}

function send<T>(path: string, method: string, body: unknown): Promise<T> {
  return json<T>(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}

// --- typy ----------------------------------------------------------------------------------

export type CaseStatus =
  | 'brak_dzialan'
  | 'zapytania_wyslane'
  | 'kwerenda'
  | 'doprecyzowanie'
  | 'odpowiedz_w_przygotowaniu'
  | 'przygotowana_odpowiedz'
  | 'odpowiedz_wyslana'

export const STATUS_LABELS: Record<CaseStatus, string> = {
  brak_dzialan: 'Brak działań',
  zapytania_wyslane: 'Zapytania wysłane do wydziałów',
  kwerenda: 'Kwerenda (termin przedłużony)',
  doprecyzowanie: 'Wezwanie do doprecyzowania',
  odpowiedz_w_przygotowaniu: 'Odpowiedź w przygotowaniu',
  przygotowana_odpowiedz: 'Przygotowana odpowiedź',
  odpowiedz_wyslana: 'Odpowiedź wysłana',
}

/** Krótkie etykiety do kolumny rejestru. */
export const STATUS_SHORT: Record<CaseStatus, string> = {
  brak_dzialan: 'Brak działań',
  zapytania_wyslane: 'Zapytania wysłane',
  kwerenda: 'Kwerenda',
  doprecyzowanie: 'Doprecyzowanie',
  odpowiedz_w_przygotowaniu: 'W przygotowaniu',
  przygotowana_odpowiedz: 'Przygotowana',
  odpowiedz_wyslana: 'Wysłana',
}

export type Health ={ status: string; offline_mode: boolean; model: string; llm_enabled: boolean }

export type ParsedRequest = {
  wnioskodawca: string | null
  typ_wnioskodawcy: string | null
  adres_do_odpowiedzi: string | null
  forma_odpowiedzi: string | null
  data_na_pismie: string | null
  temat_skrot: string
  pytania: string[]
  kategoria: string
  czy_to_wniosek_udip: boolean
  uwagi: string
}

export type SimilarCase = {
  id: number
  case_number: string
  received_date: string | null
  response_date: string | null
  applicant: string
  subject: string
  procedure_mode: string
  departments: string[]
  response_text: string
  score: number | null
}

export type DepartmentSuggestion = { code: string; name: string; reason: string }

export type IntakeAnalysis = {
  intake_id: number
  filename: string
  extraction: {
    has_text_layer: boolean
    used_ocr: boolean
    text_length: number
    /** Jakość odczytu 0–1; poniżej 0,5 skan jest nieczytelny (np. pismo odręczne). */
    quality: number
    warning: string | null
    manual_text_used?: boolean
  }
  llm_used: boolean
  parsed_request: ParsedRequest
  similar_cases: SimilarCase[]
  suggested_departments: DepartmentSuggestion[]
  suggested_external_entities: { id: number; name: string; reason: string }[]
  suggested_deadline: {
    received_date: string
    deadline_date: string
    max_extended_deadline: string
    days_remaining: number
    note: string | null
  } | null
  initial_status: string
  text_preview: string
}

export type Urgency = 'overdue' | 'today' | 'tomorrow' | 'soon' | 'normal' | 'done'

export type CaseItem = {
  id: number
  ordinal: number | null
  case_number: string
  year: number
  applicant: string
  subject: string
  received_date: string | null
  deadline_date: string | null
  response_date: string | null
  date_parse_warning: string | null
  status: CaseStatus
  procedure_mode: string
  departments: string[]
  initials: string | null
  notes: string | null
  days_remaining: number | null
  answered_on_time: boolean | null
  deadline_note: string | null
  /** Termin 14-dniowy przed przedłużeniem. */
  original_deadline_date: string | null
  /** O ile dni przedłużono termin (kwerenda / doprecyzowanie). */
  extension_days: number
  /** Najpóźniejszy dopuszczalny termin: 2 miesiące od wpływu (art. 13 ust. 2 u.d.i.p.). */
  max_deadline_date: string | null
  dept_total: number
  dept_answered: number
  dept_waiting: string[]
  dept_clarification: string[]
  urgency: Urgency
}

export type DeptStatus = 'oczekuje' | 'odpowiedzial' | 'uszczegolowienie'

export type DepartmentStatus = {
  code: string
  name: string
  status: DeptStatus
  status_label: string
  requested_at: string | null
  answered_at: string | null
  clarification_count: number
  note: string | null
}

export type AnonymizationCandidate = {
  id: number
  quote: string
  category: string
  reason: string
  start: number
  end: number
  mask: string
  active: boolean
  source: string
}

export type Draft = {
  id: number
  kind: string
  draft_text: string
  anonymization_candidates: AnonymizationCandidate[]
  final_text: string | null
  generated_format: string | null
  llm_used: boolean
  created_at: string
}

export type CaseDetail = CaseItem & {
  applicant_contact: string | null
  request_text: string | null
  parsed_request: ParsedRequest | null
  response_text: string | null
  department_status: DepartmentStatus[]
  documents: { id: number; kind: string; filename: string | null; text: string; document_date: string | null }[]
  department_replies: { id: number; department: string | null; filename: string | null; text: string; created_at: string }[]
  drafts: Draft[]
  events: { event: string; detail: string | null; created_at: string }[]
}

export type DraftResult = {
  case_id: number
  status: CaseStatus
  kind: string
  deadline_date: string | null
  warning: string | null
  draft_id: number
  draft_text: string
  llm_used: boolean
  anonymization_candidates: AnonymizationCandidate[]
}

export type Department = { code: string; name: string; keywords: string; is_active: boolean }
export type ExternalEntity = { id: number; name: string; name_genitive: string; contact: string; keywords: string; is_active: boolean }
export type Rule = { id: number; title: string; source: string; content: string; is_active: boolean; created_at: string; updated_at: string }
export type Category = { id: number; name: string; legal_basis: string; regex: string | null; mask: string; is_active: boolean }

// --- wywołania -----------------------------------------------------------------------------

export const getHealth = () => json<Health>('/')

export type UploadInput = { file: File; receivedAt: string; manualText?: string }

/** POST /api/intake/analyze — niczego nie rejestruje; sprawa powstaje dopiero po zatwierdzeniu przez urzędnika. */
export function analyzeRequest({ file, receivedAt, manualText }: UploadInput): Promise<IntakeAnalysis> {
  const body = new FormData()
  body.append('file', file)
  body.append('received_at', receivedAt)
  if (manualText?.trim()) body.append('manual_text', manualText.trim())
  return json<IntakeAnalysis>('/api/intake/analyze', { method: 'POST', body })
}

export type RegisterInput = {
  case_number?: string | null
  applicant: string
  applicant_contact?: string | null
  subject: string
  received_date: string
  deadline_date?: string | null
  departments: string[]
  initials?: string | null
  intake_id?: number
  parsed_request?: ParsedRequest
  generate_dept_request_template?: boolean
}

export type RegisterResult = {
  id: number
  case_number: string
  status: CaseStatus
  deadline_date: string
  departments: string[]
  request_templates: Record<string, string>
}

export const registerCase = (input: RegisterInput) => send<RegisterResult>('/api/cases/register', 'POST', input)

export function listCases(params: { year?: number; q?: string }): Promise<CaseItem[]> {
  const qs = new URLSearchParams()
  if (params.year) qs.set('year', String(params.year))
  if (params.q?.trim()) qs.set('q', params.q.trim())
  return json<CaseItem[]>(`/api/cases?${qs}`)
}

export const listYears = () => json<number[]>('/api/cases/years')
export const getCase = (id: number) => json<CaseDetail>(`/api/cases/${id}`)

export const updateStatus = (id: number, status: CaseStatus, deadline_date?: string | null) =>
  send<{ case_id: number; status: CaseStatus; deadline_date: string | null }>(`/api/cases/${id}/status`, 'PATCH', {
    status,
    deadline_date: deadline_date || null,
  })

export function departmentReply(id: number, input: { file?: File | null; text?: string; department?: string }) {
  const body = new FormData()
  if (input.file) body.append('file', input.file)
  if (input.text?.trim()) body.append('reply_text', input.text.trim())
  if (input.department) body.append('department', input.department)
  return json<DraftResult>(`/api/cases/${id}/department-reply`, { method: 'POST', body })
}

export type LetterKind = 'odpowiedz' | 'nie_dysponent' | 'kwerenda' | 'doprecyzowanie'

export const createLetter = (
  id: number,
  input: { kind: LetterKind; new_deadline?: string | null; external_entity_id?: number | null; department?: string | null; details?: string | null },
) => send<DraftResult>(`/api/cases/${id}/letter`, 'POST', input)

export const addCaseDepartment = (id: number, code: string) =>
  send<DepartmentStatus[]>(`/api/cases/${id}/departments`, 'POST', { code })

export const setDepartmentStatus = (id: number, code: string, status: DeptStatus) =>
  send<DepartmentStatus[]>(`/api/cases/${id}/departments/${encodeURIComponent(code)}`, 'PATCH', { status })

export const requestClarification = (id: number, code: string, details: string) =>
  send<{ code: string; text: string; departments: DepartmentStatus[] }>(
    `/api/cases/${id}/departments/${encodeURIComponent(code)}/clarification`,
    'POST',
    { details: details || null },
  )

export const anonymizePreview =(text: string, knownPeople: string[]) =>
  send<AnonymizationCandidate[]>('/api/response/anonymize-preview', 'POST', { text, known_people: knownPeople })

/** Zwraca plik pisma (DOCX/PDF) z nałożonymi anonimizacjami i nazwę pliku. */
export async function generateDocument(input: {
  draft_id: number
  content: string
  format: 'docx' | 'pdf'
  anonymization_items: { start: number; end: number; mask: string; active: boolean }[]
}): Promise<{ blob: Blob; filename: string }> {
  const res = await request('/api/response/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const match = /filename="([^"]+)"/.exec(disposition)
  return { blob: await res.blob(), filename: match?.[1] ?? `odpowiedz.${input.format}` }
}

export const markSent = (case_id: number, draft_id: number, final_content: string) =>
  send<{ case_id: number; status: CaseStatus; response_date: string }>('/api/response/send', 'POST', {
    case_id,
    draft_id,
    final_content,
  })

export const listDepartments = () => json<Department[]>('/api/knowledge/departments')
export const listExternalEntities = () => json<ExternalEntity[]>('/api/knowledge/external-entities')
export const listRules = () => json<Rule[]>('/api/knowledge/rules')
export const listCategories = () => json<Category[]>('/api/knowledge/anonymization-categories')
export const setRuleActive = (id: number, is_active: boolean) => send<Rule>(`/api/knowledge/rules/${id}`, 'PUT', { is_active })

export function importExcel(file: File) {
  const body = new FormData()
  body.append('file', file)
  return json<{ imported: number; updated: number; skipped: number; warnings: string[] }>('/api/knowledge/cases/import-excel', {
    method: 'POST',
    body,
  })
}

export function importRuleDocument(file: File, title: string, source: string) {
  const body = new FormData()
  body.append('file', file)
  if (title.trim()) body.append('title', title.trim())
  if (source.trim()) body.append('source', source.trim())
  return json<Rule[]>('/api/knowledge/rules/import-document', { method: 'POST', body })
}
