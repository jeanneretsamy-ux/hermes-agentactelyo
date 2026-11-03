/** Browser fixture for the real runtime loader, registry and plugin lifecycle.
 * No mock plugin SDK or generated result; only the Electron shell is absent.
 */
import React, { useState, useSyncExternalStore } from 'react'
import { createRoot } from 'react-dom/client'

import { $pluginRecords, setPluginEnabled } from '@/contrib/plugins-store'
import { registry } from '@/contrib/registry'
import { loadRuntimePlugin, unloadRuntimePlugin } from '@/contrib/runtime-loader'

const area = 'secondarySidebar'
const subscribe = (listener: () => void) => registry.subscribeArea(area, listener)
const snapshot = () => registry.getArea(area)

function Workshop() {
  const panes = useSyncExternalStore(subscribe, snapshot)
  const records = useSyncExternalStore($pluginRecords.subscribe, $pluginRecords.get)
  const [selected, setSelected] = useState('')
  const [status, setStatus] = useState('Aucun plugin chargé.')

  async function load(file: File | undefined) {
    if (!file) return
    const id = await loadRuntimePlugin(await file.text(), file.name, { defaultEnabled: false })
    if (!id) {
      setStatus('Échec du chargement.')
      return
    }
    setSelected(id)
    setStatus(`Chargé : ${id}`)
  }

  return (
    <main>
      <h1>Atelier — chargeur réel</h1>
      <p>Fixture de test du Desktop, sans compte ni shell Electron.</p>
      <label>
        Fichier du plugin
        <input type="file" accept=".js" onChange={e => void load(e.target.files?.[0])} />
      </label>
      <label>
        Plugin
        <select value={selected} onChange={e => setSelected(e.target.value)}>
          <option value="">Choisir</option>
          {Object.values(records).map(row => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
      </label>
      <button disabled={!selected} onClick={() => void setPluginEnabled(selected, true)}>
        Activer
      </button>
      <button disabled={!selected} onClick={() => void setPluginEnabled(selected, false)}>
        Désactiver
      </button>
      <button
        disabled={!selected}
        onClick={() => {
          unloadRuntimePlugin(selected)
          setSelected('')
          setStatus('Déchargé.')
        }}
      >
        Décharger
      </button>
      <p role="status">{status}</p>
      <p data-testid="pane-count">{panes.length} panneau(x)</p>
      {panes.map(pane => (
        <section key={pane.id} data-plugin-pane={pane.id}>
          {pane.render?.()}
        </section>
      ))}
    </main>
  )
}

createRoot(document.getElementById('root')!).render(<Workshop />)
