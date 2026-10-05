import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { catalog, convert } from './content.mjs';
import { renderDiagram } from './figures.mjs';

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const root = path.resolve(site, '..');
const manuscript = path.join(root, '书稿');
const entries = catalog(fs.readdirSync(manuscript));
for (const entry of entries) {
  entry.source = fs.readFileSync(path.join(manuscript, entry.file), 'utf8');
  entry.title = entry.source.match(/^#\s+(.+)$/m)?.[1] || entry.title;
}
fs.mkdirSync(path.join(site, '.vitepress'), { recursive: true });
fs.mkdirSync(path.join(site, 'public'), { recursive: true });
fs.cpSync(path.join(root, '图表'), path.join(site, 'public/figures'), { recursive: true });
for (let i = 0; i < entries.length; i++) {
  const entry = entries[i];
  const original = entry.source;
  let figure = 0;
  for (const block of original.matchAll(/```mermaid\s*\n([\s\S]*?)```/g)) {
    const output = path.join(site, `public/figures/导出版/${entry.file.slice(0, 4)}-关系图-${++figure}.svg`);
    fs.mkdirSync(path.dirname(output), { recursive: true });
    fs.writeFileSync(output, await renderDiagram(block[1]));
  }
  const content = convert(original, entry.file, entries);
  for (const image of content.matchAll(/!\[[^\]]*\]\(([^)]+)\)/g)) {
    const local = path.join(site, 'public', image[1].replace(/^\//, ''));
    if (!fs.existsSync(local)) throw Error(`图表缺失: ${image[1]}`);
  }
  const neighbor = index => index >= 0 && index < entries.length ? { text: entries[index].title, link: '/' + entries[index].route } : false;
  const frontmatter = { title: entry.title, prev: neighbor(i - 1), next: neighbor(i + 1) };
  fs.writeFileSync(path.join(site, `${entry.route}.md`), `---\n${Object.entries(frontmatter).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join('\n')}\n---\n\n${content}`);
}
// Titles from manuscript headings are also used by sidebar and contents.
fs.writeFileSync(path.join(site, '.vitepress/navigation.json'), JSON.stringify(entries.map(({ source, ...entry }) => entry), null, 2));
fs.writeFileSync(path.join(site, 'contents.md'), `# 完整目录\n\n从导读开始，也可以按问题选择章节。全书现实资料截止：**2026年9月29日**。\n\n${entries.map(e => `- [${e.title}](./${e.route})`).join('\n')}\n`);
fs.writeFileSync(path.join(site, 'index.md'), `---
layout: home
hero:
  name: 中国政治是怎么运转的
  text: 给普通读者的运行说明书
  tagline: 从制度、人物与现实事件，理解机构、干部、政策与监督机制。
  actions:
    - theme: brand
      text: 开始阅读
      link: /guide
    - theme: alt
      text: 完整目录
      link: /contents
    - theme: alt
      text: 下载电子书
      link: /downloads
features:
  - title: 先画出制度地图
    details: 分清党与国家、人大与政协、政府与司法机关的角色与关系。
    link: /chapter-01
  - title: 看懂现实中的过程
    details: 从任免、换届、政策和监督事件出发，辨认程序与证据。
    link: /chapter-10
  - title: 学会自己继续阅读
    details: 区分事实、解释与未知，使用公开来源核查新闻与传闻。
    link: /chapter-24
---

## 读前说明

全书包含导读、24章正文和6个附录。现实资料截止：**2026年9月29日**。人物职务与制度变化，请结合章末注释的核查时点阅读。

这本书不写无法确认的政坛内幕。每章保留资料来源，明确区分**事实、解释与未知**。

免费阅读不代表授予开放版权许可。书稿与引用材料的版权边界见[仓库说明](https://github.com/S150101132/how-chinese-politics-works#勘误与参与)。

发现错误或有资料补充，欢迎[提交反馈](https://github.com/S150101132/how-chinese-politics-works/issues/new/choose)。
`);
fs.writeFileSync(path.join(site, 'downloads.md'), `# 下载电子书\n\n三种格式与仓库交付版一致，现实资料截止：**2026年9月29日**。\n\n- [下载 PDF](https://github.com/S150101132/how-chinese-politics-works/raw/refs/heads/main/交付/中国政治是怎么运转的.pdf)\n- [下载 EPUB](https://github.com/S150101132/how-chinese-politics-works/raw/refs/heads/main/交付/中国政治是怎么运转的.epub)\n- [下载 Word](https://github.com/S150101132/how-chinese-politics-works/raw/refs/heads/main/交付/中国政治是怎么运转的.docx)\n- [SHA256 校验文件](https://github.com/S150101132/how-chinese-politics-works/blob/main/交付/SHA256SUMS)\n\n正式版本发布后，可在[版本发布页](https://github.com/S150101132/how-chinese-politics-works/releases)查看版本说明及附件。\n\n免费阅读不代表授予开放版权许可，请保留书稿及引用来源的版权声明。\n`);
console.log(`Generated ${entries.length} manuscript pages, homepage, contents and downloads.`);
