import assert from 'node:assert/strict';
import { test } from 'node:test';
import { hasLinks, matchesQuickFilters } from '../js/catalogue-filters.mjs';

test('link presence accepts both data formats and excludes blank values', () => {
  assert.equal(hasLinks({ link: 'existing-file' }), true);
  assert.equal(hasLinks({ links: ['existing-file'], pending_links: ['existing-file'] }), true);
  assert.equal(hasLinks({ link: ' ', links: ['', ' '] }), false);
  assert.equal(hasLinks({}), false);
});

test('link and subtitle filters combine with AND before pagination', () => {
  const items = [
    { code: 'A', link: 'file', subtitle: 'subtitle.srt' },
    { code: 'B', link: 'file', subtitle: '' },
    { code: 'C', link: '', subtitle: 'subtitle.srt' },
    { code: 'D', link: '', subtitle: '' },
  ];
  const select = options => items.filter(item => matchesQuickFilters(item, options)).map(item => item.code);
  assert.deepEqual(select({}), ['A', 'B', 'C', 'D']);
  assert.deepEqual(select({ linked: true }), ['A', 'B']);
  assert.deepEqual(select({ sub: true }), ['A', 'C']);
  assert.deepEqual(select({ linked: true, sub: true }), ['A']);
  const lateMatch = [...Array.from({ length: 24 }, () => ({ link: '', subtitle: '' })), items[0]];
  assert.equal(lateMatch.filter(item => matchesQuickFilters(item, { linked: true })).slice(0, 24)[0].code, 'A');
});
