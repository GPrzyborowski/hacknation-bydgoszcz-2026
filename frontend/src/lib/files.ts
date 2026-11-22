/** Wstępna kontrola pliku w przeglądarce, zanim trafi do backendu. */

export type FileRules = { extensions: string[]; maxBytes: number }

const FORMAT_ALIASES: Record<string, string> = { JPEG: 'JPG', TIF: 'TIFF' }

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot === -1 ? '' : name.slice(dot).toLowerCase()
}

/** [".pdf", ".docx", ".jpg", ".jpeg"] → „PDF, DOCX lub JPG”. */
export function formatsLabel(extensions: string[]): string {
  const labels = [...new Set(extensions.map((ext) => ext.slice(1).toUpperCase()).map((label) => FORMAT_ALIASES[label] ?? label))]
  return labels.length > 1 ? `${labels.slice(0, -1).join(', ')} lub ${labels.at(-1)}` : (labels[0] ?? '')
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  const megabytes = bytes / (1024 * 1024)
  return `${(Number.isInteger(megabytes) ? String(megabytes) : megabytes.toFixed(1)).replace('.', ',')} MB`
}

export function validateFile(file: File, rules: FileRules): string | null {
  if (!rules.extensions.includes(extensionOf(file.name))) {
    return `nieobsługiwany format (dozwolone: ${formatsLabel(rules.extensions)})`
  }
  if (file.size === 0) return 'plik jest pusty'
  if (file.size > rules.maxBytes) return `plik przekracza ${formatSize(rules.maxBytes)}`
  return null
}
