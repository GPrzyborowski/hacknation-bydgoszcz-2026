/** Ustawowy termin udostępnienia informacji publicznej (art. 13 ust. 1 u.d.i.p.). */
export const ANSWER_DAYS = 14

const DAY_MS = 24 * 60 * 60 * 1000

/** Dzisiejsza data lokalna w formacie RRRR-MM-DD (wartość pola <input type="date">). */
export function todayIso(): string {
  const now = new Date()
  return toIso(now)
}

function toIso(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

/** Parsuje RRRR-MM-DD jako datę lokalną (bez przesunięć strefy czasowej). */
export function parseIso(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return null
  const d = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
  return Number.isNaN(d.getTime()) || toIso(d) !== value ? null : d
}

export function addDays(d: Date, days: number): Date {
  const next = new Date(d)
  next.setDate(next.getDate() + days)
  return next
}

/** Liczba dni kalendarzowych od dziś do wskazanej daty (ujemna, gdy data minęła). */
export function daysFromToday(d: Date): number {
  const today = parseIso(todayIso())!
  return Math.round((d.getTime() - today.getTime()) / DAY_MS)
}

const longDate = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' })
const weekday = new Intl.DateTimeFormat('pl-PL', { weekday: 'long' })
const shortDate = new Intl.DateTimeFormat('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric' })

export const formatLong = (d: Date) => longDate.format(d)
export const formatWeekday = (d: Date) => weekday.format(d)
export const formatShort = (d: Date) => shortDate.format(d)


/** Niedziela Wielkanocna (algorytm Meeusa/Jonesa/Butchera). */
function easterSunday(year: number): Date {
  const a = year % 19
  const b = Math.floor(year / 100)
  const c = year % 100
  const d = Math.floor(b / 4)
  const e = b % 4
  const f = Math.floor((b + 8) / 25)
  const g = Math.floor((b - f + 1) / 3)
  const h = (19 * a + b - d - g + 15) % 30
  const i = Math.floor(c / 4)
  const k = c % 4
  const l = (32 + 2 * e + 2 * i - h - k) % 7
  const m = Math.floor((a + 11 * h + 22 * l) / 451)
  const month = Math.floor((h + l - 7 * m + 114) / 31)
  const day = ((h + l - 7 * m + 114) % 31) + 1
  return new Date(year, month - 1, day)
}

/** Dni ustawowo wolne od pracy w Polsce (ustawa o dniach wolnych od pracy, stan od 2025 r.). */
function publicHolidays(year: number): Set<string> {
  const fixed = ['01-01', '01-06', '05-01', '05-03', '08-15', '11-01', '11-11', '12-24', '12-25', '12-26']
  const easter = easterSunday(year)
  const movable = [0, 1, 49, 60].map((offset) => toIso(addDays(easter, offset)))
  return new Set([...fixed.map((md) => `${year}-${md}`), ...movable])
}

/** Sobota, niedziela lub święto ustawowe. */
export function isNonWorkingDay(d: Date): boolean {
  const dow = d.getDay()
  return dow === 0 || dow === 6 || publicHolidays(d.getFullYear()).has(toIso(d))
}

export function nextWorkingDay(d: Date): Date {
  let next = addDays(d, 1)
  while (isNonWorkingDay(next)) next = addDays(next, 1)
  return next
}

export type DeadlineInfo = {
  received: Date
  /** 14. dzień od daty wpływu. */
  day14: Date
  /**
   * Obowiązujący termin: data wpływu + 14 dni — tak liczy rejestr UMB
   * („WNIOSKI O UDOSTĘPNIANIE INFORMACJI PUBLICZNEJ.xlsx”, formuła =E+14), bez przesuwania.
   * Według niego liczone są pozostałe dni i stan ostrzeżenia (tak samo jak w backendzie).
   */
  deadline: Date
  /** 14. dzień przypada w sobotę, niedzielę lub święto — pokazujemy ostrzeżenie. */
  nonWorkingDay: boolean
  /** Następny dzień roboczy (art. 57 § 4 KPA) — informacyjnie, przy ostrzeżeniu. */
  nextWorking: Date
  remaining: number
}

export function deadlineFor(receivedIso: string): DeadlineInfo | null {
  const received = parseIso(receivedIso)
  if (!received) return null
  const day14 = addDays(received, ANSWER_DAYS)
  return {
    received,
    day14,
    deadline: day14,
    nonWorkingDay: isNonWorkingDay(day14),
    nextWorking: nextWorkingDay(day14),
    remaining: daysFromToday(day14),
  }
}

export function remainingText(remaining: number): string {
  if (remaining > 0) return `Pozostało dni: ${remaining}`
  if (remaining === 0) return 'Termin upływa dziś'
  return `Termin minął · dni po terminie: ${-remaining}`
}
