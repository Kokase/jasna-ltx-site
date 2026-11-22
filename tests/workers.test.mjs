import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { after, before, mock, test } from 'node:test';

const root = new URL('../', import.meta.url);
let worker;
let stateDirectory;
let origin;

before(async () => {
  stateDirectory = await mkdtemp(new URL('../.wrangler-test-', import.meta.url));
  worker = spawn(process.execPath, [
    'node_modules/wrangler/bin/wrangler.js', 'dev', '--local',
    '--ip', '127.0.0.1', '--port', '0', '--inspector-port', '0',
    '--persist-to', stateDirectory,
  ], {
    cwd: root,
    env: { ...process.env, CI: 'true', WRANGLER_SEND_METRICS: 'false' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  origin = await new Promise((resolve, reject) => {
    let output = '';
    const timer = setTimeout(() => reject(new Error(`Worker startup timed out:\n${output}`)), 30000);
    const onOutput = (chunk) => {
      output += chunk.toString();
      const ready = output.match(/Ready on (http:\/\/127\.0\.0\.1:\d+)/);
      if (ready) {
        clearTimeout(timer);
        resolve(ready[1]);
      }
    };
    worker.stdout.on('data', onOutput);
    worker.stderr.on('data', onOutput);
    worker.once('error', (error) => { clearTimeout(timer); reject(error); });
    worker.once('exit', (code) => {
      clearTimeout(timer);
      reject(new Error(`Worker exited with code ${code}:\n${output}`));
    });
  });
});

after(async () => {
  if (worker && worker.exitCode === null && worker.signalCode === null) {
    const exited = once(worker, 'exit');
    worker.kill('SIGTERM');
    await exited;
  }
  if (stateDirectory) await rm(stateDirectory, { recursive: true, force: true });
});

async function api(path, body) {
  const response = await fetch(origin + path, body === undefined ? {} : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return { response, body: await response.json() };
}

test('serves the existing site, downloads, headers and SPA fallback', async () => {
  const headers = await readFile(new URL('dist/client/_headers', root), 'utf8');
  assert.equal(headers.startsWith('\uFEFF'), false, 'Cloudflare deployment rejects a BOM before the first header rule');
  for (const path of ['/index.html', '/css/style.css', '/js/app.js', '/data/movies.json',
    '/xd_plus.js', '/xd_plus.css', '/robots.txt', '/xdown/icon.svg', '/dl/XDown.apk']) {
    const response = await fetch(origin + path);
    assert.equal(response.status, 200, path);
    const expected = await readFile(new URL('.' + path, root));
    assert.deepEqual(Buffer.from(await response.arrayBuffer()), expected, path);
    if (path === '/data/movies.json') {
      assert.equal(response.headers.get('Cache-Control'), 'public, max-age=86400, stale-while-revalidate=604800');
    }
  }
  const home = await fetch(origin + '/');
  assert.equal(home.headers.get('Cache-Control'), 'public, max-age=3600');
  const fallback = await fetch(origin + '/missing-page', { headers: { 'Sec-Fetch-Mode': 'navigate' } });
  assert.equal(await fallback.text(), await home.text());
});

test('does not publish server source, configuration or generated bundles', async () => {
  const home = await readFile(new URL('index.html', root), 'utf8');
  for (const path of ['/wrangler.toml', '/package.json', '/functions/api/sync.js',
    '/scripts/sync.js', '/dist/worker/index.js', '/.git/config', '/tests/workers.test.mjs']) {
    const response = await fetch(origin + path);
    assert.ok(response.status === 404 || response.status === 200, path);
    if (response.status === 200) assert.equal(await response.text(), home, path);
  }
});

test('routes API requests ahead of SPA assets and preserves CORS', async () => {
  const status = await api('/api/status');
  assert.equal(status.response.status, 200);
  assert.equal(status.body.ok, true);
  assert.equal(status.body.data.comments, 0);
  assert.equal(status.response.headers.get('Access-Control-Allow-Origin'), '*');
  const preflight = await fetch(origin + '/api/comments', { method: 'OPTIONS' });
  assert.equal(preflight.status, 204);
  assert.match(preflight.headers.get('Access-Control-Allow-Methods'), /POST/);
  const missing = await fetch(origin + '/api/unknown', { headers: { 'Sec-Fetch-Mode': 'navigate' } });
  assert.equal(missing.status, 404);
  assert.equal((await missing.json()).reason, 'not found');
  assert.equal((await api('/api/v2/app/version')).body.version, 'v4.6.0');
});

test('preserves comment creation, cooldown, likes and ownership checks with local KV', async () => {
  const created = await api('/api/comments', { code: 'TEST', body: 'Worker test', client: 'owner' });
  assert.equal(created.response.status, 200);
  const id = created.body.data.item.id;
  assert.equal(created.body.data.item.mine, true);
  assert.equal((await api('/api/comments', { code: 'TEST', body: 'Again', client: 'owner' })).response.status, 429);
  const liked = await api('/api/comments/like', { id, client: 'reader', like: true });
  assert.equal(liked.body.data.likes, 1);
  const listed = await api('/api/comments?code=TEST&client=reader');
  assert.equal(listed.body.data.items[0].liked, true);
  assert.equal((await api('/api/comments/delete', { id, client: 'reader' })).response.status, 401);
  assert.equal((await api('/api/comments/delete', { id, client: 'owner' })).body.data.deleted, true);
  assert.deepEqual((await api('/api/comments?code=TEST')).body.data.items, []);
});

test('preserves submission and feedback writes and review with local KV', async () => {
  const submission = await api('/api/submissions', { code: 'TEST', client: 'tester' });
  assert.equal(submission.body.data.ids.length, 1);
  assert.equal((await api('/api/submissions')).body.data.items[0].code, 'TEST');
  assert.equal((await api('/api/submissions/block', { voter: 'tester' })).body.data.blocked, true);
  const feedback = await api('/api/feedback', { body: 'Migration test', client: 'tester' });
  const id = feedback.body.data.item.id;
  assert.equal((await api('/api/feedback')).body.data.items[0].body, 'Migration test');
  const reviewed = await api('/api/feedback/review', { actions: [{ id, action: 'approve' }] });
  assert.equal(reviewed.body.data.results[0].status, 'approved');
  assert.equal((await api('/api/verify', {})).body.data.items[0].success, true);
  assert.equal((await api('/api/export')).body.data.comments, 0);
  assert.equal((await fetch(origin + '/api/evidence')).headers.get('Content-Type'), 'image/png');
});

test('preserves specific proxy and sync routes without contacting upstream services', async () => {
  for (const path of ['/api/img', '/api/v', '/api/fx', '/api/ts', '/api/xsearch']) {
    assert.equal((await fetch(origin + path)).status, 400, path);
  }
  for (const path of ['/api/img', '/api/v']) {
    assert.equal((await fetch(origin + path + '?u=https://example.com/test')).status, 403, path);
  }
  assert.equal((await api('/api/sync')).body.ok, true);

  // Exercise the generated router with mocked fetches for network-only routes.
  const { default: compiled } = await import(new URL('../dist/worker/index.js', import.meta.url));
  const upstream = mock.method(globalThis, 'fetch', async () => new Response('fixture'));
  try {
    for (const path of ['/api/xtest', '/api/xtest2']) {
      const response = await compiled.fetch(new Request('https://test.invalid' + path), {}, { waitUntil() {} });
      assert.equal(response.status, 200, path);
      assert.ok((await response.json()).results.length > 0, path);
    }
    const response = await compiled.fetch(new Request('https://test.invalid/api/sync', { method: 'POST' }), {}, { waitUntil() {} });
    assert.equal(response.status, 500);
  } finally {
    upstream.mock.restore();
  }
});
