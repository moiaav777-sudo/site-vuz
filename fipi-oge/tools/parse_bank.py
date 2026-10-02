"""Разбор выгруженных страниц открытого банка заданий ОГЭ (raw/<код>/page_NNN.html) в JSON.

Банк отдаёт поток блоков <div class="qblock">: блок без id — общий текст (документ)
к группе заданий «Задание №1…N», блоки с id — сами задания. Картинки и вложения
вставляются через JS-функции ShowPicture*(…), их заменяем на <img>/<a>.
"""
import os, re, json, glob, html, sys
import xml.etree.ElementTree as ET

subjects = [l.rstrip('\n').split('\t') for l in open('subjects.tsv', encoding='utf-8') if l.strip()]
IMG_EXT = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg')
BLOCK = re.compile(r'<div class="qblock[^"]*"(?: id=\'q(\w+)\')?>')
SCRIPT_CALL = re.compile(r"<script[^>]*>\s*(ShowPicture\w*)\(([^<]*?)\)\s*;?\s*</script>", re.S | re.I)

def fix_path(p):
    while '. ' in p: p = p.replace('. ', '.')
    return p

def render_call(fn, args, base):
    """ShowPicture*(…) -> HTML. args: список строковых аргументов."""
    paths = [fix_path(a) for a in args if re.search(r'\.\w{2,4}$', a) and '/' in a or (fn == 'ShowPicture' and re.search(r'\.\w{2,4}$', a))]
    if fn == 'ShowPicture' and paths:                      # относительный путь внутри документа
        paths = [base + p if not p.startswith('docs/') else p for p in paths]
    hint = next((a for a in args if a and not re.search(r'\.\w{2,4}$', a) and not a.isdigit()), '')
    out = []
    files = [p for p in paths if not p.lower().endswith(IMG_EXT)]
    imgs = [p for p in paths if p.lower().endswith(IMG_EXT)]
    if fn == 'ShowPictureQ3' and len(imgs) == 2:            # картинка + инвертированная версия: берём первую
        imgs = imgs[:1]
    for f in files:
        out.append(f'<a class="attachment" href="{f}">{html.escape(os.path.basename(f))}</a>')
    if files and imgs:                                      # превью к вложению не считаем картинкой задания
        imgs = []
    for i in imgs:
        out.append(f'<img src="{i}" alt="{html.escape(hint)}">')
    return ' '.join(out)

def split_args(s):
    return [a for a in re.findall(r"""['"]([^'"]*)['"]""", s)]

def clean_html(h, base=''):
    h = SCRIPT_CALL.sub(lambda m: render_call(m.group(1), split_args(m.group(2)), base), h)
    h = re.sub(r'<script.*?</script>', '', h, flags=re.S | re.I)
    h = re.sub(r'<a name="[^"]*"></a>', '', h)
    h = re.sub(r'\s+', ' ', h).strip()
    return h

def mathml_text(frag):
    """Линеаризация MathML в текст: дроби, степени, индексы, корни."""
    x = re.sub(r'</?m:', lambda m: m.group(0).replace('m:', ''), frag)
    x = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#)(\w+);', lambda m: html.unescape(m.group(0)), x)
    try:
        root = ET.fromstring(x)
    except ET.ParseError:
        toks = re.findall(r'<m:(mi|mn|mo|mtext)[^>]*>(.*?)</m:\1>', frag, re.S | re.I)
        return ' ' + ''.join(html.unescape(re.sub(r'<[^>]+>', '', t[1])) for t in toks) + ' '
    def walk(e):
        tag = e.tag.split('}')[-1]
        ch = [walk(c) for c in e]
        txt = (e.text or '').strip()
        if tag in ('mi', 'mn', 'mo', 'mtext', 'ms'): return txt
        if tag == 'mfrac' and len(ch) == 2: return f'({ch[0]})/({ch[1]})'
        if tag == 'msup' and len(ch) == 2: return f'{ch[0]}^{ch[1]}' if len(ch[1]) == 1 else f'{ch[0]}^({ch[1]})'
        if tag == 'msub' and len(ch) == 2: return f'{ch[0]}_{ch[1]}' if len(ch[1]) == 1 else f'{ch[0]}_({ch[1]})'
        if tag == 'msubsup' and len(ch) == 3: return f'{ch[0]}_({ch[1]})^({ch[2]})'
        if tag == 'msqrt': return '√(' + ''.join(ch) + ')'
        if tag == 'mroot' and len(ch) == 2: return f'{ch[1]}√({ch[0]})'
        if tag == 'mover' and len(ch) == 2: return f'{ch[0]}‾' if ch[1] in ('¯', '‾', '_') else f'{ch[0]}{ch[1]}'
        if tag == 'mtable': return ' [' + '; '.join(ch) + '] '
        if tag == 'mtr': return ' '.join(ch)
        if tag == 'mfenced': return '(' + ', '.join(ch) + ')'
        return ''.join(ch) if ch else txt
    return ' ' + walk(root) + ' '

def to_text(h):
    t = re.sub(r'<m:math.*?</m:math>', lambda m: mathml_text(m.group(0)), h, flags=re.S | re.I)
    t = re.sub(r'<img[^>]*src="([^"]+)"[^>]*>', r' [рис.: \1] ', t)
    t = re.sub(r'<a class="attachment" href="([^"]+)">[^<]*</a>', r' [файл: \1] ', t)
    t = re.sub(r'<br\s*/?>|</p>|</tr>|</div>|</li>|</h\d>', '\n', t, flags=re.I)
    t = re.sub(r'</td>', ' | ', t, flags=re.I)
    t = re.sub(r'<[^>]+>', '', t)
    t = html.unescape(t)
    t = re.sub(r'[ \t\xa0]+', ' ', t); t = re.sub(r' *\n *', '\n', t); t = re.sub(r'\n{3,}', '\n\n', t)
    t = re.sub(r'(\n\|)+\n', '\n', t)
    return t.strip()

