import { test } from 'node:test';
import assert from 'node:assert/strict';

const api = await import('./content.mjs').catch(() => ({}));
const search = await import('../.vitepress/tokenize.mjs').catch(() => ({}));
const figures = await import('./figures.mjs').catch(() => ({}));

test('rejects an incomplete manuscript rather than publishing missing chapters', () => {
  assert.equal(typeof api.catalog, 'function', 'catalog not implemented');
  assert.throws(() => api.catalog(['第01章-示例.md']), /31|完整/);
});

test('preserves sources and rewrites a relative image for the Pages subpath', () => {
  assert.equal(typeof api.convert, 'function', 'convert not implemented');
  const source = '# 示例\n\n正文[^1]。\n\n![图](../图表/第01章-机构总览.png)\n\n[^1]: 来源[原文](https://example.com/source)。\n';
  const result = api.convert(source, '第01章-示例.md', []);
  assert.match(result, /正文\[\^1\]/);
  assert.match(result, /\[\^1\]: 来源\[原文\]\(https:\/\/example.com\/source\)/);
  assert.match(result, /\/figures\/第01章-机构总览.png/);
});

test('replaces each Mermaid block with its numbered reading-edition figure', () => {
  assert.equal(typeof api.convert, 'function', 'convert not implemented');
  const result = api.convert('# 图\n```mermaid\nflowchart TD\nA --> B\n```\n', '第02章-示例.md', []);
  assert.doesNotMatch(result, /```mermaid/);
  assert.match(result, /导出版\/第02章-关系图-1.svg/);
});

test('Chinese phrases inside a sentence share search tokens with the query', () => {
  assert.equal(typeof search.tokenize, 'function', 'tokenize not implemented');
  for (const query of ['干部任免', '国务院', '证据边界']) {
    const document = new Set(search.tokenize('我们怎样理解干部任免与国务院的证据边界？'));
    assert.ok(search.tokenize(query).every(token => document.has(token)), query);
  }
});

test('rewrites manuscript chapter links and fails on unresolved local destinations', () => {
  assert.equal(typeof api.convert, 'function', 'convert not implemented');
  const entries = [{ file: '第02章-示例.md', route: 'chapter-02' }];
  assert.match(api.convert('[下一章](第02章-示例.md#小节)', '第01章-示例.md', entries), /chapter-02#小节/);
  assert.throws(() => api.convert('[坏链接](不存在.md)', '第01章-示例.md', entries), /链接/);
});

test('a changed diagram is rendered from current labels rather than an old image', async () => {
  assert.equal(typeof figures.renderDiagram, 'function', 'diagram renderer not implemented');
  const result = await figures.renderDiagram('flowchart TD\nA[新机构] -->|提名| B[新职位]');
  assert.match(result, /新机构/);
  assert.match(result, /新职位/);
  assert.match(result, /提名/);
  await assert.rejects(() => figures.renderDiagram('flowchart TD\nunsupported syntax'), /图表/);
});
