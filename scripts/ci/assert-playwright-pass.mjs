import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

// Release evidence must describe actual passes, including suites that still
// carry message-gated known bugs for upstream development.
export function assertActualPasses(report) {
  const tests = []
  const visit = suite => {
    for (const spec of suite.specs || []) {
      for (const test of spec.tests || []) tests.push({ title: spec.title, ...test })
    }
    for (const child of suite.suites || []) visit(child)
  }
  for (const suite of report.suites || []) visit(suite)
  if (report.errors?.length || tests.length === 0) throw new Error('Missing tests or global Playwright errors')
  const refused = tests.filter(test =>
    test.expectedStatus !== 'passed' ||
    test.annotations?.some(item => ['known-bug', 'skip', 'fixme'].includes(item.type)) ||
    test.results?.length !== 1 ||
    test.results[0].status !== 'passed'
  )
  if (refused.length) {
    throw new Error('Desktop update acceptance requires actual passes without skips, retries or known failures: ' +
      refused.map(test => test.title).join('; '))
  }
  return { actualPasses: tests.length, expectedFailures: 0, skipped: 0, retries: 0 }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  console.log(JSON.stringify(assertActualPasses(JSON.parse(fs.readFileSync(process.argv[2], 'utf8')))))
}
