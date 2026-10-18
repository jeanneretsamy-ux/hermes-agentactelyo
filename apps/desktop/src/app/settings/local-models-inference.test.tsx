import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { LocalModelsInference } from './local-models-inference'

const mocks = vi.hoisted(() => ({ test: vi.fn().mockResolvedValue({ job_id: 'probe' }), watch: vi.fn() }))
vi.mock('@/components/ui/button', () => ({ Button: (props: React.ComponentProps<'button'>) => <button {...props} /> }))
vi.mock('@/hermes', () => ({ testLocalModelInference: mocks.test }))
vi.mock('./local-models-owner', () => ({ useScopedLocalModelsOwner: () => ({ profile: 'cabinet' }) }))
vi.mock('@/store/local-runtime-jobs', () => ({
  isCurrentLocalModelsOwner: () => true,
  localModelsRequestScope: () => ({ profile: 'cabinet', connectionId: null }),
  watchLocalRuntimeJobs: mocks.watch
}))
afterEach(cleanup)
it('requires an explicit click and polls the job in the selected profile', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <LocalModelsInference jobs={[]} modelId="model" />
    </QueryClientProvider>
  )
  expect(mocks.test).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Tester le modèle actif' }))
  await waitFor(() => expect(mocks.watch).toHaveBeenCalledOnce())
  expect(mocks.test).toHaveBeenCalledWith('model', { profile: 'cabinet', connectionId: null })
  expect(screen.queryByText(/Inférence réussie/)).toBeNull()
})
