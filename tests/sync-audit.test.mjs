import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createSyncAudit } from '../scripts/sync-audit.mjs';

test('reports missing fields without exposing image or link values', () => {
  const audit = createSyncAudit({ updated_at: 'fixture', items: [
    { code: 'EMPTY' },
    { code: 'IMAGE', cover: 'cover.jpg', links: [] },
    { code: 'LEGACY', cover: '', link: 'existing-file' },
    { code: 'COMPLETE', cover: 'cover.jpg', links: ['existing-file'] },
    { code: 'BLANK', cover: ' ', links: ['', ' '] },
  ] });
  assert.equal(audit.total, 5);
  assert.equal(audit.missing_cover, 3);
  assert.equal(audit.missing_links, 3);
  assert.equal(audit.missing_both, 2);
  assert.equal(audit.complete, 1);
  assert.deepEqual(audit.records, [
    { code: 'EMPTY', missing: ['cover', 'links'] },
    { code: 'IMAGE', missing: ['links'] },
    { code: 'LEGACY', missing: ['cover'] },
    { code: 'BLANK', missing: ['cover', 'links'] },
  ]);
  assert.equal(JSON.stringify(audit).includes('cover.jpg'), false);
  assert.equal(JSON.stringify(audit).includes('existing-file'), false);
});
