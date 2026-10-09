import { useStore } from '@nanostores/react'
import { useQuery } from '@tanstack/react-query'
import { memo, type PointerEvent as ReactPointerEvent, useMemo, useRef, useState } from 'react'

import { BrandMark } from '@/components/brand-mark'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getOfficialSkills, type ProfileScope, profileScopeKey } from '@/hermes'
import { useI18n } from '@/i18n'
import { Loader2 } from '@/lib/icons'
import { useStoreSelector } from '@/lib/use-session-slice'
import { cn } from '@/lib/utils'
import {
  $hubActions,
  installHubSkill,
  notifyHubActionFailed,
  OFFICIAL_SKILLS_KEY,
  UPDATE_ALL_KEY,
  updateHubSkills
} from '@/store/hub-actions'
import { notify, notifyError } from '@/store/notifications'
import { $paneHeightOverride, setPaneHeightOverride } from '@/store/panes'

// Native Actelyo catalog: metadata and installs come from the scoped backend.
// No remote documentation page or cross-origin picker messages are loaded.
// Hub viewport height: persisted through the shared pane store (same one the
// terminal/editor panes use), dragged from the section's TOP edge — "pull the
// hub up" — clamped so neither the hub nor the skills list above vanishes.
const HUB_PANE_ID = 'capabilities-hub'
const HUB_DEFAULT_PX = 380
const HUB_MIN_PX = 120
const HUB_MAX_VH = 0.75
// Collapse threshold, mirroring DetailPane: a persisted height at/below this
// reads as "collapsed to the header" (the toggle stores 0).
const HUB_COLLAPSED_PX = 4
// Room the sash must always leave for the content ABOVE the picker (the
// installed-skills list plus its strip) so dragging the hub up can never
// crush the list to zero and shove its chrome under the hub header.
const HUB_LIST_RESERVED_PX = 176

interface EmbeddedHubPickerProps {
  /** Kept mounted but fully hidden (display:none). The Capabilities view uses
   *  this to preserve the loaded hub catalog across tab switches — a plain
   *  unmount would reload the whole catalog on every return to Skills. */
  hidden?: boolean
  /** Names of skills already installed in the scoped profile — a pick that
   *  matches is refused with a toast instead of re-running the install. */
  installedNames: ReadonlySet<string>
  /** Capabilities profile-scope override — installs land in THIS profile;
   *  undefined/null targets the app-wide active profile. */
  profile?: ProfileScope
}

/** The Skills Hub browser for the Skills tab: a resizable catalog of the live
 *  hub where every card installs with one click. Expanded by default —
 *  discovery IS the point — with a collapse toggle (persisted, like every
 *  other pane) and an update-all action. Memoized: the catalog must not sit in
 *  the parent's keystroke/re-render path. */
