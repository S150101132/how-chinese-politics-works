import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { base } from './content.mjs';

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dist = path.join(site, '.vitepress/dist');
const entries = JSON.parse(fs.readFileSync(path.join(site, '.vitepress/navigation.json'), 'utf8'));
const routes = ['index', 'contents', 'downloads', ...entries.map(e => e.route)];
let notes = 0, images = 0, links = 0;
for (const route of routes) {
  const html = fs.readFileSync(path.join(dist, route + '.html'), 'utf8');
  const ids = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]));
  const entry = entries.find(e => e.route === route);
  if (entry) {
    const source = fs.readFileSync(path.join(site, '..', '书稿', entry.file), 'utf8');
    const expected = [...source.matchAll(/^\[\^([^\]]+)\]:/gm)].length;
    const actual = [...html.matchAll(/class="footnote-item"/g)].length;
    assert.equal(actual, expected, route + ' lost source notes');
    notes += actual;
  }
  assert.ok(!html.includes('language-mermaid'), route + ' contains unrendered diagram');
  assert.ok(!/>[^<]*\*\*[^<]*</.test(html), route + ' contains unrendered Chinese emphasis');
  for (const match of html.matchAll(/\b(href|src)="([^"]+)"/g)) {
    const target = decodeURI(match[2]);
    if (target.startsWith('#fn')) {
      assert.ok(ids.has(target.slice(1)), route + ' broken footnote ' + target);
    }
    if (!target.startsWith(base)) continue;
    const relative = target.slice(base.length).split('#')[0].split('?')[0];
    const destination = relative || 'index.html';
    assert.ok(fs.existsSync(path.join(dist, destination)) || fs.existsSync(path.join(dist, destination + '.html')), route + ' broken local target ' + target);
    links++;
    if (match[1] === 'src' && target.includes('/figures/')) images++;
  }
}
assert.equal(images, 7, 'Expected one institution map and six relationship diagrams');
assert.ok(fs.existsSync(path.join(dist, 'sitemap.xml')), 'Missing sitemap');
console.log(JSON.stringify({ pages: routes.length, notes, images, localLinksChecked: links }));
