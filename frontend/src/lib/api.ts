const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/** Analiza z OCR i modelem trwa zwykle kilka sekund; po tym czasie pokazujemy błąd zamiast czekać. */
const TIMEOUT_MINUTES = 3

export class ApiError extends Error {
  status: number

  constructor(message: string, status = 0) {
    super(message)
    this.status = status
  }
}

export function errorMessage(error: unknown, fallback = 'Nieznany błąd.'): string {
  return error instanceof Error ? error.message : fallback
}

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

/** Komunikat z pola `detail` odpowiedzi FastAPI (tekst albo lista błędów walidacji). */
async function detailOf(response: Response): Promise<string | null> {
  const data: unknown = await response.json().catch(() => null)
  if (!data || typeof data !== 'object' || !('detail' in data)) return null
  const { detail } = data as { detail: unknown }
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => (item && typeof item === 'object' && 'msg' in item ? String(item.msg) : '')).filter(Boolean).join('; ')
  }
  return null
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MINUTES * 60_000)
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, signal: controller.signal })
  } catch {
    throw new ApiError(
      controller.signal.aborted
        ? `Serwer nie odpowiedział w ciągu ${TIMEOUT_MINUTES} minut. Sprawdź, czy backend działa.`
        : `Brak połączenia z serwerem aplikacji (${API_URL}). Sprawdź, czy backend działa.`,
    )
  } finally {
    clearTimeout(timer)
  }
  if (!response.ok) {
    throw new ApiError((await detailOf(response)) ?? messageForStatus(response.status), response.status)
  }
  return response
}

async function json<T>(path: string, init: RequestInit = {}): Promise<T> {
  return (await request(path, init)).json() as Promise<T>
}

function jsonInit(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

const sendJson = <T>(path: string, method: string, body: unknown) => json<T>(path, jsonInit(method, body))

/** FormData bez pustych pól — backend traktuje brak pola jako „nie podano”. */
function formData(fields: Record<string, string | Blob | null | undefined>): FormData {
  const form = new FormData()
  for (const [name, value] of Object.entries(fields)) {
    if (value instanceof Blob) form.append(name, value)
    else if (value?.trim()) form.append(name, value.trim())
  }
  return form
}

const postForm = <T>(path: string, fields: Record<string, string | Blob | null | undefined>) =>
  json<T>(path, { method: 'POST', body: formData(fields) })

/** Dane słownikowe pobierane raz na sesję (nieudane pobranie można ponowić). */
function cached<T>(load: () => Promise<T>): () => Promise<T> {
  let pending: Promise<T> | null = null
  return () =>
    (pending ??= load().catch((error: unknown) => {
      pending = null
      throw error
    }))
}

// --- typy ------------------------------------------------------------------------------------------

export type CaseStatus =
  | 'brak_dzialan'
  | 'zapytania_wyslane'
  | 'kwerenda'
  | 'doprecyzowanie'
  | 'odpowiedz_w_przygotowaniu'
  | 'przygotowana_odpowiedz'
  | 'odpowiedz_wyslana'

export type Urgency = 'overdue' | 'today' | 'tomorrow' | 'soon' | 'normal' | 'done'
export type LetterKind = 'odpowiedz' | 'nie_dysponent' | 'kwerenda' | 'doprecyzowanie'
export type DocumentKind = LetterKind | 'wniosek'
export type DeptStatus = 'oczekuje' | 'odpowiedzial' | 'uszczegolowienie'

export type AppConfig = {
  case_number_prefix: string
  max_upload_mb: number
  request_extensions: string[]
  knowledge_extensions: string[]
  spreadsheet_extensions: string[]
  answer_days: number
  soon_days: number
  clarification_reply_days: number
  clarification_deadline_days: number
  model: string
  llm_enabled: boolean
  offline_mode: boolean
}

export type DeadlineSuggestion = {
  received_date: string
  deadline_date: string
  max_extended_deadline: string
  days_remaining: number
  urgency: Urgency
  note: string | null
}

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
    manual_text_used: boolean
  }
  llm_used: boolean
  parsed_request: ParsedRequest
  similar_cases: SimilarCase[]
  suggested_departments: { code: string; name: string; reason: string }[]
  suggested_external_entities: { id: number; name: string; reason: string }[]
  suggested_deadline: DeadlineSuggestion
  text_preview: string
}

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
  extension_days: number
  /** Najpóźniejszy dopuszczalny termin: 2 miesiące od wpływu (art. 13 ust. 2 u.d.i.p.). */
  max_deadline_date: string | null
  dept_total: number
  dept_answered: number
  dept_waiting: string[]
  dept_clarification: string[]
  urgency: Urgency
}

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

export type AnonymizationItem = Pick<AnonymizationCandidate, 'start' | 'end' | 'mask' | 'active'>

export type Draft = {
  id: number
  kind: LetterKind
  draft_text: string
  anonymization_candidates: AnonymizationCandidate[]
  final_text: string | null
  generated_format: string | null
  llm_used: boolean
  created_at: string
}

export type CaseDocument = {
  id: number
  kind: DocumentKind
  filename: string | null
  text: string
  document_date: string | null
}

export type DepartmentReply = { id: number; department: string | null; filename: string | null; text: string; created_at: string }

export type CaseDetail = CaseItem & {
  applicant_contact: string | null
  request_text: string | null
  parsed_request: ParsedRequest | null
  response_text: string | null
  department_status: DepartmentStatus[]
  documents: CaseDocument[]
  department_replies: DepartmentReply[]
  drafts: Draft[]
  events: { event: string; detail: string | null; created_at: string }[]
}

