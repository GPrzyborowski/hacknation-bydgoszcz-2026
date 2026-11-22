/** Nazwy klas z pominięciem pustych: cx('cal-day', isToday && 'is-today'). */
export const cx = (...names: (string | false | null | undefined)[]) => names.filter(Boolean).join(' ')

export function focusById(id: string) {
  document.getElementById(id)?.focus()
}

/** Zapisuje plik z odpowiedzi API na dysku użytkownika. */
export function saveFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = Object.assign(document.createElement('a'), { href: url, download: filename })
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
