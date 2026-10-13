import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { execFileSync } from 'node:child_process'
import { pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'

const app = path.resolve(process.argv[2])
const payload = path.join(app, 'resources', 'agent-payload')
const workspace = path.resolve(process.env.GITHUB_WORKSPACE || process.cwd())
assert(app.startsWith(workspace + path.sep), 'Only the generated application may be prepared')
assert(fs.existsSync(path.join(app, 'Actelyo Law Harness.exe')), 'Wrong application')
const removed = []
let git
for (const entry of fs.readdirSync(path.join(payload, 'tools'))) {
  if (!/^git-[\w.+-]+-win32-x64$/.test(entry)) continue
  const root = path.join(payload, 'tools', entry)
  const mtab = path.join(root, 'etc', 'mtab')
  const stat = fs.lstatSync(mtab, { throwIfNoEntry: false })
  // /proc/mounts exists in MSYS, not in the native Windows filesystem.
  // Remove only the dangling link in this application copy, never its target.
  if (stat && !fs.existsSync(mtab)) {
    assert(stat.isSymbolicLink(), 'Unexpected missing mount-table entry')
    fs.unlinkSync(mtab)
    removed.push(path.relative(payload, mtab))
  }
  git = ['cmd/git.exe', 'bin/git.exe'].map(name => path.join(root, name)).find(name => fs.existsSync(name))
}
assert(git, 'Packaged Git missing')
const probe = fs.mkdtempSync(path.join(os.tmpdir(), 'actelyo-git-check-'))
const env = { ...process.env, GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: 'NUL' }
const version = execFileSync(git, ['--version'], { encoding: 'utf8', env }).trim()
execFileSync(git, ['init', '--quiet', probe], { env })
assert(fs.existsSync(path.join(probe, '.git')), 'Packaged Git cannot initialize a repository')
const { rehashPayloadDigests } = await import(pathToFileURL(path.join(workspace, 'apps/desktop/scripts/payload-digests.mjs')).href)
rehashPayloadDigests(payload)
fs.mkdirSync(path.join(workspace, 'actelyo-release'), { recursive: true })
fs.writeFileSync(path.join(workspace, 'actelyo-release/packaging-verification.json'), JSON.stringify({ sourceCommit: process.env.ACTELYO_SOURCE_SHA, removedVirtualLinks: removed, gitVersion: version, gitInitVerified: true }, null, 2))
