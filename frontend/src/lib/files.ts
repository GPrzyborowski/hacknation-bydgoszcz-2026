/** Wniosek jako dokument (PDF, Word) albo skan/zdjęcie pisma (JPG, PNG, TIFF). */
export const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.jpg', '.jpeg', '.png', '.tif', '.tiff'] as const
export const ACCEPTED_LABEL = 'PDF, DOCX, DOC, JPG, PNG lub TIFF'
export const ACCEPT_ATTR = [
  ...ACCEPTED_EXTENSIONS,
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'image/jpeg',
  'image/png',
  'image/tiff',
].join(',')
export const MAX_FILE_SIZE = 20 * 1024 * 1024

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot === -1 ? '' : name.slice(dot).toLowerCase()
}

export function validateFile(file: File): string | null {
  if (!(ACCEPTED_EXTENSIONS as readonly string[]).includes(extensionOf(file.name))) {
    return `nieobsługiwany format (dozwolone: ${ACCEPTED_LABEL})`
  }
  if (file.size === 0) return 'plik jest pusty'
  if (file.size > MAX_FILE_SIZE) return `plik przekracza ${formatSize(MAX_FILE_SIZE)}`
  return null
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  const mb = bytes / (1024 * 1024)
  const text = Number.isInteger(mb) ? String(mb) : mb.toFixed(1)
  return `${text.replace('.', ',')} MB`
}
