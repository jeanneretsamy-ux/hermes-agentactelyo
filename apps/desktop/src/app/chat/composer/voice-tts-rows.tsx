import { useMemo } from 'react'

import {
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  dropdownMenuRow
} from '@/components/ui/dropdown-menu'
import { saveHermesConfigRecord, type ProfileScope } from '@/hermes'
import { triggerHaptic } from '@/lib/haptics'
import { notifyError } from '@/store/notifications'
import type { HermesConfigRecord } from '@/types/hermes'

import { setHermesConfigCache, useHermesConfigRecord } from '../../hooks/use-config-record'
import { ENUM_OPTIONS } from '../../settings/constants'
import { asText, enumOptionsFor, getNested, setNested } from '../../settings/helpers'

const DEFAULT_TTS_PROVIDER = 'edge'

const TTS_MODEL_KEY_BY_PROVIDER: Record<string, string> = {
  elevenlabs: 'tts.elevenlabs.model_id',
  gemini: 'tts.gemini.model',
  kittentts: 'tts.kittentts.model',
  minimax: 'tts.minimax.model',
  mistral: 'tts.mistral.model',
  neutts: 'tts.neutts.model',
  openai: 'tts.openai.model'
}

const PROVIDER_LABELS: Record<string, string> = {
  edge: 'Microsoft Edge',
  elevenlabs: 'ElevenLabs',
  gemini: 'Gemini',
  kittentts: 'KittenTTS',
  minimax: 'MiniMax',
  mistral: 'Mistral',
  neutts: 'NeuTTS',
  openai: 'OpenAI',
  piper: 'Piper',
  xai: 'xAI'
}

const modelLabel = (model: string) => model.replace(/^KittenML\//, '').replace(/^neuphonic\//, '')
const providerLabel = (provider: string) => PROVIDER_LABELS[provider] ?? provider

function saveTtsValue(key: string, value: string, writeScope: ProfileScope | undefined) {
  const patch = setNested({}, key, value)

  setHermesConfigCache(previous => setNested(previous ?? {}, key, value))

  return saveHermesConfigRecord(patch, writeScope ?? undefined)
}

/**
 * Fast TTS picker shown next to the voice controls. The full Settings → Voice
 * page still owns API keys and advanced fields; this keeps the common
 * provider/model switch where the user actually presses Audio.
 */
export function VoiceTtsRows({ disabled }: { disabled: boolean }) {
  const { data: config, writeScope } = useHermesConfigRecord()
  const record: HermesConfigRecord = config ?? {}
  const provider = asText(getNested(record, 'tts.provider')) || DEFAULT_TTS_PROVIDER
  const providerOptions = useMemo(() => enumOptionsFor('tts.provider', provider, record) ?? [], [provider, record])
  const modelKey = TTS_MODEL_KEY_BY_PROVIDER[provider]
  const modelOptions = modelKey ? (ENUM_OPTIONS[modelKey] ?? []) : []
  const modelValue = modelKey ? asText(getNested(record, modelKey)) || modelOptions[0] || '' : ''

  if (providerOptions.length === 0) {
    return null
  }

  const saveProvider = (nextProvider: string) => {
    if (!nextProvider || nextProvider === provider) {
      return
    }

    triggerHaptic('open')
    saveTtsValue('tts.provider', nextProvider, writeScope).catch(error =>
      notifyError(error, 'TTS provider change failed')
    )
  }

  const saveModel = (nextModel: string) => {
    if (!modelKey || !nextModel || nextModel === modelValue) {
      return
    }

    triggerHaptic('open')
    saveTtsValue(modelKey, nextModel, writeScope).catch(error => notifyError(error, 'TTS model change failed'))
  }

  return (
    <>
      <DropdownMenuLabel>TTS provider</DropdownMenuLabel>
      <DropdownMenuRadioGroup onValueChange={saveProvider} value={provider}>
        {providerOptions.map(option => (
          <DropdownMenuRadioItem className={dropdownMenuRow} disabled={disabled} key={option} value={option}>
            {providerLabel(option)}
          </DropdownMenuRadioItem>
        ))}
      </DropdownMenuRadioGroup>
      {modelKey && modelOptions.length > 0 ? (
        <>
          <DropdownMenuLabel>TTS model</DropdownMenuLabel>
          <DropdownMenuRadioGroup onValueChange={saveModel} value={modelValue}>
            {modelOptions.map(option => (
              <DropdownMenuRadioItem className={dropdownMenuRow} disabled={disabled} key={option} value={option}>
                {modelLabel(option)}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </>
      ) : null}
    </>
  )
}
