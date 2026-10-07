import assert from 'node:assert/strict';
import test from 'node:test';
import { planTracker } from './red-tracker.mjs';

test('disabled Issues preserve red leg details without planning an issue write', () => {
  const run = { conclusion: 'failure', html_url: 'https://github.com/example/repo/actions/runs/1', head_sha: '1234567890abcdef', created_at: '2026-10-07T00:00:00Z' };
  const jobs = [{ name: 'desktop install', conclusion: 'failure', html_url: `${run.html_url}/job/2`, steps: [{ name: 'Install HEAD', conclusion: 'failure' }] }];
  const report = planTracker(run, jobs, null, false);
  assert.equal(report.action, 'report');
  assert.ok(report.body.includes(jobs[0].html_url));
  assert.ok(report.body.includes('1 red leg(s)'));
  assert.equal(planTracker(run, jobs, null, true).action, 'open');
  assert.equal(planTracker({ ...run, conclusion: 'success' }, [], null, false).action, 'none');
});
