import assert from 'node:assert/strict';
import { mock, test } from 'node:test';
import { DEFAULT_SETTINGS, nextRun, readSettings, runScheduledSync, saveSettings, validateSettings } from '../functions/_lib/sync-schedule.mjs';
import { onRequestPost } from '../functions/api/sync-settings.js';

function environment() {
  const values = new Map();
  return { values, GITHUB_TOKEN: 'server-fixture', LTX_KV: {
    get: async key => values.has(key) ? JSON.parse(values.get(key)) : null,
    put: async (key, value) => values.set(key, value),
  } };
}

test('schedule validates five-minute precision, interval and booleans', () => {
  assert.equal(validateSettings(DEFAULT_SETTINGS), true);
  for (const change of [{ time: '24:00' }, { time: '02:03' }, { intervalHours: 5 }, { enabled: 'true' }, { overwriteExisting: null }]) {
    assert.equal(Boolean(validateSettings({ ...DEFAULT_SETTINGS, ...change })), false);
  }
});

test('schedule uses UTC+8 across midnight and restores persisted settings', async () => {
  assert.equal(nextRun(DEFAULT_SETTINGS, Date.parse('2026-11-23T17:59:00Z')), '2026-11-23T18:00:00.000Z');
  assert.equal(nextRun({ ...DEFAULT_SETTINGS, enabled: false }), null);
  const env = environment();
  assert.deepEqual(await readSettings(env), DEFAULT_SETTINGS);
  const settings = { ...DEFAULT_SETTINGS, time: '23:55', intervalHours: 24 };
  await saveSettings(env, settings);
  assert.deepEqual(await readSettings(env), settings);
  assert.equal(nextRun(settings, Date.parse('2026-11-23T15:56:00Z')), '2026-11-24T15:55:00.000Z');
});

test('cron dispatches only due enabled slots once and retries failures', async () => {
  const env = environment();
  let calls = 0;
  let status = 502;
  const upstream = mock.method(globalThis, 'fetch', async (url, options) => {
    calls++;
    assert.match(url, /Kokase\/jasna-ltx-site\/actions\/workflows\/sync.yml\/dispatches$/);
    assert.deepEqual(JSON.parse(options.body), { ref: 'main', inputs: { overwrite_existing: true } });
    return new Response(null, { status });
  });
  const run = iso => runScheduledSync({ scheduledTime: Date.parse(iso) }, env);
  try {
    await run('2026-11-23T17:55:00Z');
    assert.equal(calls, 0);
    await assert.rejects(run('2026-11-23T18:00:00Z'), /502/);
    status = 204;
    await run('2026-11-23T18:00:00Z');
    await run('2026-11-23T18:00:00Z');
    assert.equal(calls, 2);
    await saveSettings(env, { ...DEFAULT_SETTINGS, enabled: false });
    await run('2026-11-24T00:00:00Z');
    assert.equal(calls, 2);
  } finally { upstream.mock.restore(); }
});

test('settings writes require authenticated repository write access and reject invalid inputs', async () => {
  const env = environment();
  const request = (body, authenticated = true) => new Request('https://test.invalid/api/sync-settings', {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...(authenticated ? { Authorization: 'Bearer browser-fixture' } : {}) },
    body: JSON.stringify(body),
  });
  let allowed = false;
  const upstream = mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'https://api.github.com/repos/Kokase/jasna-ltx-site');
    assert.equal(options.headers.Authorization, 'Bearer browser-fixture');
    return Response.json({ permissions: { push: allowed } });
  });
  try {
    assert.equal((await onRequestPost({ env, request: request(DEFAULT_SETTINGS, false) })).status, 401);
    assert.equal((await onRequestPost({ env, request: request(DEFAULT_SETTINGS) })).status, 403);
    assert.equal(env.values.size, 0);
    allowed = true;
    assert.equal((await onRequestPost({ env, request: request({ ...DEFAULT_SETTINGS, time: 'bad' }) })).status, 400);
    const settings = { ...DEFAULT_SETTINGS, enabled: false, overwriteExisting: false };
    const response = await onRequestPost({ env, request: request({ ...settings, token: 'must-not-save' }) });
    assert.equal(response.status, 200);
    assert.deepEqual(await readSettings(env), settings);
    assert.equal(JSON.stringify([...env.values]).includes('must-not-save'), false);
    assert.equal((await response.json()).data.next_run, null);
  } finally { upstream.mock.restore(); }
});
