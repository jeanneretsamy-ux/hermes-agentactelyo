import { expect, it, vi } from 'vitest'

import { attachImageBatch } from './attach-image-batch'

it('waits for each image, retaining the demonstrated order', async () => {
  let finish!: (ok: boolean) => void

  const attach = vi
    .fn()
    .mockImplementationOnce(
      () =>
        new Promise(resolve => {
          finish = resolve
        })
    )
    .mockResolvedValue(true)

  const images = [new Blob(['first']), new Blob(['second'])]
  const pending = attachImageBatch(images, attach, () => true)
  expect(attach).toHaveBeenCalledTimes(1)
  finish(true)
  expect(await pending).toBe(true)
  expect(attach.mock.calls.map(call => call[0])).toEqual(images)
})

it('stops at a failed image or a destination change, including a change during upload', async () => {
  const images = [new Blob(['first']), new Blob(['second'])]
  const failed = vi.fn().mockResolvedValue(false)
  expect(await attachImageBatch(images, failed, () => true)).toBe(false)
  expect(failed).toHaveBeenCalledTimes(1)
  let current = true

  const moved = vi.fn(async (_blob, guard) => {
    current = false

    return guard()
  })

  expect(await attachImageBatch(images, moved, () => current)).toBe(false)
  expect(moved).toHaveBeenCalledTimes(1)
})
