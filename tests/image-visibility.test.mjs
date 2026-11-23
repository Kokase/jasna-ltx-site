import assert from 'node:assert/strict';
import { test } from 'node:test';
import { observeImageVisibility } from '../js/image-visibility.mjs';

test('loads nearby images, unloads distant images and releases removed targets', (t) => {
  let deliver;
  const observed = new Set();
  let instances = 0;
  t.after(() => { delete globalThis.IntersectionObserver; });
  globalThis.IntersectionObserver = class {
    constructor(callback, options) {
      instances++;
      deliver = callback;
      assert.equal(options.rootMargin, '300px');
    }
    observe(element) { observed.add(element); }
    unobserve(element) { observed.delete(element); }
  };
  const poster = {};
  const avatar = {};
  const states = [];
  const stopPoster = observeImageVisibility(poster, visible => states.push(visible));
  const stopAvatar = observeImageVisibility(avatar, () => {});
  assert.equal(instances, 1);
  assert.equal(observed.size, 2);
  assert.deepEqual(states, []);
  deliver([{ target: poster, isIntersecting: true }]);
  deliver([{ target: poster, isIntersecting: false }]);
  assert.deepEqual(states, [true, false]);
  stopPoster();
  deliver([{ target: poster, isIntersecting: true }]);
  assert.deepEqual(states, [true, false]);
  stopAvatar();
  assert.equal(observed.size, 0);
});
