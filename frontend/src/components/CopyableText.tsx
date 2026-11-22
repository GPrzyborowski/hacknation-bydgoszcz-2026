import { useId, useRef, useState } from 'react'

/** Treść do wysłania poza systemem (prośby do wydziałów): można ją poprawić i skopiować do schowka. */
export function CopyableText({ label, text, rows = 8 }: { label: string; text: string; rows?: number }) {
  const id = useId()
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    const textarea = textareaRef.current
    if (!textarea) return
    try {
      await navigator.clipboard.writeText(textarea.value)
      setCopied(true)
    } catch {
      // Schowek bywa niedostępny (strona bez HTTPS) — zaznaczony tekst można skopiować skrótem Ctrl+C.
      textarea.select()
    }
  }

  return (
    <div className="field">
      <label className="field-label small" htmlFor={id}>
        {label}
      </label>
      <textarea
        id={id}
        ref={textareaRef}
        className="input textarea"
        rows={rows}
        defaultValue={text}
        onChange={() => setCopied(false)}
      />
      <div className="actions compact">
        <button type="button" className="link-button" onClick={copy}>
          Kopiuj treść
        </button>
        <span className="meta" role="status">
          {copied ? 'Skopiowano do schowka.' : ''}
        </span>
      </div>
    </div>
  )
}
