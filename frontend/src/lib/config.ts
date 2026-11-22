import { createContext, useContext } from 'react'
import type { AppConfig } from './api'
import type { FileRules } from './files'

/** Ustawienia z backendu (GET /api/config). Widoki renderują się dopiero po ich pobraniu. */
export const ConfigContext = createContext<AppConfig | null>(null)

export function useConfig(): AppConfig {
  const config = useContext(ConfigContext)
  if (!config) throw new Error('useConfig wymaga ConfigContext.Provider z pobraną konfiguracją.')
  return config
}

type UploadKind = 'request' | 'knowledge' | 'spreadsheet'

/** Formaty i limit rozmiaru pliku danego rodzaju — te same, które sprawdza backend. */
export function useFileRules(kind: UploadKind): FileRules {
  const config = useConfig()
  return { extensions: config[`${kind}_extensions`], maxBytes: config.max_upload_mb * 1024 * 1024 }
}
