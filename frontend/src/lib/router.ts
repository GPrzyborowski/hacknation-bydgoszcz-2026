import { useEffect, useState } from 'react'

export type Route =
  | { name: 'intake' }
  | { name: 'register' }
  | { name: 'calendar' }
  | { name: 'case'; id: number }
  | { name: 'knowledge' }

export function parseHash(hash: string): Route {
  const path = hash.replace(/^#\/?/, '')
  const caseMatch = /^sprawa\/(\d+)$/.exec(path)
  if (caseMatch) return { name: 'case', id: Number(caseMatch[1]) }
  if (path === 'rejestr') return { name: 'register' }
  if (path === 'kalendarium') return { name: 'calendar' }
  if (path === 'baza-wiedzy') return { name: 'knowledge' }
  return { name: 'intake' }
}

export function hrefFor(route: Route): string {
  switch (route.name) {
    case 'register':
      return '#/rejestr'
    case 'calendar':
      return '#/kalendarium'
    case 'case':
      return `#/sprawa/${route.id}`
    case 'knowledge':
      return '#/baza-wiedzy'
    default:
      return '#/'
  }
}

export function navigate(route: Route) {
  window.location.hash = hrefFor(route)
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash))
  useEffect(() => {
    const onChange = () => {
      setRoute(parseHash(window.location.hash))
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}
