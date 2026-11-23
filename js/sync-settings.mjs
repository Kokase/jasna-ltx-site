const ENDPOINT = '/api/sync-settings';

async function requestSettings(options) {
  const response = await fetch(ENDPOINT, options);
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401) throw new Error('請輸入有效嘅 GitHub Token。');
    if (response.status === 403) throw new Error('此 GitHub 帳戶需要有 Kokase/jasna-ltx-site 寫入權限。');
    throw new Error(result.error ?? `HTTP ${response.status}`);
  }
  return result.data;
}

function statusText(settings) {
  const format = value => new Intl.DateTimeFormat('zh-HK', {
    timeZone: 'Asia/Taipei', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value));
  return [settings.next_run ? `下次預計：${format(settings.next_run)}` : '自動採集已暫停',
    settings.last_dispatch_at ? `最近觸發：${format(settings.last_dispatch_at)}` : '尚未有新排程觸發紀錄'].join('；');
}

export async function openSyncSettings() {
  if (document.querySelector('#sync-settings-dialog')) return;
  const dialog = document.createElement('dialog');
  dialog.id = 'sync-settings-dialog';
  dialog.className = 'sync-settings-dialog';
  dialog.setAttribute('aria-labelledby', 'sync-settings-title');
  dialog.innerHTML = `
    <form action="${ENDPOINT}" method="post" aria-labelledby="sync-settings-title">
      <header><h2 id="sync-settings-title">自動採集設定</h2><button type="button" class="close" aria-label="關閉">×</button></header>
      <p class="hint">全站共用，關閉網頁後仍會執行。時間使用 UTC+8（香港／台北）。</p>
      <fieldset disabled><legend class="sr-only">採集排程</legend>
        <div class="check"><input id="sync-enabled" name="enabled" type="checkbox"><label for="sync-enabled">啟用自動採集</label></div>
        <label for="sync-time">每日基準時間</label>
        <input id="sync-time" name="time" type="time" step="300" required aria-describedby="sync-time-help">
        <small id="sync-time-help">以此時間起計，按下方頻率重複執行；時間以 5 分鐘為單位。</small>
        <label for="sync-interval">採集頻率</label>
        <select id="sync-interval" name="intervalHours">${[1,2,3,4,6,8,12,24].map(hours => `<option value="${hours}">每 ${hours} 小時</option>`).join('')}</select>
        <div class="check"><input id="sync-overwrite" name="overwriteExisting" type="checkbox"><label for="sync-overwrite">允許更新已有內容</label></div>
        <small>以新採集嘅非空資料更新同一番号；保留入庫時間、互動資料及來源缺漏嘅舊欄位。</small>
        <label for="sync-token">GitHub Token（儲存時驗證身份）</label>
        <input id="sync-token" name="token" type="password" autocomplete="off" spellcheck="false" required aria-describedby="sync-token-help">
        <small id="sync-token-help">使用有此 repo 寫入權限嘅帳戶 Token。只用作 GitHub 身份驗證，唔會儲存到瀏覽器或排程。</small>
        <button type="submit" class="save">儲存設定</button>
      </fieldset>
      <p class="hint timing">排程每 5 分鐘檢查一次，GitHub Actions 啟動時間可能稍有延遲。</p>
      <p class="status" role="status" aria-live="polite">正在讀取設定…</p>
    </form>`;
  const previousFocus = document.activeElement;
  document.body.append(dialog);
  const form = dialog.querySelector('form');
  const fieldset = form.querySelector('fieldset');
  const status = form.querySelector('.status');
  const fields = form.elements;
  const close = () => dialog.close();
  dialog.querySelector('.close').addEventListener('click', close);
  dialog.addEventListener('click', event => { if (event.target === dialog) close(); });
  dialog.addEventListener('close', () => {
    fields.token.value = '';
    dialog.remove();
    previousFocus?.focus();
  }, { once: true });
  dialog.showModal();
  try {
    const settings = await requestSettings();
    fields.enabled.checked = settings.enabled;
    fields.time.value = settings.time;
    fields.intervalHours.value = settings.intervalHours;
    fields.overwriteExisting.checked = settings.overwriteExisting;
    status.textContent = statusText(settings);
    fieldset.disabled = false;
    fields.enabled.focus();
  } catch (error) {
    status.textContent = `讀取失敗：${error.message} 請關閉後重試。`;
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const submit = form.querySelector('.save');
    const token = fields.token.value.trim();
    submit.disabled = true;
    status.textContent = '正在儲存…';
    try {
      const settings = await requestSettings({
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ enabled: fields.enabled.checked, time: fields.time.value,
          intervalHours: Number(fields.intervalHours.value), overwriteExisting: fields.overwriteExisting.checked }),
      });
      fields.token.value = '';
      status.textContent = `已儲存，最遲約 1 分鐘後全站生效。${statusText(settings)}`;
    } catch (error) {
      status.textContent = `儲存失敗：${error.message}`;
    } finally {
      submit.disabled = false;
    }
  });
}
