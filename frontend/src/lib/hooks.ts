import { useCallback, useEffect, useEffectEvent, useMemo, useState } from 'react'
import { errorMessage, listDepartments } from './api'

type QueryKey = string | number | boolean | null

/**
 * Dane z API: pobierane przy montowaniu, po zmianie `key` i po `reload()`.
 * Poprzednie dane zostają na ekranie do nadejścia nowych, a spóźniona odpowiedź jest pomijana.
 */
export function useQuery<T>(load: () => Promise<T>, key: QueryKey = null) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)
  const fetchData = useEffectEvent(load)

  useEffect(() => {
    let current = true
    fetchData().then(
      (result) => {
        if (!current) return
        setData(result)
        setError(null)
      },
      (failure: unknown) => {
        if (current) setError(errorMessage(failure))
      },
    )
    return () => {
      current = false
    }
  }, [key, version])

  const reload = useCallback(() => setVersion((value) => value + 1), [])
  return { data, error, reload, setData }
}

/**
 * Akcja użytkownika (zapis formularza, pobranie pliku): która akcja trwa i ostatni błąd.
 * `run` zwraca wynik albo `undefined`, gdy akcja się nie powiodła — komunikat trafia wtedy do `error`.
 */
export function useAction() {
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async <T>(action: () => Promise<T>, label = 'busy'): Promise<T | undefined> => {
    setBusy(label)
    setError(null)
    try {
      return await action()
    } catch (failure) {
      setError(errorMessage(failure))
      return undefined
    } finally {
      setBusy(null)
    }
  }, [])

  return { busy, error, setError, run }
}

/** Aktywne komórki urzędu oraz nazwa komórki po symbolu (także nieaktywnej). */
export function useDepartments() {
  const { data } = useQuery(listDepartments)
  const departments = useMemo(() => (data ?? []).filter((department) => department.is_active), [data])
  const nameOf = useCallback((code: string) => data?.find((department) => department.code === code)?.name ?? code, [data])
  return { departments, nameOf }
}
