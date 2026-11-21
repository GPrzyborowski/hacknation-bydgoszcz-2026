import { useRef, useState, type DragEvent, type KeyboardEvent } from 'react'
import { ACCEPTED_LABEL, ACCEPT_ATTR, MAX_FILE_SIZE, formatSize } from '../lib/files'

type Props = {
  id?: string
  invalid?: boolean
  onFiles: (files: File[]) => void
  disabled?: boolean
  describedBy?: string
}

export function FileDropzone({ id, invalid = false, onFiles, disabled = false, describedBy }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const dragDepth = useRef(0)
  const [isDragging, setIsDragging] = useState(false)

  const openPicker = () => {
    if (!disabled) inputRef.current?.click()
  }

  const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer.types).includes('Files')

  const handleDragEnter = (e: DragEvent) => {
    if (disabled || !hasFiles(e)) return
    e.preventDefault()
    dragDepth.current += 1
    setIsDragging(true)
  }

  const handleDragOver = (e: DragEvent) => {
    if (disabled || !hasFiles(e)) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }

  const handleDragLeave = (e: DragEvent) => {
    if (disabled || !hasFiles(e)) return
    dragDepth.current = Math.max(0, dragDepth.current - 1)
    if (dragDepth.current === 0) setIsDragging(false)
  }

  const handleDrop = (e: DragEvent) => {
    e.preventDefault()
    dragDepth.current = 0
    setIsDragging(false)
    if (disabled) return
    const files = Array.from(e.dataTransfer.files)
    if (files.length) onFiles(files)
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      openPicker()
    }
  }

  return (
    <div
      id={id}
      className={`dropzone${isDragging ? ' is-dragging' : ''}${disabled ? ' is-disabled' : ''}${invalid ? ' is-invalid' : ''}`}
      role="button"
      // Pozostaje w kolejności tabulacji podczas wysyłania, żeby fokus nie przepadał.
      tabIndex={0}
      aria-disabled={disabled}
      aria-invalid={invalid || undefined}
      aria-label="Dodaj plik wniosku: przeciągnij i upuść lub wybierz z dysku"
      aria-describedby={describedBy}
      onClick={openPicker}
      onKeyDown={handleKeyDown}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <svg className="dropzone-icon" viewBox="0 0 48 48" aria-hidden="true">
        <path
          d="M14 6h14l10 10v24a2 2 0 0 1-2 2H14a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinejoin="round"
        />
        <path d="M28 6v10h10" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" />
        <path
          d="M25 36V22m-6 6 6-6 6 6"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>

      <div className="dropzone-text">
        <p className="dropzone-title">
          {isDragging ? 'Upuść plik, aby go dodać' : 'Przeciągnij i upuść wniosek tutaj'}
        </p>
        <p className="dropzone-sub">
          lub <span className="dropzone-link">wybierz plik z dysku</span>
        </p>
        <p className="dropzone-hint">
          {ACCEPTED_LABEL} · jeden plik do {formatSize(MAX_FILE_SIZE)}
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_ATTR}
        hidden
        onChange={(e) => {
          const files = Array.from(e.target.files ?? [])
          if (files.length) onFiles(files)
          e.target.value = ''
        }}
      />
    </div>
  )
}
