// POST /api/sync  -> 触发 GitHub Actions 更新工作流
const REPO = 'Kokase/jasna-ltx-site';
const WF = 'sync.yml';

export async function onRequestPost({ request, env }) {
  const mode = new URL(request.url).searchParams.get('mode') ?? 'all';
  if (!['all', 'import'].includes(mode)) {
    return json({ ok: false, error: 'Invalid sync mode. Use all or import.' }, 400);
  }
  const token = env.GITHUB_TOKEN;
  if (!token) {
    return json({ ok: false, error: '服务器未配置 GITHUB_TOKEN' }, 500);
  }
  try {
    const r = await fetch(
      `https://api.github.com/repos/${REPO}/actions/workflows/${WF}/dispatches`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/vnd.github+json',
          'User-Agent': 'jasna-ltx-site',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ref: 'main', ...(mode === 'import' ? { inputs: { mode } } : {}) }),
      }
    );
    if (r.status === 204 || r.status === 200) return json({ ok: true, msg: '更新已触发' });
    const txt = await r.text();
    return json({ ok: false, error: `GitHub ${r.status}: ${txt.slice(0, 120)}` }, 502);
  } catch (e) {
    return json({ ok: false, error: String(e).slice(0, 120) }, 500);
  }
}

export async function onRequestGet({ request, env }) {
  if (new URL(request.url).searchParams.get('audit') === '1') {
    const response = await env.ASSETS.fetch(new URL('/data/sync-audit.json', request.url));
    if (!response.ok) return json({ ok: false, error: 'Sync audit is unavailable' }, 502);
    return json({ ok: true, data: await response.json() });
  }
  return json({ ok: true, hint: 'POST 触发更新' });
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' },
  });
}
