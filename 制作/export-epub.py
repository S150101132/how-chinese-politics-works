#!/usr/bin/env python3
"""Build and validate the reading EPUB from prepare-book.mjs's book.json.

Run with bundled Python, from any directory. No manuscript or image is modified.
The preparation step belongs to the caller; this script never refreshes shared data.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlsplit, unquote
import argparse
import copy
import hashlib
import html
import json
import re
import shutil
import zipfile
from lxml import etree as E

ROOT = Path(__file__).resolve().parent.parent
X = 'http://www.w3.org/1999/xhtml'
EP = 'http://www.idpf.org/2007/ops'
OPF = 'http://www.idpf.org/2007/opf'
NS = {'h': X, 'epub': EP, 'opf': OPF}
XML = '<?xml version="1.0" encoding="utf-8"?>\n'
CSS = '''
html { color: #242925; background: #fff; }
body { font-family: "Noto Serif CJK SC", "Source Han Serif SC", serif;
  line-height: 1.85; margin: 5% auto; padding: 0 5%; max-width: 42em;
  overflow-wrap: anywhere; text-align: start; }
h1,h2,h3,h4,h5,h6 { font-family: "Noto Sans CJK SC", sans-serif;
  line-height: 1.45; font-weight: 600; break-after: avoid; }
h1 { font-size: 1.8em; margin: 1.2em 0; }
h2 { font-size: 1.35em; margin-top: 2em; }
h3 { font-size: 1.15em; margin-top: 1.5em; }
p { margin: .8em 0; orphans: 2; widows: 2; }
a { color: #245944; text-decoration: underline; }
sup { font-size: .72em; line-height: 0; }
.noteref { white-space: nowrap; }
.table-wrap { max-width: 100%; margin: 1.3em 0; }
table { border-collapse: collapse; width: 100%; table-layout: fixed;
  font-size: .88em; line-height: 1.65; }
th,td { border: 1px solid #c7cdc9; padding: .5em; vertical-align: top;
  overflow-wrap: anywhere; word-break: normal; }
th { background: #f0f3f0; font-weight: 600; }
tr { break-inside: avoid; }
figure { margin: 1.5em 0; padding: 0; break-inside: avoid; }
img { display: block; max-width: 100%; height: auto; margin: auto; }
figcaption { font-size: .82em; color: #566158; margin-top: .5em; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; word-break: break-word;
  font: .85em/1.75 "Noto Sans Mono CJK SC", monospace;
  background: #f3f5f2; padding: .8em; border-left: 2px solid #8d9c91; }
blockquote { margin: 1em 0; padding-left: 1em; border-left: 2px solid #8d9c91; }
li { margin: .45em 0; }
.notes { margin-top: 3em; padding-top: 1em; border-top: 1px solid #aeb8b0;
  font-size: .88em; }
.notes ol { padding-left: 2em; }
.backlinks { font-family: sans-serif; font-size: .85em; }
hr { border: 0; border-top: 1px solid #c7cdc9; margin: 2em 0; }
@media (max-width: 480px) { body { padding: 0 4%; margin: 1em auto; }
 h1 { font-size: 1.55em; } th,td { padding: .35em; } }
'''

def esc(s):
    return html.escape(str(s), quote=True)

def clean(s):
    return html.unescape(s)

def normalized(s):
    return re.sub(r'\s+', '', s)

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def document(title, body):
    return XML + f'''<!DOCTYPE html>
<html xmlns="{X}" xmlns:epub="{EP}" lang="zh-CN" xml:lang="zh-CN">
<head><title>{esc(title)}</title><meta charset="utf-8"/>
<link rel="stylesheet" type="text/css" href="styles.css"/></head>
<body>{body}</body></html>'''

def expected_text(tokens):
    """Independent AST text oracle; not derived from generated markup."""
    out = []
    for t in tokens:
        k = t['type']
        if k in ('image', 'figure', 'space', 'hr', 'br'):
            continue
        if k == 'table':
            for cell in t['header'] + sum(t['rows'], []):
                out.append(expected_text(cell['tokens']))
        elif k == 'list':
            out.append(expected_text(t['items']))
        elif 'tokens' in t:
            out.append(expected_text(t['tokens']))
        elif k in ('text', 'escape', 'codespan', 'code'):
            text = clean(t['text'])
            if k not in ('code', 'codespan'):
                text = re.sub(r'\[\^[^\]]+\]', '', text)
            out.append(text)
        else:
            raise ValueError(f'Unknown text token: {k}')
    return ''.join(out)

def walk(tokens):
    for t in tokens:
        yield t
        for key in ('tokens', 'items'):
            if isinstance(t.get(key), list):
                yield from walk(t[key])
        if t['type'] == 'table':
            for cell in t['header'] + sum(t['rows'], []):
                yield from walk(cell['tokens'])

class Renderer:
    def __init__(self, chapter, package, images):
        self.c, self.package, self.images = chapter, package, images
        self.refs = Counter()
        self.headings = 0
        self.figures = 0
        self.tables = 0
        # Local numbering preserves the manuscript's note numbers.
        if not all(re.fullmatch(r'[1-9][0-9]*', k) for k in chapter['notes']):
            raise ValueError('This edition expects positive chapter-local note numbers')

    def text(self, value):
        parts = re.split(r'(\[\^[^\]]+\])', clean(value))
        out = []
        for part in parts:
            m = re.fullmatch(r'\[\^([^\]]+)\]', part)
            if not m:
                out.append(esc(part)); continue
            n = m[1]
            if n not in self.c['notes']:
                raise ValueError(f'Missing note {self.c["file"]}:{n}')
            self.refs[n] += 1
            rid = f'ref-{n}-{self.refs[n]}'
            out.append(f'<sup><a class="noteref" epub:type="noteref" role="doc-noteref" id="{rid}" href="#note-{n}">[{n}]</a></sup>')
        return ''.join(out)

    def image(self, source, alt):
        p = Path(unquote(source))
        if not p.is_absolute():
            p = ROOT / p
        p = p.resolve(strict=True)
        if p.suffix.lower() != '.png':
            raise ValueError(f'Expected prepared PNG: {p}')
        key = str(p)
        if key not in self.images:
            name = f'images/figure-{len(self.images)+1:02d}.png'
            shutil.copyfile(p, self.package / name)
            self.images[key] = {'href': name, 'sha256': digest(p)}
        self.figures += 1
        href = self.images[key]['href']
        return f'<a class="image-link" href="{href}" title="查看大图"><img src="{href}" alt="{esc(clean(alt))}"/></a>'

    def render(self, tokens):
        out = []
        for t in tokens:
            k = t['type']
            if k == 'space': continue
            if k == 'figure':
                img = self.image(t['path'], t['alt'])
                out.append(f'<figure>{img}<figcaption>{esc(t["alt"])}</figcaption></figure>')
            elif k == 'image': out.append(self.image(t['href'], t['text']))
            elif k == 'text': out.append(self.render(t['tokens']) if 'tokens' in t else self.text(t['text']))
            elif k == 'escape': out.append(self.text(t['text']))
            elif k == 'paragraph': out.append('<p>' + self.render(t['tokens']) + '</p>')
            elif k == 'heading':
                self.headings += 1
                level = max(2, min(6, t['depth']))
                out.append(f'<h{level} id="heading-{self.headings}">{self.render(t["tokens"])}</h{level}>')
            elif k in ('strong', 'em', 'del'):
                out.append(f'<{k}>' + self.render(t['tokens']) + f'</{k}>')
            elif k == 'codespan': out.append('<code>' + esc(clean(t['text'])) + '</code>')
            elif k == 'code':
                if t.get('lang') == 'mermaid':
                    raise ValueError('Unprepared Mermaid: run prepare-book.mjs first')
                out.append('<pre>' + esc(t['text']) + '</pre>')
            elif k == 'br': out.append('<br/>')
            elif k == 'hr': out.append('<hr/>')
            elif k == 'blockquote': out.append('<blockquote>' + self.render(t['tokens']) + '</blockquote>')
            elif k == 'link':
                href = t['href']
                if urlsplit(href).scheme not in ('http', 'https', 'mailto') and not href.startswith('#'):
                    raise ValueError(f'Unmapped local manuscript link: {href}')
                out.append(f'<a href="{esc(href)}">' + self.render(t['tokens']) + '</a>')
            elif k == 'list':
                tag = 'ol' if t['ordered'] else 'ul'
                start = f' start="{int(t.get("start") or 1)}"' if t['ordered'] else ''
                out.append(f'<{tag}{start}>' + self.render(t['items']) + f'</{tag}>')
            elif k == 'list_item': out.append('<li>' + self.render(t['tokens']) + '</li>')
            elif k == 'table':
                self.tables += 1
                def row(cells, tag):
                    return '<tr>' + ''.join(f'<{tag}'+(' scope="col"' if tag == 'th' else '')+'>'+self.render(cell['tokens'])+f'</{tag}>' for cell in cells) + '</tr>'
                out.append('<div class="table-wrap"><table><thead>'+row(t['header'], 'th')+'</thead><tbody>'+''.join(row(r, 'td') for r in t['rows'])+'</tbody></table></div>')
            else:
                raise ValueError(f'Unsupported token: {k} in {self.c["file"]}')
        return ''.join(out)

def visible_text(el, remove):
    tree = copy.deepcopy(el)
    for item in tree.xpath(remove, namespaces=NS):
        if item.tail:
            previous = item.getprevious()
            if previous is None:
                item.getparent().text = (item.getparent().text or '') + item.tail
            else:
                previous.tail = (previous.tail or '') + item.tail
        item.getparent().remove(item)
    return ''.join(tree.itertext())

def validate(folder, book, chapter_stats):
    parser = E.XMLParser(resolve_entities=False, no_network=True)
    docs = {}
    for p in folder.rglob('*'):
        if p.suffix in ('.xml', '.xhtml', '.opf'):
            docs[p.resolve()] = E.parse(str(p), parser)
    ids = {}
    links = 0
    for p, tree in docs.items():
        found = tree.xpath('//@id')
        if len(found) != len(set(found)): raise ValueError(f'Duplicate ID: {p}')
        ids[p] = set(found)
    for p, tree in docs.items():
        for href in tree.xpath('//@href | //@src | //@full-path'):
            u = urlsplit(href)
            if u.scheme in ('https', 'http', 'mailto'): continue
            if u.scheme or u.netloc or u.query: raise ValueError(f'Unexpected link {href}')
            target = (folder / unquote(u.path) if p.name == 'container.xml' else p.parent / unquote(u.path)).resolve() if u.path else p
            if not target.is_relative_to(folder.resolve()) or not target.is_file():
                raise ValueError(f'Broken local link: {p}: {href}')
            if u.fragment and unquote(u.fragment) not in ids.get(target, set()):
                raise ValueError(f'Broken fragment: {p}: {href}')
            links += 1
    package = docs[(folder/'EPUB/package.opf').resolve()]
    manifest = package.xpath('//opf:manifest/opf:item', namespaces=NS)
    mid = {e.get('id'): e for e in manifest}
    spine = package.xpath('//opf:spine/opf:itemref/@idref', namespaces=NS)
    if spine != [c['id'] for c in book]: raise ValueError('Spine order mismatch')
    if any(i not in mid for i in spine): raise ValueError('Unmanifested spine item')
    if len(package.xpath('//opf:item[@properties="nav"]', namespaces=NS)) != 1:
        raise ValueError('Missing EPUB3 navigation')
    nav = docs[(folder/'EPUB/nav.xhtml').resolve()]
    nav_links = nav.xpath('//h:nav[@epub:type="toc"]/h:ol/h:li/h:a', namespaces=NS)
    if [a.text for a in nav_links] != [c['title'] for c in book]: raise ValueError('TOC titles mismatch')
    declared = {e.get('href') for e in manifest}
    actual = {str(p.relative_to(folder/'EPUB')) for p in (folder/'EPUB').rglob('*') if p.is_file() and p.name != 'package.opf'}
    if declared != actual: raise ValueError('Manifest resource mismatch')
    for c, stats in zip(book, chapter_stats):
        tree = docs[(folder/'EPUB'/f'{c["id"]}.xhtml').resolve()]
        source_tokens = list(walk(c['tokens'])) + [t for ts in c['notesTokens'].values() for t in walk(ts)]
        expected_links = Counter(t['href'] for t in source_tokens if t['type'] == 'link')
        actual_links = Counter(tree.xpath('//h:a[not(@epub:type="noteref") and not(@class="image-link") and not(ancestor::h:p[@class="backlinks"])]/@href', namespaces=NS))
        if expected_links != actual_links: raise ValueError(f'Source links changed: {c["file"]}')
        if tree.xpath('string(//h:h1)', namespaces=NS) != c['title']: raise ValueError('Chapter title mismatch')
        main = tree.xpath('//*[@id="chapter-body"]')[0]
        actual_text = visible_text(main, './/h:sup[h:a[@epub:type="noteref"]] | .//h:figcaption')
        if normalized(actual_text) != normalized(expected_text(c['tokens'])):
            raise ValueError(f'Body text mismatch: {c["file"]}')
        prose = visible_text(main, './/h:pre | .//h:code')
        if re.search(r'\*\*[^*]+\*\*', prose):
            raise ValueError(f'Unparsed emphasis in prepared tokens: {c["file"]}; refresh preparation')
        for n, ts in c['notesTokens'].items():
            note = tree.xpath(f'//*[@id="note-{n}"]/h:div', namespaces=NS)[0]
            if normalized(visible_text(note, './/h:sup[h:a[@epub:type="noteref"]]')) != normalized(expected_text(ts)):
                raise ValueError(f'Note text mismatch: {c["file"]}:{n}')
        refs = tree.xpath('//h:a[@epub:type="noteref"]', namespaces=NS)
        note_refs = sum(len(re.findall(r'\[\^[^\]]+\]', t)) for t in c['notes'].values())
        if len(refs) != len(c['refs']) + note_refs: raise ValueError('Footnote reference count mismatch')
        for a in refs:
            n = a.get('href')[1:]
            if not tree.xpath(f'//*[@id="{n}"]//h:a[@href="#{a.get("id")}"]', namespaces=NS):
                raise ValueError('Footnote back link missing')
        if len(tree.xpath('//h:table', namespaces=NS)) != sum(t['type'] == 'table' for t in source_tokens): raise ValueError('Table loss')
        for source, actual in zip((t for t in source_tokens if t['type'] == 'table'), tree.xpath('//h:table', namespaces=NS)):
            rows = [source['header']] + source['rows']
            actual_rows = actual.xpath('./h:thead/h:tr | ./h:tbody/h:tr', namespaces=NS)
            if len(rows) != len(actual_rows): raise ValueError(f'Table row mismatch: {c["file"]}')
            for cells, actual_row in zip(rows, actual_rows):
                actual_cells = actual_row.xpath('./h:th | ./h:td', namespaces=NS)
                if len(cells) != len(actual_cells): raise ValueError(f'Table column mismatch: {c["file"]}')
                for cell, actual_cell in zip(cells, actual_cells):
                    actual_cell_text = visible_text(actual_cell, './/h:sup[h:a[@epub:type="noteref"]]')
                    if normalized(actual_cell_text) != normalized(expected_text(cell['tokens'])):
                        raise ValueError(f'Table cell mismatch: {c["file"]}')
        if len(tree.xpath('//h:img', namespaces=NS)) != sum(t['type'] in ('image','figure') for t in source_tokens): raise ValueError('Image loss')
        expected_alts = [clean(t['alt'] if t['type'] == 'figure' else t['text']) for t in source_tokens if t['type'] in ('image','figure')]
        if tree.xpath('//h:img/@alt', namespaces=NS) != expected_alts: raise ValueError(f'Image alt mismatch: {c["file"]}')
        if tree.xpath('//h:section[@class="notes"]/h:ol/h:li/@value', namespaces=NS) != list(c['notes']):
            raise ValueError(f'Note numbering mismatch: {c["file"]}')
        if tree.xpath('//h:pre[contains(.,"flowchart ")]', namespaces=NS): raise ValueError('Raw Mermaid leaked')
    return {'xmlDocuments': len(docs), 'localLinksValidated': links, 'textComparison': 'all chapter titles, body text, and every note match prepared tokens (whitespace ignored)'}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, default=ROOT/'tmp/book/book.json')
    ap.add_argument('--output', type=Path, default=ROOT/'交付/中国政治是怎么运转的.epub')
    ap.add_argument('--expanded', type=Path, default=ROOT/'tmp/book/epub')
    args = ap.parse_args()
    book = json.loads(args.input.read_text())
    if len(book) != 31 or len({c['id'] for c in book}) != 31:
        raise ValueError('Expected 31 uniquely identified sections')
    folder = args.expanded.resolve()
    # Delete only this tool's private expanded artifact; never shared preparation data.
    if folder == ROOT or folder == ROOT/'tmp/book' or folder == args.input.parent.resolve():
        raise ValueError('Unsafe expanded output directory')
    if folder.exists(): shutil.rmtree(folder)
    package = folder/'EPUB'
    (package/'images').mkdir(parents=True)
    (folder/'META-INF').mkdir()
    (folder/'mimetype').write_bytes(b'application/epub+zip')
    (folder/'META-INF/container.xml').write_text(XML+'<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="EPUB/package.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    (package/'styles.css').write_text(CSS)
    images, stats = {}, []
    for c in book:
        r = Renderer(c, package, images)
        body = r.render(c['tokens'])
        if Counter(c['refs']) != r.refs: raise ValueError(f'Reference token mismatch: {c["file"]}')
        notes = []
        rendered_notes = {n:r.render(c['notesTokens'][n]) for n in c['notes']}
        for n in c['notes']:
            if r.refs[n] == 0: raise ValueError(f'Unused note: {c["file"]}:{n}')
            text = rendered_notes[n]
            backs = ' '.join(f'<a href="#ref-{n}-{i}" aria-label="返回注{n}第{i}处引用">↩{i}</a>' for i in range(1,r.refs[n]+1))
            notes.append(f'<li value="{int(n)}"><aside epub:type="footnote" role="doc-footnote" id="note-{n}"><div>{text}</div><p class="backlinks">{backs}</p></aside></li>')
        end = '<section class="notes" epub:type="endnotes"><h2 id="notes">注释与资料</h2><ol>'+''.join(notes)+'</ol></section>' if notes else ''
        (package/f'{c["id"]}.xhtml').write_text(document(c['title'], '<main><h1 id="chapter-title">'+esc(c['title'])+'</h1><div id="chapter-body">'+body+'</div>'+end+'</main>'))
        stats.append({'id':c['id'], 'file':c['file'], 'tables':r.tables, 'figures':r.figures, 'notes':len(notes), 'references':sum(r.refs.values())})
    toc = ''.join(f'<li><a href="{c["id"]}.xhtml">{esc(c["title"])}</a></li>' for c in book)
    (package/'nav.xhtml').write_text(document('目录', f'<nav epub:type="toc" id="toc"><h1>中国政治是怎么运转的</h1><h2>目录</h2><ol>{toc}</ol></nav>'))
    modified = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    uid = 'urn:sha256:'+digest(args.input)
    manifest = '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="css" href="styles.css" media-type="text/css"/>'
    manifest += ''.join(f'<item id="{c["id"]}" href="{c["id"]}.xhtml" media-type="application/xhtml+xml"/>' for c in book)
    manifest += ''.join(f'<item id="image-{i}" href="{data["href"]}" media-type="image/png"/>' for i,data in enumerate(images.values()))
    spine = ''.join(f'<itemref idref="{c["id"]}"/>' for c in book)
    (package/'package.opf').write_text(XML+f'<package xmlns="{OPF}" version="3.0" unique-identifier="book-id" xml:lang="zh-CN"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="book-id">{uid}</dc:identifier><dc:title>中国政治是怎么运转的</dc:title><dc:language>zh-CN</dc:language><meta property="dcterms:modified">{modified}</meta></metadata><manifest>{manifest}</manifest><spine>{spine}</spine></package>')
    checks = validate(folder, book, stats)
    for data in images.values():
        if digest(package/data['href']) != data['sha256']: raise ValueError('Copied image changed')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w') as z:
        z.write(folder/'mimetype', 'mimetype', compress_type=zipfile.ZIP_STORED)
        for p in sorted(folder.rglob('*')):
            if p.is_file() and p.name != 'mimetype':
                z.write(p, p.relative_to(folder).as_posix(), compress_type=zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(args.output) as z:
        first = z.infolist()[0]
        assert first.filename == 'mimetype' and first.compress_type == zipfile.ZIP_STORED
        assert not first.extra and z.read('mimetype') == b'application/epub+zip'
        assert z.testzip() is None
    stale = [c['file'] for c in book if (ROOT/'书稿'/c['file']).stat().st_mtime > args.input.stat().st_mtime]
    report = {'status':'validated prepared-data build', 'builtAt': modified, 'inputSha256':digest(args.input), 'epubSha256':digest(args.output), 'sections':len(book), 'chapters':stats, 'images':images, 'checks':checks, 'sourceFilesNewerThanPreparation':stale}
    (folder.parent/'epub-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'output':str(args.output),'sections':len(book),'notes':sum(x['notes'] for x in stats),'references':sum(x['references'] for x in stats),'tables':sum(x['tables'] for x in stats),'figures':sum(x['figures'] for x in stats),'staleSourceFiles':len(stale),'checks':checks},ensure_ascii=False))

if __name__ == '__main__':
    main()
