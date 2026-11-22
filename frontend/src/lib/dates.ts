/** Daty w interfejsie. Terminy ustawowe i dni wolne liczy backend — tu tylko odczyt i zapis dat. */

const DAY_MS = 24 * 60 * 60 * 1000

const longDate = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' })
const shortDate = new Intl.DateTimeFormat('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric' })
const weekday = new Intl.DateTimeFormat('pl-PL', { weekday: 'long' })
const monthName = new Intl.DateTimeFormat('pl-PL', { month: 'long', year: 'numeric' })

export function toIso(day: Date): string {
  const month = String(day.getMonth() + 1).padStart(2, '0')
  return `${day.getFullYear()}-${month}-${String(day.getDate()).padStart(2, '0')}`
}

export const todayIso = () => toIso(new Date())

/** RRRR-MM-DD jako data lokalna (bez przesunięć strefy czasowej); niepoprawna data → null. */
export function parseIso(value: string | null | undefined): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? '')
  if (!match) return null
  const day = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
  return toIso(day) === value ? day : null
}

export function addDays(day: Date, days: number): Date {
  const next = new Date(day)
  next.setDate(next.getDate() + days)
  return next
}

export const daysBetween = (from: Date, to: Date) => Math.round((to.getTime() - from.getTime()) / DAY_MS)

/** RRRR-MM-DD → „14.01.2026”; brak daty → „—”. */
export function formatIso(value: string | null | undefined): string {
  const day = parseIso(value)
  return day ? shortDate.format(day) : '—'
}

/** „2026-11-21 20:35:12” (czas zapisu w bazie) → „2026-11-21 20:35”. */
export const formatTimestamp = (value: string) => value.slice(0, 16).replace('T', ' ')

export const formatLong = (day: Date) => longDate.format(day)
export const formatWeekday = (day: Date) => weekday.format(day)
export const formatMonth = (day: Date) => monthName.format(day)
