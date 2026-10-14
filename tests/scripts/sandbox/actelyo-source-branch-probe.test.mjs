import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import test from 'node:test';

const require = createRequire(import.meta.url);
const { sourceProbeGit } = require('../../install/e2e-assets/source-branch-probe.cjs');

function git(args, options = {}) {
  return execFileSync('git', args, { encoding: 'utf8', ...options }).trim();
}

test('Actelyo source probe follows staged main with isolated Git config', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'actelyo-source-probe-'));
  try {
    const bare = path.join(root, 'serve.git');
    const seed = path.join(root, 'seed');
    const checkout = path.join(root, 'checkout');
    const userData = path.join(root, 'user-data');
    fs.mkdirSync(seed);
    fs.mkdirSync(userData);
    git(['init', '--bare', bare]);
    git(['-C', seed, 'init']);
    git(['-C', seed, 'config', 'user.name', 'E2E']);
    git(['-C', seed, 'config', 'user.email', 'e2e@example.invalid']);
    const origin = 'https://github.com/jeanneretsamy-ux/hermes-agentactelyo.git';
    fs.writeFileSync(path.join(seed, 'revision.txt'), 'old\n');
    git(['-C', seed, 'add', '.']);
    git(['-C', seed, 'commit', '-m', 'old']);
    const staged = pathToFileURL(bare).href;
    git(['-C', seed, 'push', staged, 'HEAD:refs/heads/main']);
    git(['-C', bare, 'symbolic-ref', 'HEAD', 'refs/heads/main']);
    const redirectConfig = path.join(root, 'redirect-gitconfig');
    fs.writeFileSync(redirectConfig, `[url "${staged}"]\n  insteadOf = ${origin}\n`);
    git(['clone', origin, checkout], { env: { ...process.env, GIT_CONFIG_GLOBAL: redirectConfig } });
    assert.equal(git(['-C', checkout, 'config', '--get', 'remote.origin.url']), origin);
    const installedSha = git(['-C', checkout, 'rev-parse', 'HEAD']);
    fs.writeFileSync(path.join(seed, 'revision.txt'), 'new\n');
    git(['-C', seed, 'commit', '-am', 'new']);
    const expectedSha = git(['-C', seed, 'rev-parse', 'HEAD']);
    assert.notEqual(installedSha, expectedSha);
    git(['-C', seed, 'push', staged, 'HEAD:refs/heads/main']);
    const realGit = process.platform === 'win32'
      ? execFileSync('where.exe', ['git'], { encoding: 'utf8' }).trim().split(/\r?\n/)[0]
      : execFileSync('which', ['git'], { encoding: 'utf8' }).trim();
    const probe = sourceProbeGit(userData, realGit, staged, origin);
    const emptyConfig = path.join(root, 'empty-gitconfig');
    fs.writeFileSync(emptyConfig, '');
    const env = { ...process.env, GIT_CONFIG_GLOBAL: emptyConfig, GIT_CONFIG_NOSYSTEM: '1' };
    const runProbe = args => process.platform === 'win32'
      ? execFileSync('cmd.exe', ['/d', '/s', '/c', `""${probe}" ${args.map(arg => `"${arg}"`).join(' ')}"`],
        { encoding: 'utf8', env, windowsVerbatimArguments: true }).trim()
      : execFileSync(probe, args, { encoding: 'utf8', env }).trim();
    assert.equal(git(['-C', checkout, 'remote', 'get-url', 'origin'], { env }), origin);
    assert.equal(runProbe(['-C', checkout, 'remote', 'get-url', 'origin']), staged);
    assert.equal(runProbe(['-C', checkout, 'ls-remote', '--heads', 'origin', 'refs/heads/main']).split(/\s+/)[0], expectedSha);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('source probe refuses a non-GitHub origin', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'actelyo-source-probe-'));
  try {
    assert.throws(() => sourceProbeGit(root, 'git', 'file:///staged.git', 'https://example.com/other.git'),
      /installed GitHub origin/);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
