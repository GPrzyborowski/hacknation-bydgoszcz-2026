import { useEffect, useRef, useState, type DragEvent, type KeyboardEvent } from 'react'
import { cx } from '../lib/dom'
import { formatSize, formatsLabel, type FileRules } from '../lib/files'

type Props = {
  id?: string
  /** Co dodaje urzędnik, w bierniku: „wniosek”, „odpowiedź wydziału”. */
  itemName: string
  rules: FileRules
  onFiles: (files: File[]) => void
  invalid?: boolean
  disabled?: boolean
  describedBy?: string
}

const carriesFiles = (event: DragEvent) => event.dataTransfer.types.includes('Files')

/** Plik upuszczony obok strefy nie może otworzyć się w karcie przeglądarki zamiast formularza. */
function useBlockWindowDrop() {
  useEffect(() => {
    const block = (event: Event) => event.preventDefault()
    window.addEventListener('dragover', block)
    window.addEventListener('drop', block)
    return () => {
      window.removeEventListener('dragover', block)
      window.removeEventListener('drop', block)
    }
  }, [])
}

export function FileDropzone({ id, itemName, rules, onFiles, invalid = false, disabled = false, describedBy }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const dragDepth = useRef(0)
  const [isDragging, setIsDragging] = useState(false)
  useBlockWindowDrop()

  const openPicker = () => {
    if (!disabled) inputRef.current?.click()
  }

  const onDragEnter = (event: DragEvent) => {
    if (disabled || !carriesFiles(event)) return
    event.preventDefault()
    dragDepth.current += 1
    setIsDragging(true)
  }

  const onDragOver = (event: DragEvent) => {
    if (disabled || !carriesFiles(event)) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
  }

  const onDragLeave = (event: DragEvent) => {
    if (disabled || !carriesFiles(event)) return
    dragDepth.current = Math.max(0, dragDepth.current - 1)
    if (dragDepth.current === 0) setIsDragging(false)
  }

  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    dragDepth.current = 0
    setIsDragging(false)
    const files = Array.from(event.dataTransfer.files)
    if (!disabled && files.length) onFiles(files)
  }

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    openPicker()
  }

  return (
    <div
      id={id}
      className={cx('dropzone', isDragging && 'is-dragging', disabled && 'is-disabled', invalid && 'is-invalid')}
      role="button"
      // Strefa zostaje w kolejności tabulacji także podczas wysyłania, żeby fokus nie przepadał.
      tabIndex={0}
      aria-disabled={disabled}
      aria-invalid={invalid || undefined}
      aria-label={`Dodaj ${itemName}: przeciągnij i upuść plik lub wybierz go z dysku`}
      aria-describedby={describedBy}
      onClick={openPicker}
      onKeyDown={onKeyDown}
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <svg className="dropzone-icon" viewBox="0 0 48 48" aria-hidden="true">
        <g fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round">
          <path d="M14 6h14l10 10v24a2 2 0 0 1-2 2H14a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Z" />
          <path d="M28 6v10h10" />
          <path d="M25 36V22m-6 6 6-6 6 6" strokeLinecap="round" />
        </g>
      </svg>

      <div>
        <p className="dropzone-title">{isDragging ? 'Upuść plik, aby go dodać' : `Przeciągnij i upuść ${itemName} tutaj`}</p>
        <p className="dropzone-sub">
          lub <span className="dropzone-link">wybierz plik z dysku</span>
        </p>
        <p className="dropzone-hint">
          {formatsLabel(rules.extensions)} · jeden plik do {formatSize(rules.maxBytes)}
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={rules.extensions.join(',')}
        hidden
        onChange={(event) => {
          const files = Array.from(event.target.files ?? [])
          if (files.length) onFiles(files)
          event.target.value = ''
        }}
      />
    </div>
  )
}
