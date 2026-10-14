import { cn } from '@/lib/utils'

const assetPath = (path: string) => `${import.meta.env.BASE_URL}${path.replace(/^\/+/, '')}`

// The official transparent Actelyo wordmark needs a dark tile on either theme.
export function BrandMark({ className, ...props }: React.ComponentProps<'span'>) {

  return (
    <span className={cn('inline-flex size-14 shrink-0 items-center justify-center', className)} {...props}>
      <img alt="Actelyo" className="size-full object-contain rounded-lg p-1" src={assetPath('actelyo-logo.png')} style={{ backgroundColor: 'var(--actelyo-brand-tile)' }} />
    </span>
  )
}
