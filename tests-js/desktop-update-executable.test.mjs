import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { expect, test } from 'vitest'
import { packagedExe } from '../apps/desktop/e2e/update/harness'

test.each(['Actelyo Law Harness', 'Hermes'])('finds the installed product %s and rejects a directory impostor', productName => {
  const checkout = mkdtempSync(join(tmpdir(), 'desktop-product-'))
  try {
    const app = join(checkout, 'apps', 'desktop')
    const release = join(app, 'release', 'linux-unpacked')
    mkdirSync(release, { recursive: true })
    writeFileSync(join(app, 'package.json'), '\uFEFF' + JSON.stringify({ productName }))
    writeFileSync(join(release, 'chrome-sandbox'), '')
    expect(() => packagedExe({ checkout })).toThrow('no packaged')
    const executable = join(release, productName)
    mkdirSync(executable)
    expect(() => packagedExe({ checkout })).toThrow('no packaged')
    rmSync(executable, { recursive: true })
    writeFileSync(executable, '')
    expect(packagedExe({ checkout })).toBe(executable)
  } finally {
    rmSync(checkout, { recursive: true, force: true })
  }
})
