// Presets never carry credentials, model guesses, or automatic provider activation.
export const ACTELYO_PROVIDER_PRESETS = [
  { id: 'actelyo', name: 'Actelyo', baseUrl: '', helpUrl: 'https://actelyo.com' },
  { id: 'openrouter', name: 'OpenRouter', baseUrl: 'https://openrouter.ai/api/v1', helpUrl: 'https://openrouter.ai/settings/keys' },
  // Port 3001 belongs to Actelyo RAG. Configure FreeLLMAPI with PORT=3002.
  { id: 'freellmapi', name: 'FreeLLMAPI', baseUrl: 'http://127.0.0.1:3002/v1', helpUrl: 'https://github.com/tashfeenahmed/freellmapi#quick-start' },
  { id: 'omniroute', name: 'OmniRoute', baseUrl: 'http://127.0.0.1:20128/v1', helpUrl: 'https://github.com/diegosouzapw/OmniRoute#-quick-start' }
] as const
