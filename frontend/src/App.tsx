import { useEffect, useState } from 'react'
import { getHealth, type Health } from './lib/api'
import { hrefFor, useRoute, type Route } from './lib/router'
import { CalendarView } from './views/CalendarView'
import { CaseView } from './views/CaseView'
import { IntakeView } from './views/IntakeView'
import { KnowledgeView } from './views/KnowledgeView'
import { RegisterView } from './views/RegisterView'
import './App.css'
import './views.css'

const TABS: { route: Route; label: string; match: Route['name'][] }[] = [
  { route: { name: 'intake' }, label: 'Nowy wniosek', match: ['intake'] },
  { route: { name: 'register' }, label: 'Rejestr wniosków', match: ['register', 'case'] },
  { route: { name: 'calendar' }, label: 'Kalendarium', match: ['calendar'] },
  { route: { name: 'knowledge' }, label: 'Baza wiedzy', match: ['knowledge'] },
]

function App() {
  const route = useRoute()
  const [health, setHealth] = useState<Health | null>(null)
  const [backendDown, setBackendDown] = useState(false)

  useEffect(() => {
    let alive = true
    getHealth()
      .then((h) => alive && setHealth(h))
      .catch(() => alive && setBackendDown(true))
    return () => {
      alive = false
    }
  }, [])

  const wide = route.name === 'register' || route.name === 'calendar' || route.name === 'case' || route.name === 'knowledge'

  return (
    <div className="page">
      <a className="skip-link" href="#tresc">
        Przejdź do treści
      </a>

      <header className="topbar">
        <div className="container container-wide topbar-inner">
          <div className="brand">
            <span className="brand-name">Asystent UDIP</span>
            <span className="brand-org">Urząd Miasta Bydgoszczy</span>
          </div>
          {health && (
            <span
              className="badge-local"
              title={
                health.llm_enabled
                  ? 'Treść wniosków jest analizowana przez model Google Gemini — używaj danych testowych.'
                  : 'Brak klucza Gemini — analiza regułowa'
              }
            >
              {health.llm_enabled ? `Model: ${health.model}` : 'Bez modelu (analiza regułowa)'}
            </span>
          )}
        </div>
        <nav className="tabs" aria-label="Sekcje">
          <div className="container container-wide tabs-inner">
            {TABS.map((tab) => {
              const current = tab.match.includes(route.name)
              return (
                <a
                  key={tab.label}
                  href={hrefFor(tab.route)}
                  className={`tab${current ? ' is-current' : ''}`}
                  aria-current={current ? 'page' : undefined}
                >
                  {tab.label}
                </a>
              )
            })}
          </div>
        </nav>
      </header>

      <main id="tresc" className={`container main${wide ? ' container-wide' : ''}`}>
        {backendDown && (
          <div className="notice notice-error" role="alert">
            <p>
              <strong>Brak połączenia z serwerem aplikacji.</strong> Uruchom backend (docker compose up) i odśwież stronę.
            </p>
          </div>
        )}
        {route.name === 'intake' && <IntakeView />}
        {route.name === 'register' && <RegisterView />}
        {route.name === 'calendar' && <CalendarView />}
        {route.name === 'case' && <CaseView key={route.id} id={route.id} />}
        {route.name === 'knowledge' && <KnowledgeView />}
      </main>

      <footer className="footer">
        <div className={`container${wide ? ' container-wide' : ''}`}>
          Narzędzie pomocnicze · nic nie jest wysyłane automatycznie do wydziałów ani wnioskodawców
        </div>
      </footer>
    </div>
  )
}

export default App
