import { spawn } from 'node:child_process'

import { expect, test } from 'vitest'

import { localBackendProcess, windowsListeningPids } from './desktop-smoke-process.ts'

test('Windows listener parsing rejects adjacent ports, connections and malformed PIDs', (): void => {
  const table = `
  Proto Local Address Foreign Address State PID
  TCP 127.0.0.1:57510 0.0.0.0:0 LISTENING 123
  TCP [::1]:57510 [::]:0 LISTENING 123
  TCP 0.0.0.0:575100 0.0.0.0:0 LISTENING 456
  TCP 127.0.0.1:57510 127.0.0.1:9000 ESTABLISHED 456
  UDP 127.0.0.1:57510 *:* LISTENING 789
  TCP [::]:57510 [::]:0 LISTENING NaN
  TCP [::]:57510 [::]:0 LISTENING 0
  TCP [::]:57510 [::]:0 LISTENING 321`

  expect(windowsListeningPids(table, 57510)).toEqual([123, 321])
  expect(windowsListeningPids(table, 9999)).toEqual([])
})

test.runIf(process.platform === 'win32')('Windows identifies a real owned child listener and rejects an unrelated owner', async (): Promise<void> => {
  const child = spawn(process.execPath, ['-e', 'const s=require("node:net").createServer();s.listen(0,"127.0.0.1",()=>console.log(s.address().port))'], { stdio: ['ignore', 'pipe', 'pipe'] })

  try {
    const port = await new Promise<number>((resolve, reject): void => {
      child.once('error', reject)
      child.stdout.once('data', (data: Buffer): void => resolve(Number(data.toString().trim())))
    })

    expect(localBackendProcess(port, process.pid).pid).toBe(child.pid)
    expect((): void => { localBackendProcess(port, child.pid!) }).toThrow('found 0')
  } finally {
    const exited = new Promise<void>((resolve): void => { child.once('exit', (): void => resolve()) })
    child.kill()
    await exited
  }
}, 60_000)
