import { REPO, readSettings, saveSettings, scheduleStatus, validateSettings } from '../_lib/sync-schedule.mjs';

function json(value, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: {
    'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store',
  } });
}

export async function onRequestGet({ env }) {
  return json({ ok: true, data: await scheduleStatus(env, await readSettings(env)) });
}

export async function onRequestPost({ request, env }) {
  const authorization = request.headers.get('Authorization') ?? '';
  if (!/^Bearer \S+$/.test(authorization)) return json({ ok: false, error: 'GitHub authentication required' }, 401);
  let github;
  try {
    github = await fetch(`https://api.github.com/repos/${REPO}`, { headers: {
      Authorization: authorization, Accept: 'application/vnd.github+json', 'User-Agent': 'jasna-ltx-site',
    } });
  } catch {
    return json({ ok: false, error: 'GitHub authentication is unavailable' }, 502);
  }
  if (github.status === 401) return json({ ok: false, error: 'Invalid GitHub token' }, 401);
  if (github.status === 403 || github.status === 404) return json({ ok: false, error: 'Repository write access required' }, 403);
  if (!github.ok) return json({ ok: false, error: 'GitHub authentication is unavailable' }, 502);
  if (!(await github.json()).permissions?.push) return json({ ok: false, error: 'Repository write access required' }, 403);
  let settings;
  try { settings = await request.json(); }
  catch { return json({ ok: false, error: 'Invalid JSON' }, 400); }
  if (!validateSettings(settings)) return json({ ok: false, error: 'Invalid schedule settings' }, 400);
  const { enabled, intervalHours, time, overwriteExisting } = settings;
  const saved = { enabled, intervalHours, time, overwriteExisting };
  await saveSettings(env, saved);
  return json({ ok: true, data: await scheduleStatus(env, saved) });
}
