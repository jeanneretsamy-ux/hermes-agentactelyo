import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PLUGIN_CATALOG_URL, type PluginCatalogEntry } from '@/lib/plugin-catalog'
import { queryClient } from '@/lib/query-client'
import { openCatalogPluginInstall } from '@/store/plugin-catalog-install'

export function NativePluginCatalog({ profile }: { profile: null | string }) {
  const [search, setSearch] = useState('')

  const catalog = useQuery({
    queryKey: ['actelyo-plugin-catalog'],
    queryFn: async () => {
      const response = await fetch(PLUGIN_CATALOG_URL, { signal: AbortSignal.timeout(15000) })

      if (!response.ok) {
        throw new Error('Catalogue indisponible')
      }

      const rows: unknown = await response.json()

      if (!Array.isArray(rows)) {
        throw new Error('Format du catalogue invalide')
      }

      return rows.filter((row): row is PluginCatalogEntry =>
        Boolean(row && typeof row.name === 'string' && typeof row.repo === 'string' && row.repo)
      )
    }
  }, queryClient)

  return (
    <section aria-label="Catalogue de plugins Actelyo" className="h-full space-y-3 overflow-auto p-3">
      <h3 className="font-semibold">Actelyo — Catalogue de plugins</h3>
      <Input aria-label="Rechercher un plugin" onChange={event => setSearch(event.target.value)} value={search} />
      {catalog.isPending && <p role="status">Chargement du catalogue…</p>}
      {catalog.isError && (
        <div role="alert">
          <p>Impossible de charger le catalogue.</p>
          <Button onClick={() => void catalog.refetch()}>Réessayer</Button>
        </div>
      )}
      <ul className="space-y-2">
        {catalog.data
          ?.filter(row => row.name.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
          .map(row => (
            <li className="flex items-center justify-between gap-2 rounded border p-2" key={row.name}>
              <span>{row.name}</span>
              <Button onClick={() => openCatalogPluginInstall(row, profile)} type="button" variant="outline">
                Configurer l’installation
              </Button>
            </li>
          ))}
      </ul>
      <p className="text-xs text-(--ui-text-secondary)">
        Extensions tierces : leurs noms et auteurs sont conservés. L’installation demande une confirmation.
      </p>
    </section>
  )
}
