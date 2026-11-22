import type { CaseItem, CaseStatus, DeptStatus, DocumentKind, LetterKind, Urgency } from './api'

export const STATUS_LABELS: Record<CaseStatus, string> = {
  brak_dzialan: 'Brak działań',
  zapytania_wyslane: 'Zapytania wysłane do wydziałów',
  kwerenda: 'Kwerenda (termin przedłużony)',
  doprecyzowanie: 'Wezwanie do doprecyzowania',
  odpowiedz_w_przygotowaniu: 'Odpowiedź w przygotowaniu',
  przygotowana_odpowiedz: 'Przygotowana odpowiedź',
  odpowiedz_wyslana: 'Odpowiedź wysłana',
}

/** Krótkie etykiety do kolumny rejestru i kalendarium. */
export const STATUS_SHORT: Record<CaseStatus, string> = {
  brak_dzialan: 'Brak działań',
  zapytania_wyslane: 'Zapytania wysłane',
  kwerenda: 'Kwerenda',
  doprecyzowanie: 'Doprecyzowanie',
  odpowiedz_w_przygotowaniu: 'W przygotowaniu',
  przygotowana_odpowiedz: 'Przygotowana',
  odpowiedz_wyslana: 'Wysłana',
}

export const DOCUMENT_LABELS: Record<DocumentKind, string> = {
  wniosek: 'Wniosek',
  odpowiedz: 'Odpowiedź',
  kwerenda: 'Pismo — kwerenda',
  doprecyzowanie: 'Wezwanie do doprecyzowania',
  nie_dysponent: 'Pismo — brak dysponenta',
}

export const DEPT_STATUS_TAG: Record<DeptStatus, string> = {
  oczekuje: 'tag',
  odpowiedzial: 'tag is-success',
  uszczegolowienie: 'tag is-warning',
}

/** Etapy sprawy z opisu wyzwania: a) brak działań … e) odpowiedź wysłana. */
export const STAGES: { label: string; statuses: CaseStatus[] }[] = [
  { label: 'Brak działań', statuses: ['brak_dzialan'] },
  { label: 'Zapytania do wydziałów', statuses: ['zapytania_wyslane', 'kwerenda', 'doprecyzowanie'] },
  { label: 'Odpowiedź w przygotowaniu', statuses: ['odpowiedz_w_przygotowaniu'] },
  { label: 'Przygotowana odpowiedź', statuses: ['przygotowana_odpowiedz'] },
  { label: 'Odpowiedź wysłana', statuses: ['odpowiedz_wyslana'] },
]

export const isClosed = (status: CaseStatus) => status === 'odpowiedz_wyslana'

/** Kwerenda i wezwanie do doprecyzowania przedłużają sprawę, ale jej nie zamykają. */
export const isInterimLetter = (kind: LetterKind) => kind === 'kwerenda' || kind === 'doprecyzowanie'

/** Sprawy podświetlane w rejestrze: po terminie oraz z terminem dziś lub jutro. */
export const isUrgent = (urgency: Urgency) => urgency === 'overdue' || urgency === 'today' || urgency === 'tomorrow'

export function urgencyLabel(urgency: Urgency, soonDays: number): string | null {
  switch (urgency) {
    case 'overdue':
      return 'po terminie'
    case 'today':
      return 'termin dziś'
    case 'tomorrow':
      return 'termin jutro'
    case 'soon':
      return `termin w ciągu ${soonDays} dni`
    default:
      return null
  }
}

/** „Pozostało dni: 5”, „Termin upływa jutro”, „Termin minął · dni po terminie: 2”. */
export function remainingText(days: number): string {
  if (days > 1) return `Pozostało dni: ${days}`
  if (days === 1) return 'Termin upływa jutro'
  if (days === 0) return 'Termin upływa dziś'
  return `Termin minął · dni po terminie: ${-days}`
}

/** „dziś”, „jutro”, „za 5 dni”. */
export function inDaysText(days: number): string {
  if (days === 0) return 'dziś'
  if (days === 1) return 'jutro'
  return `za ${days} dni`
}

/** Kolumna „Pozostało dni” rejestru: liczba dni, „dziś”, dni po terminie albo „—” dla spraw zakończonych. */
export function remainingLabel(item: CaseItem): string {
  if (isClosed(item.status)) return item.answered_on_time === false ? 'po terminie' : '—'
  const days = item.days_remaining
  if (days === null) return '—'
  if (days < 0) return `${-days} po terminie`
  return days === 0 ? 'dziś' : String(days)
}

/** „BKS.IV.1431.590.2026” → „590.2026” — do ciasnych miejsc, np. kalendarium. */
export function shortCaseNumber(caseNumber: string, prefix: string): string {
  return caseNumber.startsWith(`${prefix}.`) ? caseNumber.slice(prefix.length + 1) : caseNumber
}

export const deptLabel = (code: string, name: string) => `${code} — ${name}`
