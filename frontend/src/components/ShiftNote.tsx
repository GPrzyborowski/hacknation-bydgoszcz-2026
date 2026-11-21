import { formatLong, formatWeekday } from '../lib/deadline'

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

/** Ostrzeżenie, gdy 14. dzień przypada w dzień wolny (rejestr UMB nie przesuwa terminu). */
export function ShiftNote({ day14, nextWorking }: { day14: Date; nextWorking: Date }) {
  return (
    <span className="deadline-shift">
      {capitalize(formatWeekday(day14))}, {formatLong(day14)}, to dzień wolny. Rejestr urzędu liczy termin jako 14.
      dzień od wpływu; według art. 57 § 4 KPA upłynąłby {formatLong(nextWorking)}. Bezpieczniej odpowiedzieć
      wcześniej.
    </span>
  )
}
