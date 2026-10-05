// Independent browser smoke checks for the expanded EPUB. Does not edit sources.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const modules = path.resolve(path.dirname(process.execPath), '../node_modules');
const { chromium } = await import(pathToFileURL(path.join(modules, 'playwright/index.mjs')).href);
const { default: sharp } = await import(pathToFileURL(path.join(modules, 'sharp/dist/index.mjs')).href);

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dir = path.join(root, 'tmp/book/epub/EPUB');
const output = path.join(root, 'tmp/book/epub-reading');
fs.mkdirSync(output, { recursive: true });
const book = JSON.parse(fs.readFileSync(path.join(root, 'tmp/book/book.json'), 'utf8'));
const browser = await chromium.launch({ executablePath: '/usr/bin/chromium', headless: true, args: ['--no-sandbox'] });
const results = [];
try {
  for (const width of [360, 768, 1280]) {
    const page = await browser.newPage({ viewport: { width, height: 900 }, deviceScaleFactor: 1 });
    for (const section of book.map((_, i) => i)) {
      await page.goto(pathToFileURL(path.join(dir, `section-${section}.xhtml`)).href);
      await page.evaluate(() => document.fonts.ready);
      const layout = await page.evaluate(() => ({
        title: document.title,
        viewport: window.innerWidth,
        width: document.documentElement.scrollWidth,
        tables: document.querySelectorAll('table').length,
        images: [...document.images].map(i => ({ loaded: i.complete && i.naturalWidth > 0, width: i.getBoundingClientRect().width, naturalWidth: i.naturalWidth })),
        badBoxes: [...document.querySelectorAll('table,img,pre')].filter(e => e.getBoundingClientRect().right > window.innerWidth + 1).length,
      }));
      if (layout.width > width + 1 || layout.badBoxes || layout.images.some(i => !i.loaded)) throw Error(`Layout failure ${width}/${section}: ${JSON.stringify(layout)}`);
      if (width === 360) {
        await page.screenshot({ path: path.join(output, `opening-${section}.png`) });
        const imgs = page.locator('img');
        for (let i = 0; i < await imgs.count(); i++) {
          await imgs.nth(i).scrollIntoViewIfNeeded();
          await page.screenshot({ path: path.join(output, `figure-${section}-${i}.png`) });
        }
      }
      const ref = page.locator('a[role="doc-noteref"]').first();
      let jump = false;
      if (await ref.count()) {
        const id = await ref.getAttribute('id');
        const target = await ref.getAttribute('href');
        await ref.click();
        if ((await page.evaluate(() => location.hash)) !== target) throw Error('Note jump failed');
        await page.locator(`${target} a[href="#${id}"]`).click();
        if ((await page.evaluate(() => location.hash)) !== `#${id}`) throw Error('Note return failed');
        jump = true;
      }
      const imageLink = page.locator('a.image-link').first();
      let imageOpen = false;
      if (await imageLink.count()) {
        const source = new URL(await imageLink.getAttribute('href'), page.url()).href;
        await imageLink.click();
        if (page.url() !== source || !(await page.locator('img').evaluate(i => i.complete && i.naturalWidth > 0))) throw Error('Original image open failed');
        await page.goBack();
        imageOpen = true;
      }
      results.push({ section, width, ...layout, noteJumpAndReturn: jump, originalImageOpened: imageOpen });
      if ([1, 2, 12, 13, 19, 25].includes(section)) {
        const target = page.locator(section === 1 || section === 2 ? 'img' : section === 13 ? 'pre' : 'table').first();
        if (await target.count()) await target.evaluate(e => e.scrollIntoView({ block: 'start' }));
        await page.screenshot({ path: path.join(output, `${section}-${width}.png`) });
      }
    }
    await page.close();
  }
  // Contact sheets contain the exact 360px screenshots, with no resampling.
  for (let start = 0; start < book.length; start += 4) {
    const composite = [];
    for (let i = start; i < Math.min(start + 4, book.length); i++) {
      composite.push({ input: path.join(output, `opening-${i}.png`), left: ((i-start)%2)*360, top: Math.floor((i-start)/2)*900 });
    }
    await sharp({ create: { width: 720, height: 1800, channels: 3, background: '#dddddd' } }).composite(composite).png().toFile(path.join(output, `contact-${start}.png`));
  }
  fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({ testedAt: new Date().toISOString(), engine: 'Chromium', results }, null, 2));
  console.log(JSON.stringify({ pages: results.length, sections: book.length, widths: [360, 768, 1280], overflow: 0, screenshots: output }));
} finally {
  await browser.close();
}
