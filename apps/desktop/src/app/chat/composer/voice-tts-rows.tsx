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
const DEFAULT_STT_PROVIDER = 'local'

const STT_MODEL_KEY_BY_PROVIDER: Record<string, string> = {
  elevenlabs: 'stt.elevenlabs.model_id',
  groq: 'stt.groq.model',
  local: 'stt.local.model',
  local_command: 'stt.local.model',
  mistral: 'stt.mistral.model',
  openai: 'stt.openai.model'
}

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
  deepinfra: 'DeepInfra',
  edge: 'Microsoft Edge',
  elevenlabs: 'ElevenLabs',
  gemini: 'Gemini',
  groq: 'Groq',
  kittentts: 'KittenTTS',
  local: 'Local Whisper',
  local_command: 'Local command / Phonon',
  minimax: 'MiniMax',
  mistral: 'Mistral',
  neutts: 'NeuTTS',
  openai: 'OpenAI',
  piper: 'Piper',
  xai: 'xAI'
}

const PHONON_STT_MODELS = ['phonon-2', 'phonon-1', 'phonon-1-big', 'phonon-1-micro']

const modelLabel = (model: string) => model.replace(/^KittenML\//, '').replace(/^neuphonic\//, '')
const providerLabel = (provider: string) => PROVIDER_LABELS[provider] ?? provider

function modelOptionsFor(key: string | undefined, provider: string): string[] {
  if (!key) {
    return []
  }

  const options = ENUM_OPTIONS[key] ?? []

  if (provider === 'local_command' && key === 'stt.local.model') {
    return [...PHONON_STT_MODELS, ...options.filter(option => !PHONON_STT_MODELS.includes(option))]
  }

  return options
}

function saveAudioValue(key: string, value: string, writeScope: ProfileScope | undefined) {
  const patch = setNested({}, key, value)

  setHermesConfigCache(previous => setNested(previous ?? {}, key, value))

  return saveHermesConfigRecord(patch, writeScope ?? undefined)
}

/**
 * Fast audio model picker shown next to the voice controls. The full Settings → Voice
 * page still owns API keys and advanced fields; this keeps the common
 * TTS/STT provider and model switches where the user actually presses Audio.
 */
export function VoiceTtsRows({ disabled }: { disabled: boolean }) {
  const { data: config, writeScope } = useHermesConfigRecord()
  const record: HermesConfigRecord = config ?? {}
  const provider = asText(getNested(record, 'tts.provider')) || DEFAULT_TTS_PROVIDER
  const providerOptions = useMemo(() => enumOptionsFor('tts.provider', provider, record) ?? [], [provider, record])
  const modelKey = TTS_MODEL_KEY_BY_PROVIDER[provider]
  const modelOptions = modelOptionsFor(modelKey, provider)
  const modelValue = modelKey ? asText(getNested(record, modelKey)) || modelOptions[0] || '' : ''
  const sttProvider = asText(getNested(record, 'stt.provider')) || DEFAULT_STT_PROVIDER
  const sttProviderOptions = useMemo(() => {
    const options = enumOptionsFor('stt.provider', sttProvider, record) ?? []

    return options.includes('local_command') ? options : [...options, 'local_command']
  }, [record, sttProvider])
  const sttModelKey = STT_MODEL_KEY_BY_PROVIDER[sttProvider]
  const sttModelOptions = modelOptionsFor(sttModelKey, sttProvider)
  const sttModelValue = sttModelKey ? asText(getNested(record, sttModelKey)) || sttModelOptions[0] || '' : ''

  if (providerOptions.length === 0 && sttProviderOptions.length === 0) {
    return null
  }

  const saveProvider = (nextProvider: string) => {
    if (!nextProvider || nextProvider === provider) {
      return
    }

    triggerHaptic('open')
    saveAudioValue('tts.provider', nextProvider, writeScope).catch(error =>
      notifyError(error, 'TTS provider change failed')
    )
  }

  const saveModel = (nextModel: string) => {
    if (!modelKey || !nextModel || nextModel === modelValue) {
      return
    }

    triggerHaptic('open')
    saveAudioValue(modelKey, nextModel, writeScope).catch(error => notifyError(error, 'TTS model change failed'))
  }

  const saveSttProvider = (nextProvider: string) => {
    if (!nextProvider || nextProvider === sttProvider) {
      return
    }

    triggerHaptic('open')
    saveAudioValue('stt.provider', nextProvider, writeScope).catch(error =>
      notifyError(error, 'STT provider change failed')
    )
  }

  const saveSttModel = (nextModel: string) => {
    if (!sttModelKey || !nextModel || nextModel === sttModelValue) {
      return
    }

    triggerHaptic('open')
    saveAudioValue(sttModelKey, nextModel, writeScope).catch(error => notifyError(error, 'STT model change failed'))
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
      <DropdownMenuLabel>STT provider</DropdownMenuLabel>
      <DropdownMenuRadioGroup onValueChange={saveSttProvider} value={sttProvider}>
        {sttProviderOptions.map(option => (
          <DropdownMenuRadioItem className={dropdownMenuRow} disabled={disabled} key={option} value={option}>
            {providerLabel(option)}
          </DropdownMenuRadioItem>
        ))}
      </DropdownMenuRadioGroup>
      {sttModelKey && sttModelOptions.length > 0 ? (
        <>
          <DropdownMenuLabel>STT model</DropdownMenuLabel>
          <DropdownMenuRadioGroup onValueChange={saveSttModel} value={sttModelValue}>
            {sttModelOptions.map(option => (
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