def media(h):
    return (sorted(set(re.findall(r'<img[^>]*src="([^"]+)"', h))),
            sorted(set(re.findall(r'<a class="attachment" href="([^"]+)"', h))))

def parse_doc(b):
    hint = re.search(r'<div id="hint" class="hint" name="hint">(.*?)</div>', b, re.S)
    base = re.search(r"files_abs_location='([^']*)'", b)
    body = b[hint.end():] if hint else b
    body = re.sub(r'^.*?files_abs_location=\'[^\']*\';\s*</script>', '', body, count=1, flags=re.S) if base else body
    body = re.sub(r'</div>\s*$', '', body.strip())
    h = clean_html(body, base.group(1) if base else '')
    imgs, files = media(h)
    return {'hint': html.unescape(hint.group(1)).strip() if hint else '', 'html': h, 'text': to_text(h), 'images': imgs, 'files': files}

def parse_task(code, guid_proj, b):
    sid = BLOCK.match(b).group(1)
    guid = re.search(r'name="guid" value="([0-9A-Fa-f]{32})"', b).group(1)
    hint = re.search(r'<div id="hint" class="hint" name="hint">(.*?)</div>', b, re.S)
    q = re.search(r"<TD valign=top width=100% bgcolor=\"#FAFBCA\" class='cell_0'>(.*?)</TD></TR>\s*<TR bgcolor=\"#FFFFFF\">", b, re.S)
    ans = re.search(r"<TD class='varinats-block'>(.*?)</TD></TR>\s*<TR><TD class='submit-block'>", b, re.S)
    info = {}
    for k, v in re.findall(r'<td class="param-name">([^<]*?):?</td><td[^>]*>(.*?)</td>', b, re.S):
        vals = [html.unescape(re.sub(r'<[^>]+>', ' ', x)).strip() for x in re.findall(r'<div>(.*?)</div>', v, re.S)] or [html.unescape(re.sub(r'<[^>]+>', ' ', v)).strip()]
        vals = [re.sub(r'\s+', ' ', x) for x in vals if x.strip()]
        info[k.strip()] = vals if len(vals) > 1 else (vals[0] if vals else '')
    qh = clean_html(q.group(1)) if q else ''
    ah = re.sub(r'<input[^>]*>', '', clean_html(ans.group(1))) if ans else ''
    imgs, files = media(qh + ' ' + ah)
    hint_txt = html.unescape(hint.group(1)).strip() if hint else ''
    m = re.match(r'Задание\s*№\s*(\d+)\.?\s*(.*)', hint_txt)
    return {
        'id': sid, 'guid': guid.upper(), 'subject': code,
        'document_id': None, 'number_in_group': int(m.group(1)) if m else None,
        'hint': m.group(2).strip() if m else hint_txt,
        'kes': info.get('КЭС', ''), 'answer_type': info.get('Тип ответа', ''),
        'extra': {k: v for k, v in info.items() if k not in ('КЭС', 'Тип ответа')},
        'question_html': qh, 'answer_html': ah,
        'question_text': to_text(qh), 'answer_text': to_text(ah),
        'images': imgs, 'files': files,
        'url': f'https://oge.fipi.ru/bank/index.php?proj={guid_proj}&qid={guid.upper()}',
    }

def split_blocks(s):
    idx = [m.start() for m in BLOCK.finditer(s)] + [len(s)]
    return [s[idx[i]:idx[i+1]] for i in range(len(idx) - 1)]

if __name__ == '__main__':
    os.makedirs('out', exist_ok=True)
    stats = {}
    for guid_proj, code, name in subjects:
        tasks, docs, seen = [], [], set()
        cur_doc = None
        for fn in sorted(glob.glob(f'raw/{code}/page_*.html')):
            s = open(fn, 'rb').read().decode('cp1251', 'replace')
            for b in split_blocks(s):
                if BLOCK.match(b).group(1) is None:           # общий текст
                    d = parse_doc(b); d['id'] = len(docs) + 1; docs.append(d); cur_doc = d['id']
                    continue
                try: t = parse_task(code, guid_proj, b)
                except Exception as e: print('PARSE FAIL', fn, e, file=sys.stderr); continue
                if t['number_in_group'] is None: cur_doc = None
                t['document_id'] = cur_doc
                if t['guid'] in seen: continue
                seen.add(t['guid']); tasks.append(t)
        if not tasks: continue
        json.dump({'subject': name, 'code': code, 'project_guid': guid_proj,
                   'source': f'https://oge.fipi.ru/bank/index.php?proj={guid_proj}',
                   'count': len(tasks), 'documents_count': len(docs), 'documents': docs, 'tasks': tasks},
                  open(f'out/{code}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        n_img = len({p for t in tasks for p in t['images']} | {p for d in docs for p in d['images']})
        n_files = len({p for t in tasks for p in t['files']} | {p for d in docs for p in d['files']})
        stats[code] = {'subject': name, 'tasks': len(tasks), 'documents': len(docs), 'images': n_img, 'files': n_files,
                       'tasks_with_document': sum(1 for t in tasks if t['document_id'])}
        print(code, stats[code], flush=True)
    json.dump(stats, open('out/_stats.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