export type DraftResult = {
  case_id: number
  status: CaseStatus
  kind: LetterKind
  deadline_date: string | null
  warning: string | null
  draft_id: number
  draft_text: string
  llm_used: boolean
  anonymization_candidates: AnonymizationCandidate[]
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

export type Department = { code: string; name: string; keywords: string; is_active: boolean }
export type ExternalEntity = { id: number; name: string; name_genitive: string; contact: string; keywords: string; is_active: boolean }
export type Rule = { id: number; title: string; source: string; content: string; is_active: boolean }
export type Category = { id: number; name: string; legal_basis: string; regex: string | null; mask: string; is_active: boolean }
export type ImportSummary = { imported: number; updated: number; skipped: number; warnings: string[] }

// --- system ------------------------------------------------------------------------------------------

export const getConfig = () => json<AppConfig>('/api/config')

export const previewDeadline = (received: string) =>
  json<DeadlineSuggestion>(`/api/deadlines/preview?${new URLSearchParams({ received })}`)

export const listNonWorkingDays = (from: string, to: string) =>
  json<string[]>(`/api/deadlines/non-working-days?${new URLSearchParams({ from, to })}`)

// --- wnioski i sprawy ------------------------------------------------------------------------------

/** Analiza niczego nie rejestruje — sprawa powstaje dopiero po zatwierdzeniu danych przez urzędnika. */
export const analyzeRequest = (file: File, receivedAt: string, manualText?: string) =>
  postForm<IntakeAnalysis>('/api/intake/analyze', { file, received_at: receivedAt, manual_text: manualText })

export const registerCase = (input: RegisterInput) => sendJson<RegisterResult>('/api/cases/register', 'POST', input)

export function listCases(filters: { year?: number; query?: string; openOnly?: boolean } = {}): Promise<CaseItem[]> {
  const params = new URLSearchParams()
  if (filters.year) params.set('year', String(filters.year))
  if (filters.query?.trim()) params.set('q', filters.query.trim())
  if (filters.openOnly) params.set('open_only', 'true')
  return json<CaseItem[]>(`/api/cases?${params}`)
}

export const listYears = () => json<number[]>('/api/cases/years')
export const getCase = (id: number) => json<CaseDetail>(`/api/cases/${id}`)

export const updateStatus = (id: number, status: CaseStatus, deadline: string | null) =>
  sendJson<{ case_id: number; status: CaseStatus }>(`/api/cases/${id}/status`, 'PATCH', { status, deadline_date: deadline || null })

export const departmentReply = (id: number, reply: { file: File | null; text: string; department: string }) =>
  postForm<DraftResult>(`/api/cases/${id}/department-reply`, { file: reply.file, reply_text: reply.text, department: reply.department })

export type LetterInput = {
  kind: LetterKind
  new_deadline?: string | null
  external_entity_id?: number | null
  department?: string | null
  details?: string | null
}

export const createLetter = (id: number, input: LetterInput) => sendJson<DraftResult>(`/api/cases/${id}/letter`, 'POST', input)

export const addCaseDepartment = (id: number, code: string) =>
  sendJson<DepartmentStatus[]>(`/api/cases/${id}/departments`, 'POST', { code })

export const setDepartmentStatus = (id: number, code: string, status: DeptStatus) =>
  sendJson<DepartmentStatus[]>(`/api/cases/${id}/departments/${encodeURIComponent(code)}`, 'PATCH', { status })

export const requestClarification = (id: number, code: string, details: string) =>
  sendJson<{ code: string; text: string; departments: DepartmentStatus[] }>(
    `/api/cases/${id}/departments/${encodeURIComponent(code)}/clarification`,
    'POST',
    { details: details.trim() || null },
  )

// --- pisma i anonimizacja ---------------------------------------------------------------------------

export const anonymizePreview = (text: string, knownPeople: string[]) =>
  sendJson<AnonymizationCandidate[]>('/api/response/anonymize-preview', 'POST', { text, known_people: knownPeople })

/** Plik pisma (DOCX/PDF) z nałożonymi anonimizacjami i nazwą pliku z nagłówka odpowiedzi. */
export async function generateDocument(input: {
  draft_id: number
  content: string
  format: 'docx' | 'pdf'
  anonymization_items: AnonymizationItem[]
}): Promise<{ blob: Blob; filename: string }> {
  const response = await request('/api/response/generate', jsonInit('POST', input))
  const filename = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') ?? '')?.[1]
  return { blob: await response.blob(), filename: filename ?? `odpowiedz.${input.format}` }
}

/** Odnotowuje wysłanie pisma; zaznaczone fragmenty maskuje serwer przed zapisem w aktach i archiwum. */
export const markSent = (caseId: number, draftId: number, content: string, items: AnonymizationItem[]) =>
  sendJson<{ case_id: number; status: CaseStatus; response_date: string }>('/api/response/send', 'POST', {
    case_id: caseId,
    draft_id: draftId,
    final_content: content,
    anonymization_items: items,
  })

// --- baza wiedzy -------------------------------------------------------------------------------------

export const listDepartments = cached(() => json<Department[]>('/api/knowledge/departments'))
export const listExternalEntities = cached(() => json<ExternalEntity[]>('/api/knowledge/external-entities'))
export const listRules = () => json<Rule[]>('/api/knowledge/rules')
export const listCategories = () => json<Category[]>('/api/knowledge/anonymization-categories')

export const setRuleActive = (id: number, isActive: boolean) =>
  sendJson<Rule>(`/api/knowledge/rules/${id}`, 'PUT', { is_active: isActive })

export const importExcel = (file: File) => postForm<ImportSummary>('/api/knowledge/cases/import-excel', { file })

export const importRuleDocument = (file: File, title: string, source: string) =>
  postForm<Rule[]>('/api/knowledge/rules/import-document', { file, title, source })
