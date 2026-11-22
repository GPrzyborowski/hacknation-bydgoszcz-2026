import { ErrorNotice } from './components/Notice'
import { getConfig } from './lib/api'
import { ConfigContext } from './lib/config'
import { cx } from './lib/dom'
import { useQuery } from './lib/hooks'
import { hrefFor, useRoute, type Route } from './lib/router'
import { CalendarView } from './views/CalendarView'
import { CaseView } from './views/case/CaseView'
import { IntakeView } from './views/intake/IntakeView'
import { KnowledgeView } from './views/KnowledgeView'
import { RegisterView } from './views/RegisterView'
import './App.css'
import './views.css'

const TABS: { route: Route; label: string; alsoCurrentOn?: Route['name'] }[] = [
  { route: { name: 'intake' }, label: 'Nowy wniosek' },
  { route: { name: 'register' }, label: 'Rejestr wniosków', alsoCurrentOn: 'case' },
  { route: { name: 'calendar' }, label: 'Kalendarium' },
  { route: { name: 'knowledge' }, label: 'Baza wiedzy' },
]

export default function App() {
  const route = useRoute()
  const config = useQuery(getConfig)
  // Formularz wniosku ma wąską kolumnę do czytania; rejestr, kalendarium i karta sprawy potrzebują szerokości.
  const wide = route.name !== 'intake'

  return (
    <div className="page">
      <a className="skip-link" href="#tresc">
        Przejdź do treści
      </a>

      <header className="topbar">
        <div className="container container-wide topbar-inner">
          <div className="brand">
            <span className="brand-name">UDIPilot</span>
            <span className="brand-org">Urząd Miasta Bydgoszczy</span>
          </div>
          {config.data && !config.data.llm_enabled && <MissingKeyBadge />}
        </div>
        <nav className="tabs" aria-label="Sekcje">
          <div className="container container-wide tabs-inner">
            {TABS.map((tab) => {
              const current = route.name === tab.route.name || route.name === tab.alsoCurrentOn
              return (
                <a
                  key={tab.label}
                  href={hrefFor(tab.route)}
                  className={cx('tab', current && 'is-current')}
                  aria-current={current ? 'page' : undefined}
                >
                  {tab.label}
                </a>
              )
            })}
          </div>
        </nav>
      </header>

      <main id="tresc" className={cx('container main', wide && 'container-wide')}>
        {config.data ? (
          <ConfigContext value={config.data}>
            <Page route={route} />
          </ConfigContext>
        ) : config.error ? (
          <ErrorNotice title="Brak połączenia z serwerem aplikacji." message={config.error}>
            <button type="button" className="secondary-button" onClick={config.reload}>
              Spróbuj ponownie
            </button>
          </ErrorNotice>
        ) : (
          <p className="field-hint">Łączenie z serwerem…</p>
        )}
      </main>

      <footer className="footer">
        <div className={cx('container', wide && 'container-wide')}>
          Narzędzie pomocnicze · nic nie jest wysyłane automatycznie do wydziałów ani wnioskodawców
        </div>
      </footer>
    </div>
  )
}

/** Widoczne tylko przy braku klucza — bez niego analiza wniosków i projekty pism nie działają. */
function MissingKeyBadge() {
  return (
    <span className="model-badge is-missing" title="Wpisz GEMINI_API_KEY w pliku .env i uruchom ponownie backend.">
      Brak klucza Gemini
    </span>
  )
}

function Page({ route }: { route: Route }) {
  switch (route.name) {
    case 'intake':
      return <IntakeView />
    case 'register':
      return <RegisterView />
    case 'calendar':
      return <CalendarView />
    case 'knowledge':
      return <KnowledgeView />
    case 'case':
      return <CaseView key={route.id} id={route.id} />
  }
}
