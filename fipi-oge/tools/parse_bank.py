import os, re, json, glob, html, sys
subjects = [l.rstrip('\n').split('\t') for l in open('subjects.tsv', encoding='utf-8') if l.strip()]
PIC = re.compile(r"<script[^>]*>\s*ShowPictureQ\w*\(\s*['\"]([^'\"]+)['\"]\s*(?:,\s*['\"]([^'\"]*)['\"])?[^<]*</script>", re.S|re.I)
def fix_pic(m):
    p = m.group(1)
    while '. ' in p: p = p.replace('. ', '.')
    alt = html.escape(m.group(2) or '')
    return f'<img src="{p}" alt="{alt}">'
def clean_html(h):
    h = PIC.sub(fix_pic, h)
    h = re.sub(r'<script.*?</script>', '', h, flags=re.S|re.I)
    h = re.sub(r'<a name="[^"]*"></a>', '', h)
    h = re.sub(r'\s+', ' ', h).strip()
    return h
def to_text(h):
    t = re.sub(r'<m:math.*?</m:math>', lambda m: mathml_text(m.group(0)), h, flags=re.S|re.I)
    t = re.sub(r'<img[^>]*src="([^"]+)"[^>]*>', r' [рис.: \1] ', t)
    t = re.sub(r'<br\s*/?>|</p>|</tr>|</div>|</li>', '\n', t, flags=re.I)
    t = re.sub(r'</td>', ' | ', t, flags=re.I)
    t = re.sub(r'<[^>]+>', '', t)
    t = html.unescape(t)
    t = re.sub(r'[ \t\xa0]+', ' ', t); t = re.sub(r' *\n *', '\n', t); t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()
def mathml_text(m):
    # crude linearisation of MathML: keep token contents in order
    toks = re.findall(r'<m:(mi|mn|mo|mtext)[^>]*>(.*?)</m:\1>', m, re.S|re.I)
    return ' ' + ''.join(html.unescape(re.sub(r'<[^>]+>', '', t[1])) for t in toks) + ' '
def parse_block(code, guid_proj, b):
    sid = re.match(r"<div class=\"qblock[^\"]*\" id='q(\w+)'>", b).group(1)
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
    ah = clean_html(ans.group(1)) if ans else ''
    # strip interactive inputs from the answer area but keep option texts
    ah_vis = re.sub(r'<input[^>]*>', '', ah)
    imgs = sorted(set(re.findall(r'<img[^>]*src="([^"]+)"', qh + ah)))
    return {
        'id': sid, 'guid': guid.upper(), 'subject': code,
        'hint': html.unescape(hint.group(1)).strip() if hint else '',
        'kes': info.get('КЭС', ''), 'answer_type': info.get('Тип ответа', ''),
        'extra': {k: v for k, v in info.items() if k not in ('КЭС', 'Тип ответа')},
        'question_html': qh, 'answer_html': ah_vis,
        'question_text': to_text(qh), 'answer_text': to_text(ah_vis),
        'images': imgs,
        'url': f'https://oge.fipi.ru/bank/index.php?proj={guid_proj}&qid={guid.upper()}',
    }
def split_blocks(s):
    idx = [m.start() for m in re.finditer(r'<div class="qblock[^"]*" id=\'q\w+\'>', s)]
    idx.append(len(s))
    return [s[idx[i]:idx[i+1]] for i in range(len(idx)-1)]
if __name__ == '__main__':
    os.makedirs('out', exist_ok=True)
    stats = {}
    for guid_proj, code, name in subjects:
        tasks, seen = [], set()
        for fn in sorted(glob.glob(f'raw/{code}/page_*.html')):
            s = open(fn, 'rb').read().decode('cp1251', 'replace')
            for b in split_blocks(s):
                try: t = parse_block(code, guid_proj, b)
                except Exception as e: print('PARSE FAIL', fn, e, file=sys.stderr); continue
                if t['guid'] in seen: continue
                seen.add(t['guid']); tasks.append(t)
        if not tasks: continue
        json.dump({'subject': name, 'code': code, 'project_guid': guid_proj, 'source': f'https://oge.fipi.ru/bank/index.php?proj={guid_proj}', 'count': len(tasks), 'tasks': tasks},
                  open(f'out/{code}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        stats[code] = (name, len(tasks), sum(len(t['images']) for t in tasks), sum(1 for t in tasks if not t['question_text'] and not t['images']))
        print(code, stats[code], flush=True)
    json.dump(stats, open('out/_stats.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
