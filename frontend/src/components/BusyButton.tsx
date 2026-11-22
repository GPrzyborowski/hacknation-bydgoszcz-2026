import type { ButtonHTMLAttributes } from 'react'

type Props = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'className'> & {
  busy: boolean
  /** Napis na czas trwania akcji, np. „Zapisywanie…”. */
  busyLabel: string
  variant?: 'primary' | 'secondary'
}

/** Przycisk akcji, która chwilę trwa: pokazuje postęp i blokuje ponowne kliknięcie. */
export function BusyButton({ busy, busyLabel, variant = 'primary', disabled, children, ...props }: Props) {
  return (
    <button className={`${variant}-button`} disabled={busy || disabled} {...props}>
      {busy && <span className="spinner" aria-hidden="true" />}
      {busy ? busyLabel : children}
    </button>
  )
}
