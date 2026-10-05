import { defineConfig } from 'vitepress';
import footnote from 'markdown-it-footnote';
import fs from 'node:fs';
import { tokenize } from './tokenize.mjs';
import { cjkStrong } from './cjk-strong.mjs';

const entries = JSON.parse(fs.readFileSync(new URL('./navigation.json', import.meta.url), 'utf8'));
const items = entries.map(e => ({ text: e.title, link: '/' + e.route }));
const siteUrl = 'https://s150101132.github.io/how-chinese-politics-works/';

export default defineConfig({
  lang: 'zh-CN',
  title: '中国政治是怎么运转的',
  description: '一本给普通读者看的中国政治运行说明书：从制度、人物与现实事件理解机构、干部、政策与监督机制。',
  base: '/how-chinese-politics-works/',
  srcExclude: ['README.md', 'scripts/**'],
  cleanUrls: true,
  sitemap: { hostname: siteUrl },
  head: [
    ['meta', { name: 'theme-color', content: '#f7f5ef' }],
    ['meta', { property: 'og:type', content: 'book' }],
    ['meta', { property: 'og:locale', content: 'zh_CN' }],
    ['meta', { property: 'og:site_name', content: '中国政治是怎么运转的' }],
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
    ['meta', { property: 'og:image', content: siteUrl + 'social-preview.png' }],
    ['meta', { name: 'twitter:image', content: siteUrl + 'social-preview.png' }]
  ],
  transformHead({ pageData }) {
    const url = siteUrl + pageData.relativePath.replace(/index\.md$/, '').replace(/\.md$/, '');
    return [
      ['link', { rel: 'canonical', href: url }],
      ['meta', { property: 'og:url', content: url }],
      ['meta', { property: 'og:title', content: pageData.title || '中国政治是怎么运转的' }],
      ['meta', { property: 'og:description', content: '从制度、人物与现实事件读懂当代中国。全书现实资料截止2026年9月29日。' }]
    ];
  },
  markdown: { config(md) { md.use(footnote); md.use(cjkStrong); } },
  themeConfig: {
    siteTitle: '中国政治是怎么运转的',
    nav: [
      { text: '首页', link: '/' },
      { text: '完整目录', link: '/contents' },
      { text: '下载', link: '/downloads' },
      { text: '反馈', link: 'https://github.com/S150101132/how-chinese-politics-works/issues/new/choose' }
    ],
    sidebar: [
      { text: '阅读入口', items: [{ text: '完整目录', link: '/contents' }, items[0]] },
      { text: '制度地图 · 第1—8章', collapsed: false, items: items.slice(1, 9) },
      { text: '干部、政策与监督 · 第9—17章', collapsed: false, items: items.slice(9, 18) },
      { text: '历史与现实阅读 · 第18—24章', collapsed: false, items: items.slice(18, 25) },
      { text: '附录', collapsed: true, items: items.slice(25) }
    ],
    outline: { level: [2, 3], label: '本页目录' },
    docFooter: { prev: '上一篇', next: '下一篇' },
    darkModeSwitchLabel: '切换阅读主题',
    sidebarMenuLabel: '全书目录',
    returnToTopLabel: '返回顶部',
    socialLinks: [{ icon: 'github', link: 'https://github.com/S150101132/how-chinese-politics-works' }],
    search: {
      provider: 'local',
      options: {
        miniSearch: {
          options: { tokenize, processTerm: term => term.toLowerCase() },
          searchOptions: { combineWith: 'AND', fuzzy: false, prefix: false }
        },
        translations: {
          button: { buttonText: '搜索全书', buttonAriaLabel: '搜索全书' },
          modal: { displayDetails: '显示摘要', resetButtonTitle: '清空搜索', backButtonTitle: '返回', noResultsText: '没有找到相关内容', footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' } }
        }
      }
    },
    footer: { message: '现实资料截止：2026年9月29日 · 免费阅读不代表授予开放版权许可' }
  }
});
