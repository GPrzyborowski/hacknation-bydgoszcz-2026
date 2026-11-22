import type { ReactNode } from 'react'

/** Para „etykieta — wartość” na liście faktów (`<dl className="facts">`). */
export function Fact({ term, numeric = false, children }: { term: string; numeric?: boolean; children: ReactNode }) {
  return (
    <div>
      <dt>{term}</dt>
      <dd className={numeric ? 'num' : undefined}>{children}</dd>
    </div>
  )
}
