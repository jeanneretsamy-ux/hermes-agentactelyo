import type { LegalSnapshot, RpcMethods } from '@hermes/shared'
import type { FormEvent, ReactNode } from 'react'

import { Input } from '@/components/ui/input'
import type { LegalWrite } from '@/store/legal-practice'

export type LegalWriter = <M extends LegalWrite>(
  method: M,
  params: Omit<RpcMethods[M]['params'], 'profile' | 'project_id' | 'request_id'>
) => Promise<boolean>
export interface LegalSectionProps {
  data: LegalSnapshot
  write: LegalWriter
  submit: (action: () => Promise<void>) => (event: FormEvent) => void
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-sm">
      <span className="text-(--ui-text-secondary)">{label}</span>
      {children}
    </label>
  )
}

export function Choice({
  label,
  value,
  onChange,
  items
}: {
  label: string
  value: string
  onChange: (value: string) => void
  items: { id: string; label: string }[]
}) {
  return (
    <Field label={label}>
      <select
        className="h-9 w-full rounded-md border border-(--ui-stroke-secondary) bg-(--ui-chat-bubble-background) px-2"
        onChange={e => onChange(e.target.value)}
        value={value}
      >
        <option value="">Choisir…</option>
        {items.map(item => (
          <option key={item.id} value={item.id}>
            {item.label}
          </option>
        ))}
      </select>
    </Field>
  )
}

export function TextField({
  label,
  value,
  onChange,
  type = 'text',
  required = false
}: {
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
  required?: boolean
}) {
  return (
    <Field label={label}>
      <Input onChange={e => onChange(e.target.value)} required={required} type={type} value={value} />
    </Field>
  )
}
