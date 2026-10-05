import { instance } from '@viz-js/viz';

let runtime;
const wrap = (text, width = 12) => text.replace(/<br\s*\/?>/g, '\n').split('\n').map(line => Array.from(line).reduce((s, c, i) => s + c + (i % width === width - 1 ? '\n' : ''), '').trim()).join('\n');

// The manuscript's deliberately small flowchart grammar is also used by
// 制作/prepare-book.mjs. Fail on unsupported syntax rather than omit a relation.
export async function renderDiagram(source) {
  const lines = source.trim().split('\n');
  if (!/^flowchart (?:LR|TD|TB)$/.test(lines[0].trim())) throw Error('图表方向不支持');
  const nodes = new Map(), edges = [];
  for (const line of lines.slice(1)) {
    if (!line.trim()) continue;
    const m = line.trim().match(/^(\w+)(?:\[([^\]]+)\])?\s*(-->|-\.->)(?:\|([^|]+)\|)?\s*(\w+)(?:\[([^\]]+)\])?\s*$/);
    if (!m) throw Error('图表语法不支持: ' + line);
    if (m[2]) nodes.set(m[1], wrap(m[2]));
    if (m[6]) nodes.set(m[5], wrap(m[6]));
    edges.push([m[1], m[5], m[4] || '', m[3] === '-.->']);
  }
  const quote = JSON.stringify;
  const dot = 'digraph G { graph [rankdir=TB, bgcolor="white", pad="0.25", nodesep="0.35", ranksep="0.25"]; node [shape=box, width=2.75, style="rounded,filled", fillcolor="#f3f4f1", color="#738078", fontname="Noto Sans CJK SC", fontsize=14, margin="0.12,0.10"]; edge [color="#62716c", fontname="Noto Sans CJK SC", fontsize=11]; ' + [...nodes].map(([id, label]) => `${id} [label=${quote(label)}];`).join(' ') + ' ' + edges.map(([a, b, label, dashed]) => `${a} -> ${b} [label=${quote(wrap(label, 8))}${dashed ? ', style=dashed' : ''}];`).join(' ') + ' }';
  runtime ||= instance();
  return (await runtime).renderString(dot, { format: 'svg' }).replace(/<g id="edge[\s\S]*?<\/g>/g, group => group.replace(/<text /g, '<text style="paint-order:stroke;stroke:white;stroke-width:3;stroke-linejoin:round" '));
}
