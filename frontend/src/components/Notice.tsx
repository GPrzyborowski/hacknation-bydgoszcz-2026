import type { ReactNode } from 'react'

type Tone = 'info' | 'success' | 'warning' | 'error'

/** Komunikat w ramce: tytuł w osobnym wierszu, pod nim treść. Czerwony (`error`) także dla spraw po terminie. */
export function Notice({ tone, title, children }: { tone: Tone; title?: string; children?: ReactNode }) {
  return (
    <div className={`notice notice-${tone}`} role={tone === 'success' ? 'status' : undefined}>
      {title && <strong>{title}</strong>}
      {children}
    </div>
  )
}

/** Błąd: pogrubione zdanie nagłówkowe, wyjaśnienie i opcjonalnie akcja naprawcza. Ogłaszany czytnikom ekranu. */
export function ErrorNotice({ title, message, children }: { title?: string; message: string; children?: ReactNode }) {
  return (
    <div className="notice notice-error" role="alert">
      <p>
        {title && <strong>{title}</strong>} {message}
      </p>
      {children}
    </div>
  )
}
