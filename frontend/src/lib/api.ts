const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class UploadError extends Error {}

export type UploadInput = {
  /** Plik wniosku (jeden na wniosek). */
  file: File
  /** Data wpływu w formacie RRRR-MM-DD. */
  receivedAt: string
}

/** Przetworzone zgłoszenie (POST /api/intake/analyze → parsed_request). */
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
  /** Podmioty spoza urzędu, które mogą być dysponentem informacji. */
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

export type UploadResult = {
  /** Identyfikator analizy (intake_id) — przekazywany przy rejestracji sprawy. */
  id?: string
  analysis?: IntakeAnalysis
}

function messageForStatus(status: number): string {
  if (status === 413) return 'Plik jest zbyt duży dla serwera.'
  if (status === 400 || status === 415) return 'Serwer nie przyjmuje tego pliku.'
  if (status === 403) return 'Tryb offline: model językowy jest poza siecią urzędu, dane nie zostały wysłane.'
  if (status === 422) return 'Dokument nie ma warstwy tekstowej, a odczyt OCR się nie powiódł.'
  if (status === 502) return 'Model językowy nie odpowiedział poprawnie. Spróbuj ponownie.'
  if (status === 404 || status === 405 || status === 501)
    return 'Usługa przyjmowania wniosków nie jest dostępna na serwerze.'
  if (status >= 500) return 'Wystąpił błąd po stronie serwera aplikacji.'
  return `Serwer odrzucił żądanie (kod ${status}).`
}

/** Komunikat z pola `detail` odpowiedzi FastAPI, jeśli jest tekstem. */
async function detailOf(res: Response): Promise<string | null> {
  const data: unknown = await res.json().catch(() => null)
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
  }
  return null
}

/**
 * Wysyła plik wniosku do analizy: POST /api/intake/analyze (multipart/form-data).
 * Pola: "file" (plik wniosku), "received_at" (data wpływu, RRRR-MM-DD).
 * Backend niczego nie rejestruje — sprawa trafia do rejestru dopiero po zatwierdzeniu przez urzędnika.
 */
export async function uploadRequest({ file, receivedAt }: UploadInput): Promise<UploadResult> {
  const body = new FormData()
  body.append('file', file)
  body.append('received_at', receivedAt)

  let res: Response
  try {
    res = await fetch(`${API_URL}/api/intake/analyze`, { method: 'POST', body })
  } catch {
    throw new UploadError('Brak połączenia z serwerem aplikacji.')
  }
  if (!res.ok) {
    const detail = await detailOf(res)
    const base = messageForStatus(res.status)
    throw new UploadError(detail ? `${base} ${detail}` : base)
  }

  const data = (await res.json().catch(() => null)) as IntakeAnalysis | null
  if (data && typeof data.intake_id === 'number') return { id: String(data.intake_id), analysis: data }
  return {}
}
