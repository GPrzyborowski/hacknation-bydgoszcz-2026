import { useEffect, useState } from 'react'

const PATHS = {
  intake: '',
  register: 'rejestr',
  calendar: 'kalendarium',
  knowledge: 'baza-wiedzy',
} as const

type PageName = keyof typeof PATHS

export type Route = { name: PageName } | { name: 'case'; id: number }

const CASE_PATH = /^sprawa\/(\d+)$/

function parseHash(hash: string): Route {
  const path = hash.replace(/^#\/?/, '')
  const caseMatch = CASE_PATH.exec(path)
  if (caseMatch) return { name: 'case', id: Number(caseMatch[1]) }
  const page = (Object.keys(PATHS) as PageName[]).find((name) => PATHS[name] === path)
  return { name: page ?? 'intake' }
}

export function hrefFor(route: Route): string {
  return route.name === 'case' ? `#/sprawa/${route.id}` : `#/${PATHS[route.name]}`
}

export const caseHref = (id: number) => hrefFor({ name: 'case', id })

export function navigate(route: Route) {
  window.location.hash = hrefFor(route)
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseHash(window.location.hash))
  useEffect(() => {
    const onHashChange = () => {
      setRoute(parseHash(window.location.hash))
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])
  return route
}
