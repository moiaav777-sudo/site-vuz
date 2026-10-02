import os, re, ssl, sys, time, urllib.request, urllib.error
BASE = 'https://oge.fipi.ru/bank/'
ctx = ssl.create_default_context(cafile='ca-with-gs.pem')
opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.ProxyHandler({'https': os.environ.get('HTTPS_PROXY', '')}))
opener.addheaders = [('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) site-vuz-archiver')]
def get(url, tries=5):
    for i in range(tries):
        try:
            with opener.open(url, timeout=120) as r: return r.read()
        except Exception as e:
            print('retry', i, url, e, flush=True); time.sleep(2 ** i)
    raise RuntimeError(url)
subjects = [l.rstrip('\n').split('\t') for l in open('subjects.tsv', encoding='utf-8') if l.strip()]
PS = 100
for guid, code, name in subjects:
    d = f'raw/{code}'; os.makedirs(d, exist_ok=True)
    first = get(f'{BASE}questions.php?proj={guid}&page=0&pagesize={PS}')
    m = re.search(rb'setQCount\((\d+)', first); count = int(m.group(1))
    pages = -(-count // PS)
    open(f'{d}/page_000.html', 'wb').write(first)
    print(f'{code} {name}: {count} tasks, {pages} pages', flush=True)
    for p in range(1, pages):
        fn = f'{d}/page_{p:03d}.html'
        if os.path.exists(fn) and os.path.getsize(fn) > 5000: continue
        open(fn, 'wb').write(get(f'{BASE}questions.php?proj={guid}&page={p}&pagesize={PS}'))
        time.sleep(0.3)
    print(f'{code} done', flush=True)
print('ALL DONE', flush=True)
