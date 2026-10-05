import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {mkdtempSync,rmSync,mkdirSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=fileURLToPath(new URL('../../../',import.meta.url));
const picker=process.env.ACTELYO_TEST_PICKER || path.join(root,'scripts/sandbox/pick-release-tags.sh');
const bash=process.env.BASH_EXE || 'bash';
function pick(repo,allow=false) {
 return spawnSync(bash,[picker,'--repo',repo,'--count','1',...(allow?['--allow-unreleased']:[])],{encoding:'utf8',cwd:root});
}

test('an unreleased checkout is opt-in; publishing tags restores the same release baseline',()=>{
 const repo=mkdtempSync(path.join(os.tmpdir(),'actelyo-e2e-tags-'));
 try {
  const git=(args)=>{const result=spawnSync('git',['-C',repo,...args],{encoding:'utf8'});assert.equal(result.status,0,result.stderr);};
  git(['init']);git(['-c','user.name=Test','-c','user.email=test@example.invalid','commit','--allow-empty','-m','fixture']);
  assert.notEqual(pick(repo).status,0,'strict release selection must reject an unreleased repo');
  const unreleased=pick(repo,true);assert.equal(unreleased.status,0,unreleased.stderr);assert.deepEqual(JSON.parse(unreleased.stdout),[]);
  git(['tag','v2026.1.1']);
  assert.deepEqual(JSON.parse(pick(repo,true).stdout),JSON.parse(pick(repo).stdout));
 }finally{rmSync(repo,{recursive:true,force:true});}
});

test('no historical releases still produces executable current-source upgrade legs and a readable report',()=>{
 const script=path.join(root,'scripts/sandbox/generate-e2e-matrix.mjs');
 const plan=spawnSync(process.execPath,[script,'--tags','[]','--route','pr'],{encoding:'utf8',cwd:root});
 assert.equal(plan.status,0,plan.stderr);
 const legs=Object.values(JSON.parse(plan.stdout)).flatMap(matrix=>matrix.include);
 assert.ok(legs.length>0);assert.ok(legs.some(leg=>leg.install_ref==='HEAD'&&leg.update_ref==='NEXT'));
 assert.ok(legs.every(leg=>leg.install_ref==='HEAD'));
 const report=spawnSync(process.execPath,[script,'--tags','[]','--format','results'],{encoding:'utf8',cwd:root,input:''});
 assert.equal(report.status,0,report.stderr);assert.ok(report.stdout.length>0);
});

test('installer Git transport reaches the same staged repository with either URL suffix',()=>{
 const work=mkdtempSync(path.join(os.tmpdir(),'actelyo-e2e-redirect-'));
 try {
  const repo=path.join(work,'repo'),serve=path.join(work,'serve.git');mkdirSync(repo);
  const git=(args)=>{const result=spawnSync('git',args,{encoding:'utf8'});assert.equal(result.status,0,result.stderr);return result.stdout.trim();};
  git(['-C',repo,'init']);git(['-C',repo,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','--allow-empty','-m','fixture']);
  const sha=git(['-C',repo,'rev-parse','HEAD']);git(['clone','--bare',repo,serve]);
  const url='https://github.com/jeanneretsamy-ux/hermes-agentactelyo';git(['-C',repo,'remote','add','origin',url]);
  for(const origin of [url,url+'.git']){
   git(['-C',repo,'remote','set-url','origin',origin]);
   const run=spawnSync(bash,['-c',`set -euo pipefail
source "$1"
fail() { echo "$*" >&2; exit 1; }
ok() { :; }
repo=$(cd "$2" && pwd); work=$(cd "$3" && pwd); serve=$(cd "$4" && pwd)
arm_source_redirect "$repo" "$work" "$serve"
is_supported_source_origin "$5.git"
is_supported_source_origin 'https://github.com/NousResearch/hermes-agent.git'
if is_supported_source_origin 'file:///tmp/serve.git'; then exit 1; fi
if is_supported_source_origin 'https://github.com/unrelated/project.git'; then exit 1; fi
[ "$(git -C "$repo" remote get-url origin)" = "$5.git" ]
for url in "$5" "$5.git"; do "$HERMES_E2E_REAL_GIT" ls-remote "$url" HEAD; done
`,'fixture',process.env.ACTELYO_TEST_REDIRECT || path.join(root,'tests/install/e2e-assets/installer-common.sh'),repo,work,serve,url],{encoding:'utf8',cwd:root});
   assert.equal(run.status,0,run.stderr);assert.ok(run.stdout.trim().split('\n').every(line=>line.startsWith(sha)));
  }
 }finally{rmSync(work,{recursive:true,force:true});}
});
