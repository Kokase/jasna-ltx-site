export const REPO = 'Kokase/jasna-ltx-site';
const SETTINGS_KEY = 'sync:settings';
const LAST_RUN_KEY = 'sync:last-dispatch';
export const DEFAULT_SETTINGS = { enabled: true, intervalHours: 6, time: '02:00', overwriteExisting: true };
const OFFSET = 8 * 60 * 60 * 1000;

export function validateSettings(value) {
  return value && typeof value.enabled === 'boolean'
    && typeof value.overwriteExisting === 'boolean'
    && [1, 2, 3, 4, 6, 8, 12, 24].includes(value.intervalHours)
    && typeof value.time === 'string' && /^(?:[01]\d|2[0-3]):[0-5][05]$/.test(value.time);
}

export async function readSettings(env) {
  return await env.LTX_KV.get(SETTINGS_KEY, 'json') ?? { ...DEFAULT_SETTINGS };
}

export async function saveSettings(env, settings) {
  await env.LTX_KV.put(SETTINGS_KEY, JSON.stringify(settings));
}

export function scheduleSlot(settings, timestamp) {
  const [hours, minutes] = settings.time.split(':').map(Number);
  const anchor = (hours * 60 + minutes) * 60000 - OFFSET;
  const interval = settings.intervalHours * 60 * 60 * 1000;
  return anchor + Math.floor((timestamp - anchor) / interval) * interval;
}

export function nextRun(settings, timestamp = Date.now()) {
  if (!settings.enabled) return null;
  return new Date(scheduleSlot(settings, timestamp) + settings.intervalHours * 3600000).toISOString();
}

export async function dispatchSync(env, { mode = 'all', overwriteExisting = true } = {}) {
  if (!env.GITHUB_TOKEN) throw new Error('Server GITHUB_TOKEN is not configured');
  const response = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/sync.yml/dispatches`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'User-Agent': 'jasna-ltx-site',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ ref: 'main', inputs: mode === 'import' ? { mode } : { overwrite_existing: overwriteExisting } }),
  });
  if (response.status !== 204 && response.status !== 200) {
    const error = new Error(`GitHub dispatch failed (${response.status})`);
    error.status = 502;
    throw error;
  }
}

export async function runScheduledSync(controller, env) {
  const settings = await readSettings(env);
  if (!settings.enabled) return;
  const timestamp = controller.scheduledTime;
  const slot = scheduleSlot(settings, timestamp);
  if (timestamp - slot >= 5 * 60000) return;
  const previous = await env.LTX_KV.get(LAST_RUN_KEY, 'json');
  if (previous?.slot >= slot) return;
  await dispatchSync(env, settings);
  await env.LTX_KV.put(LAST_RUN_KEY, JSON.stringify({ slot, dispatched_at: new Date(timestamp).toISOString() }));
}

export async function scheduleStatus(env, settings) {
  const previous = await env.LTX_KV.get(LAST_RUN_KEY, 'json');
  return { ...settings, timezone: 'Asia/Taipei', next_run: nextRun(settings), last_dispatch_at: previous?.dispatched_at ?? null };
}
