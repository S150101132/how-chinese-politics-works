export const base = '/how-chinese-politics-works/';

export function catalog(files) {
  const ordered = [
    ...files.filter(f => /^导读.*\.md$/.test(f)),
    ...files.filter(f => /^第\d\d章.*\.md$/.test(f)).sort(),
    ...files.filter(f => /^附录[A-F].*\.md$/.test(f)).sort()
  ];
  const expected = ['guide', ...Array.from({ length: 24 }, (_, i) => `chapter-${String(i + 1).padStart(2, '0')}`), ...'abcdef'.split('').map(c => `appendix-${c}`)];
  const entries = ordered.map(file => ({
    file,
    route: file.startsWith('导读') ? 'guide' : file.startsWith('第') ? `chapter-${file.slice(1, 3)}` : `appendix-${file[2].toLowerCase()}`,
    title: file.replace(/\.md$/, '').replace('-', ' · ')
  }));
  if (entries.length !== 31 || entries.some((entry, i) => entry.route !== expected[i])) throw Error('需要完整31篇书稿：导读、24章、附录A至F');
  return entries;
}

export function convert(source, file, entries) {
  let figure = 0;
  return source.replace(/```mermaid\s*\n[\s\S]*?```/g, () =>
    `![本章制度关系图](/figures/导出版/${file.slice(0, 4)}-关系图-${++figure}.svg)`
  ).replace(/(!?\[[^\]\n]*\])\(([^)\s]+)\)/g, (match, label, target) => {
    if (/^(https?:|mailto:|#)/.test(target)) return match;
    if (label.startsWith('!') && target.startsWith('/figures/')) return match;
    if (label.startsWith('!') && target.startsWith('../图表/')) return `${label}(/figures/${target.slice(6)})`;
    const [destination, hash] = decodeURI(target).split('#');
    const entry = entries.find(e => e.file === destination.replace(/^(\.\.\/书稿\/|\.\/)/, ''));
    if (!entry) throw Error(`未解析的本地链接 ${file}: ${target}`);
    return `${label}(./${entry.route}${hash ? '#' + hash : ''})`;
  });
}