export const EmbeddedHubPicker = memo(function EmbeddedHubPicker({
  hidden = false,
  installedNames,
  profile
}: EmbeddedHubPickerProps) {
  const { t } = useI18n()
  const h = t.skills.hub
  // Subscribe to the ONE flag this header renders, not the whole action map —
  // $hubActions churns on every tailed log line during an install.
  const updating = useStoreSelector($hubActions, actions => actions[UPDATE_ALL_KEY]?.running ?? false)
  // Collapse state rides the same persisted height override the sash writes
  // (0 = collapsed to the header), so "Hide the hub browser" survives tab
  // switches and restarts instead of re-expanding the catalog
  // on every visit. Same contract as DetailPane.
  const heightOverride = useStore($paneHeightOverride(HUB_PANE_ID))
  const height = heightOverride ?? HUB_DEFAULT_PX
  const open = height > HUB_COLLAPSED_PX
  const [dragging, setDragging] = useState(false)
  const sectionRef = useRef<HTMLElement>(null)

  // Top-edge sash: dragging UP grows the hub (shrinking the skills list above,
  // which is the flex-1 sibling). Same gesture as DetailPane / the shell's
  // bottom panes; double-click resets to the default height. The catalog gets
  // pointer-events disabled for the duration or it swallows the pointermoves.
  const startDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) {
      return
    }

    event.preventDefault()
    const startY = event.clientY
    const startHeight = height
    // Clamp against the actual Capabilities column, not just the window: the
    // hub may never grow past "column minus the list's reserved strip", so
    // the installed list always keeps real height and its header/footer can't
    // end up sharing pixels with the hub header.
    const column = sectionRef.current?.parentElement
    const columnMax = column ? column.clientHeight - HUB_LIST_RESERVED_PX : Number.POSITIVE_INFINITY
    const max = Math.max(HUB_MIN_PX, Math.round(Math.min(window.innerHeight * HUB_MAX_VH, columnMax)))
    setDragging(true)

    const onMove = (move: globalThis.PointerEvent) => {
      setPaneHeightOverride(
        HUB_PANE_ID,
        Math.round(Math.min(max, Math.max(HUB_MIN_PX, startHeight + (startY - move.clientY))))
      )
    }

    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      setDragging(false)
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp, { once: true })
  }

  const [query, setQuery] = useState('')

  const catalog = useQuery({
    queryKey: [...OFFICIAL_SKILLS_KEY, profileScopeKey(profile)],
    queryFn: () => getOfficialSkills(profile),
    enabled: open && !hidden,
    staleTime: 60_000,
    retry: false
  })

  const runningKeys = useStoreSelector($hubActions, actions =>
    Object.keys(actions)
      .filter(key => actions[key]?.running)
      .sort()
      .join('|')
  )

  const running = useMemo(() => new Set(runningKeys.split('|')), [runningKeys])

  const skills = useMemo(() => {
    const needle = query.trim().toLowerCase()

    return (catalog.data?.skills ?? []).filter(
      skill =>
        !needle ||
        [skill.name, skill.description, skill.category, ...(skill.tags ?? [])].join(' ').toLowerCase().includes(needle)
    )
  }, [catalog.data, query])

  const install = (identifier: string, name: string) => {
    if (installedNames.has(name) || installedNames.has(identifier) || running.has(identifier)) {
      return
    }
    notify({ kind: 'success', title: h.installStarted(name), message: h.actionLog })
    void installHubSkill(identifier, profile).catch(err => notifyHubActionFailed(err, h.actionFailed, name, profile))
  }

  const updateAll = () => {
    notify({ kind: 'success', title: h.updateStarted, message: h.actionLog })
    void updateHubSkills(profile).catch(err => notifyError(err, h.actionFailed))
  }

  return (
    <section
      className={cn(
        // Shrinkable (no shrink-0) + overflow-hidden: the picker is a flex
        // child of the Capabilities column. Before, its fixed-height viewport
        // made the section's min-content height rigid, so a short window (or a
        // tall persisted drag height) starved the installed list to 0px and
        // the list's strip/footer painted straight over this header. Now the
        // section clips its own content and gives height back to the list;
        // min-h keeps the header row itself always visible.
        'relative flex min-h-9 flex-col overflow-hidden border-t border-(--ui-stroke-secondary)',
        hidden && 'hidden'
      )}
      ref={sectionRef}
    >
      {/* Top-edge drag sash — pull the whole hub section up/down. */}
      <div
        className="group/hubsash absolute inset-x-0 top-0 z-10 h-1 -translate-y-1/2 cursor-row-resize"
        onDoubleClick={() => setPaneHeightOverride(HUB_PANE_ID, undefined)}
        onPointerDown={startDrag}
      >
        <div
          className={cn(
            'absolute inset-x-0 top-1/2 h-px -translate-y-1/2 transition-colors',
            dragging ? 'bg-(--ui-stroke-secondary)' : 'group-hover/hubsash:bg-(--ui-stroke-secondary)'
          )}
        />
      </div>
      <div className="flex shrink-0 items-center justify-between px-3 py-1.5">
        <span className="flex items-center gap-2 text-[0.7rem] font-medium text-(--ui-text-tertiary)">
          <BrandMark className="size-7" />
          Actelyo · {h.pickerTitle}
        </span>
        <div className="flex items-center gap-1">
          <Button disabled={updating} onClick={updateAll} size="xs" variant="text">
            {updating && <Loader2 className="size-3 animate-spin" />}
            {updating ? h.updating : h.updateAll}
          </Button>
          <Button onClick={() => setPaneHeightOverride(HUB_PANE_ID, open ? 0 : undefined)} size="xs" variant="text">
            {open ? h.pickerHide : h.pickerBrowse}
          </Button>
        </div>
      </div>
      {open && (
        <div className="flex min-h-0 flex-col gap-2 px-3 pb-2" style={{ flex: `0 1 ${height}px` }}>
          <Input
            aria-label={t.skills.searchSkills}
            onChange={event => setQuery(event.target.value)}
            placeholder={t.skills.searchSkills}
            value={query}
          />
          <div
            aria-label={`Actelyo · ${h.pickerTitle}`}
            className="min-h-0 flex-1 overflow-auto rounded-lg border border-(--ui-stroke-secondary)"
            role="region"
          >
            {catalog.isPending && <p className="p-3 text-sm">{t.skills.loading}</p>}
            {catalog.isError && (
              <div className="p-3 text-sm" role="alert">
                {h.loadFailed}
                <Button onClick={() => void catalog.refetch()} size="xs" variant="text">
                  {t.skills.refresh}
                </Button>
              </div>
            )}
            {skills.map(skill => {
              const installed =
                skill.installed || installedNames.has(skill.name) || installedNames.has(skill.identifier)

              const installing = running.has(skill.identifier)

              return (
                <div
                  className="flex items-center gap-3 border-b border-(--ui-stroke-secondary) p-3 last:border-b-0"
                  key={skill.identifier}
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{skill.name}</p>
                    <p className="text-xs text-(--ui-text-tertiary)">{skill.description}</p>
                  </div>
                  <Button
                    disabled={installed || installing}
                    onClick={() => install(skill.identifier, skill.name)}
                    size="xs"
                    variant="textStrong"
                  >
                    {installed ? h.installed : installing ? h.installing : h.install}
                  </Button>
                </div>
              )
            })}
            {!catalog.isPending && !catalog.isError && skills.length === 0 && (
              <p className="p-3 text-sm">{h.noResults}</p>
            )}
          </div>
        </div>
      )}
    </section>
  )
})
