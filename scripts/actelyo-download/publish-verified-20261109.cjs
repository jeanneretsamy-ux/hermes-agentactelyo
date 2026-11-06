// Stream the verified public-source installer from CI to an immutable draft release.
// No multi-gigabyte installer is staged on this space-constrained PC.
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const { Readable, Transform, Writable } = require('node:stream');
const { pipeline } = require('node:stream/promises');
const repo = 'jeanneretsamy-ux/hermes-agentactelyo';
const source = 'c466b3238d25b52a4b6159a0e2a68817f28554b6';
const runId = '42252422093';
const version = '2026.11.9';
const out = path.resolve('outputs/provider-upgrade/public-law-' + version);
const publish = process.argv.includes('--publish-verified-public-source');
if (process.env.GITHUB_REPOSITORY !== repo || process.env.GITHUB_ACTIONS !== 'true') throw Error('Dedicated publication workflow required');
const token = process.env.GITHUB_TOKEN;
if (!token) throw Error('Workflow token required');
const headers = { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json' };
async function api(route, method = 'GET', body, missing = false) {
  const response = await fetch('https://api.github.com/' + route, {
    method, headers: { ...headers, 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(60000)
  });
  if (missing && response.status === 404) return null;
  if (!response.ok) throw Error('GitHub HTTP ' + response.status);
  return response.json();
}
async function archive(id) {
  const response = await fetch(`https://api.github.com/repos/${repo}/actions/artifacts/${id}/zip`, {
    headers, redirect: 'manual', signal: AbortSignal.timeout(60000)
  });
  if (response.status !== 302) throw Error('Artifact HTTP ' + response.status);
  const url = new URL(response.headers.get('location'));
  if (url.protocol !== 'https:' || !url.hostname.endsWith('.blob.core.windows.net')) throw Error('Unexpected artifact host');
  async function range(start, end) {
    const r = await fetch(url, { headers: { Range: `bytes=${start}-${end}` }, signal: AbortSignal.timeout(1200000) });
    if (r.status !== 206 || r.headers.get('content-range')?.split('/')[0] !== `bytes ${start}-${end}`) {
      await r.body?.cancel(); throw Error('Invalid byte-range response');
    }
    return r;
  }
  const head = await fetch(url, { method: 'HEAD', signal: AbortSignal.timeout(60000) });
  const total = Number(head.headers.get('content-length'));
  if (!head.ok || !Number.isSafeInteger(total) || total < 22 || total >= 0xffffffff) throw Error('Unsupported archive size');
  const tail = Buffer.from(await (await range(Math.max(0, total - 65536), total - 1)).arrayBuffer());
  let end = -1;
  for (let i = tail.length - 22; i >= 0; i--) if (tail.readUInt32LE(i) === 0x06054b50) { end = i; break; }
  if (end < 0) throw Error('ZIP footer missing');
  const size = tail.readUInt32LE(end + 12), offset = tail.readUInt32LE(end + 16);
  if (size > 2000000 || !size) throw Error('Unexpected ZIP directory');
  const directory = Buffer.from(await (await range(offset, offset + size - 1)).arrayBuffer());
  const entries = new Map();
  for (let cursor = 0; cursor < directory.length;) {
    if (directory.readUInt32LE(cursor) !== 0x02014b50) throw Error('Bad ZIP directory');
    const length = directory.readUInt16LE(cursor + 28), extra = directory.readUInt16LE(cursor + 30), comment = directory.readUInt16LE(cursor + 32);
    const name = path.posix.basename(directory.subarray(cursor + 46, cursor + 46 + length).toString());
    if (entries.has(name)) throw Error('Duplicate ZIP entry');
    entries.set(name, { method: directory.readUInt16LE(cursor + 10), compressed: directory.readUInt32LE(cursor + 20), bytes: directory.readUInt32LE(cursor + 24), local: directory.readUInt32LE(cursor + 42) });
    cursor += 46 + length + extra + comment;
  }
  async function stream(name) {
    const entry = entries.get(name);
    if (!entry || ![0, 8].includes(entry.method) || entry.compressed < 1) throw Error('Invalid artifact entry ' + name);
    const local = Buffer.from(await (await range(entry.local, entry.local + 29)).arrayBuffer());
    if (local.readUInt32LE(0) !== 0x04034b50) throw Error('Bad local ZIP header');
    const start = entry.local + 30 + local.readUInt16LE(26) + local.readUInt16LE(28);
    const response = await range(start, start + entry.compressed - 1);
    const input = Readable.fromWeb(response.body);
    if (entry.method === 0) return input;
    const inflate = zlib.createInflateRaw(); input.on('error', error => inflate.destroy(error)); input.pipe(inflate); return inflate;
  }
  async function small(name) {
    const entry = entries.get(name);
    if (!entry || entry.bytes > 5000000) throw Error('Small proof missing or oversized: ' + name);
    const chunks = []; let length = 0;
    for await (const chunk of await stream(name)) { length += chunk.length; if (length > entry.bytes) throw Error('Proof length exceeded'); chunks.push(chunk); }
    if (length !== entry.bytes) throw Error('Truncated proof');
    return Buffer.concat(chunks);
  }
  return { entries, stream, small };
}
const json = bytes => JSON.parse(bytes.toString('utf8').replace(/^\uFEFF/, ''));
(async () => {
  const [repository, run, artifacts] = await Promise.all([
    api('repos/' + repo), api(`repos/${repo}/actions/runs/${runId}`), api(`repos/${repo}/actions/runs/${runId}/artifacts`)
  ]);
  if (repository.private || run.conclusion !== 'success' || run.head_sha !== source) throw Error('Access, source or Windows QA is not verified');
  const installer = artifacts.artifacts.filter(a => a.name === 'actelyo-law-harness-verified-installer' && !a.expired);
  const proof = artifacts.artifacts.filter(a => a.name === 'actelyo-law-harness-windows-verification' && !a.expired);
  if (installer.length !== 1 || proof.length !== 1) throw Error('Exact review artifacts missing');
  const [bundle, evidence] = await Promise.all([archive(installer[0].id), archive(proof[0].id)]);
  const manifest = json(await bundle.small('build-manifest.json'));
  const parts = json(await bundle.small('parts.json'));
  const native = json(await evidence.small('native-window-branding.json'));
  if (manifest.source_commit !== source || manifest.version !== version || manifest.verified_installed !== true || manifest.model_included !== false || !native.matchingPixels || native.personalProfileUsed !== false) throw Error('Installed native application proof differs');
  if (parts.artifact !== `Actelyo-Law-Harness-Setup-${version}-x64.exe` || parts.sha256 !== manifest.sha256 || parts.bytes !== manifest.bytes || !/^[a-f0-9]{64}$/.test(parts.sha256) || parts.parts.length < 2 || parts.parts.length > 5) throw Error('Invalid installer manifest');
  let sum = 0;
  for (const [index, part] of parts.parts.entries()) {
    if (part.name !== parts.artifact + '.part' + String(index + 1).padStart(2, '0') || !Number.isSafeInteger(part.bytes) || part.bytes < 1 || part.bytes > 1000000000 || !/^[a-f0-9]{64}$/.test(part.sha256) || bundle.entries.get(part.name)?.bytes !== part.bytes) throw Error('Invalid part manifest');
    sum += part.bytes;
  }
  if (sum !== parts.bytes) throw Error('Part sizes do not match installer');
  fs.mkdirSync(out, { recursive: true });
  for (const [name, value] of [['build-manifest.json', manifest], ['parts.json', parts], ['native-window-branding.json', native]]) fs.writeFileSync(path.join(out, name), JSON.stringify(value, null, 2));
  console.log('Verified Windows installation, exact source and native icon; ' + parts.parts.length + ' parts');
  if (!publish) { console.log('Read-only review complete; no release created'); return; }
  const base = 'repos/' + repo, tag = 'desktop-law-v' + version;
  let release = await api(base + '/releases/tags/' + tag, 'GET', undefined, true);
  if (!release) release = await api(base + '/releases', 'POST', {
    tag_name: tag, target_commitish: source, name: 'Actelyo Law Harness ' + version, draft: true, prerelease: false, make_latest: 'false',
    body: 'Windows x64 — candidat 2026.11.9 non signé. Cabinet natif relié à l’ERP, atelier de plugins et recherche sourcée. Installation Windows, navigation et logo violet natif vérifiés sur cet installateur exact. Les fonctions financières partagées nécessitent la connexion ERP ; les modèles et clés sont à configurer séparément. Aucune certification de qualité juridique, inférence réelle, transmission fiscale, signature ou parité mobile complète. Les sources applicatives c466b323 et dfe8f6f9 sont identiques hors workflows CI et collecte des preuves.'
  });
  const fullHash = crypto.createHash('sha256');
  async function upload(name, size, digest, body) {
    const url = new URL(release.upload_url.replace(/\{.*$/, ''));
    if (url.protocol !== 'https:' || url.hostname !== 'uploads.github.com') throw Error('Invalid upload host');
    url.searchParams.set('name', name);
    const response = await fetch(url, { method: 'POST', headers: { ...headers, 'Content-Type': 'application/octet-stream', 'Content-Length': String(size) }, body, duplex: 'half', signal: AbortSignal.timeout(1800000) });
    if (!response.ok) throw Error('Upload HTTP ' + response.status);
    const asset = await response.json();
    if (asset.size !== size || asset.digest !== 'sha256:' + digest) throw Error('Uploaded digest mismatch');
  }
  for (const part of parts.parts) {
    const existing = release.assets.find(a => a.name === part.name);
    if (existing && (existing.digest !== 'sha256:' + part.sha256 || existing.size !== part.bytes)) throw Error('Existing asset differs; refusing overwrite');
    if (!existing && !release.draft) throw Error('Public release cannot be changed');
    const hash = crypto.createHash('sha256'); let count = 0;
    const measure = new Transform({ transform(chunk, _encoding, done) { count += chunk.length; if (count > part.bytes) return done(Error('Part size exceeded')); hash.update(chunk); fullHash.update(chunk); done(null, chunk); } });
    const input = await bundle.stream(part.name);
    if (existing) await pipeline(input, measure, new Writable({ write(_chunk, _encoding, done) { done(); } }));
    else {
      const staged = path.join(out, part.name + '.staged');
      await pipeline(input, measure, fs.createWriteStream(staged));
      try { if (count !== part.bytes || hash.copy().digest('hex') !== part.sha256) throw Error('Staged part hash differs'); await upload(part.name, part.bytes, part.sha256, fs.createReadStream(staged)); fs.unlinkSync(staged); }
      catch (error) { input.destroy(error); measure.destroy(error); throw error; }
    }
    if (count !== part.bytes || hash.digest('hex') !== part.sha256) throw Error('Streamed part verification failed');
    console.log('Verified streamed ' + part.name);
  }
  if (fullHash.digest('hex') !== parts.sha256) throw Error('Reconstituted installer SHA-256 mismatch; draft remains unpublished');
  for (const name of ['SHA256SUMS.txt', 'build-manifest.json', 'parts.json']) {
    const buffer = await bundle.small(name), digest = crypto.createHash('sha256').update(buffer).digest('hex');
    const existing = release.assets.find(a => a.name === name);
    if (existing) { if (existing.size !== buffer.length || existing.digest !== 'sha256:' + digest) throw Error('Existing manifest differs'); }
    else { if (!release.draft) throw Error('Public release cannot be changed'); await upload(name, buffer.length, digest, buffer); }
  }
  for (const name of ['native-window-branding.json', 'native-window-icon.png', 'verification.json']) {
    const buffer = await evidence.small(name), digest = crypto.createHash('sha256').update(buffer).digest('hex');
    const existing = release.assets.find(a => a.name === name);
    if (existing) { if (existing.size !== buffer.length || existing.digest !== 'sha256:' + digest) throw Error('Existing QA proof differs'); }
    else { if (!release.draft) throw Error('Public release cannot be changed'); await upload(name, buffer.length, digest, buffer); }
  }
  release = await api(base + '/releases/' + release.id);
  for (const part of parts.parts) if (!release.assets.some(a => a.name === part.name && a.size === part.bytes && a.digest === 'sha256:' + part.sha256)) throw Error('Release readback mismatch');
  if (release.draft) release = await api(base + '/releases/' + release.id, 'PATCH', { draft: false, make_latest: 'false' });
  const published = [];
  for (const part of parts.parts) {
    const asset = release.assets.find(a => a.name === part.name);
    const response = await fetch(asset.browser_download_url, { method: 'HEAD', signal: AbortSignal.timeout(60000) });
    if (!response.ok) throw Error('Public download unavailable HTTP ' + response.status);
    published.push({ ...part, url: asset.browser_download_url });
  }
  const receipt = { version, source, qaRun: runId, release: release.html_url, file: parts.artifact, bytes: parts.bytes, sha256: parts.sha256, parts: published, publicAvailabilityVerified: true };
  fs.writeFileSync(path.join(out, 'publication.json'), JSON.stringify(receipt, null, 2)); console.log(JSON.stringify(receipt));
})().catch(error => { console.error(error.message); console.error('cause=' + (error.cause?.code || error.code || 'none') + ':' + String(error.cause?.message || '').replace(/https?:\/\/\S+/g,'[URL]')); process.exitCode = 1; });




