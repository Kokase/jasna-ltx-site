import { cp, mkdir, rm } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const output = new URL('dist/client/', root);
const assets = [
  'index.html', 'robots.txt', '_headers', 'xd_plus.js', 'xd_plus.css',
  'css', 'js', 'data', 'dl', 'xdown',
];

await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await Promise.all(assets.map((asset) => cp(
  new URL(asset, root), new URL(asset, output), { recursive: true },
)));
