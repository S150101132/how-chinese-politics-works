import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const bundled='/home/wangbiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const moduleRoot=process.env.BOOK_NODE_MODULES || (fs.existsSync(path.join(process.cwd(),'node_modules/marked')) ? path.join(process.cwd(),'node_modules') : bundled);
const require=createRequire(path.join(path.dirname(moduleRoot),'_book_runtime.cjs'));
const { marked }=await import(pathToFileURL(require.resolve('marked')).href);
const vizModule=await import(pathToFileURL(require.resolve('@viz-js/viz')).href);
const instance=vizModule.instance || vizModule.default.instance;
const sharp=(await import(pathToFileURL(require.resolve('sharp')).href)).default;

const root=process.cwd(), tmp=path.join(root,'tmp/book');
fs.mkdirSync(tmp,{recursive:true});
fs.mkdirSync(path.join(root,'图表/导出版'),{recursive:true});
const files=fs.readdirSync(path.join(root,'书稿'));
const order=[...files.filter(x=>x.startsWith('导读')), ...files.filter(x=>/^第\d\d章/.test(x)).sort(), ...files.filter(x=>/^附录[A-F]/.test(x)).sort()];
if(order.length!==31) throw Error('Expected introduction, 24 chapters, six appendices');
const viz=await instance();
// The manuscript uses intentional emphasis beside Chinese punctuation.
// CommonMark's delimiter rules otherwise expose some literal ** markers.
marked.use({extensions:[{name:'cjkStrong',level:'inline',start:src=>src.indexOf('**'),tokenizer(src){const m=/^\*\*([\s\S]+?)\*\*/.exec(src);if(m)return {type:'strong',raw:m[0],text:m[1],tokens:marked.Lexer.lexInline(m[1])};}}]});
const wrap=(s,n=12)=>s.replace(/<br\s*\/?>/g,'\n').split('\n').map(l=>Array.from(l).reduce((a,c,i)=>a+c+(i%n===n-1?'\n':''),'').trim()).join('\n');
const quote=s=>JSON.stringify(s);
const book=[];
for(let i=0;i<order.length;i++){
  const file=order[i], source=fs.readFileSync(path.join(root,'书稿',file),'utf8');
  let title=source.split('\n')[0].replace(/^#\s*/,'');
  const chapter=file.match(/^第(\d\d)章/);
  if(chapter){const n=Number(chapter[1]),d='一二三四五六七八九';const cn=n<10?d[n-1]:n===10?'十':n<20?'十'+d[n-11]:n===20?'二十':'二十'+d[n-21];title=title.replace(/^第[\d一二三四五六七八九十]+章\s*/,'第'+cn+'章　');}
  const notes={};
  let body=source.replace(/^\[\^([^\]]+)\]:\s*(.*)$/gm,(_,k,v)=>{if(notes[k])throw Error('Duplicate note '+file+':'+k);notes[k]=v;return '';});
  body=body.replace(/^# .+\n/,'').replace(/^\*《中国政治是怎么运转的》.*\n/gm,'').replace(/^\*(?:修订与查证日期|成稿与修订复核|资料截止|查证日期|事实截止|成稿日期|修订日期|成稿与查证|资料核验|写作与|核验日期|正文版本).*\n/gm,'');
  // Draft metadata is editorial evidence, not part of the reading edition.
  const paragraphs=body.trimStart().split(/\n\s*\n/);
  while(paragraphs[0] && (/^\*(?!\*).*(?:2026|v0\.|截止|核查|查证|访问).*(?:\*|。)$/.test(paragraphs[0].trim()) || /^(?:>\s*)?(?:版本[：:]|v0\.)/.test(paragraphs[0].trim()))) paragraphs.shift();
  body=paragraphs.join('\n\n').trim();
  // Preserve introductory note guidance, replacing only its heading with one uniform heading below.
  body=body.replace(/^#{2,3}\s*(?:注释与资料|注释与来源|注释|资料与注释|注释与参考资料|章末注释|注释与继续阅读)\s*$/gm,'').trim();
  const refs=[...body.matchAll(/\[\^([^\]]+)\]/g)].map(m=>m[1]);
  for(const k of refs)if(!notes[k])throw Error('Missing note '+file+':'+k);
  for(const k of Object.keys(notes))if(!refs.includes(k))throw Error('Unused note '+file+':'+k);
  const tokens=marked.lexer(body,{...marked.defaults,gfm:true}); let figure=0;
  function normalizeImages(ts){for(const t of ts){if(t.type==='image'&&!/^https?:/.test(t.href)){const abs=path.isAbsolute(t.href)?t.href:path.resolve(root,'书稿',t.href);t.href=path.relative(root,abs);if(t.href.startsWith('..'))throw Error('Image outside project');}if(t.tokens)normalizeImages(t.tokens);if(t.items)normalizeImages(t.items);if(t.type==='table')for(const row of [t.header,...t.rows])for(const c of row)normalizeImages(c.tokens);}}
  normalizeImages(tokens);
  for(const t of tokens){
    if(t.type==='code'&&t.lang==='mermaid'){
      const nodes=new Map(),edges=[];
      for(const line of t.text.split('\n').slice(1)){
        const m=line.trim().match(/^(\w+)(?:\[([^\]]+)\])?\s*(-->|-\.->)(?:\|([^|]+)\|)?\s*(\w+)(?:\[([^\]]+)\])?\s*$/);
        if(!m)throw Error('Unparsed diagram line '+file+':'+line);
        if(m[2])nodes.set(m[1],wrap(m[2])); if(m[6])nodes.set(m[5],wrap(m[6]));
        edges.push([m[1],m[5],m[4]||'',m[3]==='-.->']);
      }
      // WASM Graphviz's font metrics do not measure installed CJK fonts.
      // Explicit widths plus twelve-character wrapping keep CJK glyphs inside boxes.
      const dot='digraph G { graph [rankdir=TB, bgcolor="white", pad="0.25", nodesep="0.35", ranksep="0.25"]; node [shape=box, width=2.75, style="rounded,filled", fillcolor="#f3f4f1", color="#738078", fontname="Noto Sans CJK SC", fontsize=14, margin="0.12,0.10"]; edge [color="#62716c", fontname="Noto Sans CJK SC", fontsize=11]; '+[...nodes].map(([id,label])=>`${id} [label=${quote(label)}];`).join(' ')+' '+edges.map(([a,b,l,d])=>`${a} -> ${b} [label=${quote(wrap(l,8))}${d?', style=dashed':''}];`).join(' ')+' }';
      // A white glyph outline keeps relation lines from crossing label strokes.
      const svg=viz.renderString(dot,{format:'svg'}).replace(/<g id="edge[\s\S]*?<\/g>/g,g=>g.replace(/<text /g,'<text style="paint-order:stroke;stroke:white;stroke-width:3;stroke-linejoin:round" '));
      const name=`${file.slice(0,4)}-关系图-${++figure}`;
      const rel=`图表/导出版/${name}.png`;
      fs.writeFileSync(path.join(root,`图表/导出版/${name}.svg`),svg);
      await sharp(Buffer.from(svg),{density:170}).png().toFile(path.join(root,rel));
      t.type='figure';t.path=rel;t.alt='本章制度关系图，箭头文字与正文对应';
    }
  }
  book.push({id:`section-${i}`,file,title,body,tokens,notes,refs,notesTokens:Object.fromEntries(Object.entries(notes).map(([k,v])=>[k,marked.Lexer.lexInline(v,marked.defaults)]))});
}
await sharp(path.join(root,'图表/第01章-机构总览.svg'),{density:144}).png().toFile(path.join(root,'图表/第01章-机构总览.png'));
fs.writeFileSync(path.join(tmp,'book.json'),JSON.stringify(book));
console.log(JSON.stringify({sections:book.length,chapters:24,notes:book.reduce((n,c)=>n+Object.keys(c.notes).length,0),figures:book.flatMap(c=>c.tokens).filter(t=>t.type==='figure').length+1}));
