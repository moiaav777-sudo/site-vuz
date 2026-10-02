"""Download every picture referenced by the parsed tasks (out/*.json) into images/."""
import os, ssl, json, glob, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
BASE = 'https://oge.fipi.ru/'
ctx = ssl.create_default_context(cafile='ca-with-gs.pem')
opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.ProxyHandler({'https': os.environ.get('HTTPS_PROXY', '')}))
opener.addheaders = [('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) site-vuz-archiver')]
paths = sorted({p for f in glob.glob('out/*.json') if not f.endswith('_stats.json') for t in json.load(open(f, encoding='utf-8'))['tasks'] for p in t['images']})
print('images to fetch:', len(paths), flush=True)
failed = []
def fetch(p):
    dest = os.path.join('images', p)
    if os.path.exists(dest) and os.path.getsize(dest) > 0: return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for i in range(5):
        try:
            with opener.open(BASE + p, timeout=120) as r: data = r.read()
            open(dest, 'wb').write(data); return
        except Exception as e:
            time.sleep(2 ** i)
    failed.append(p)
with ThreadPoolExecutor(2) as ex:
    for n, _ in enumerate(ex.map(fetch, paths)):
        if n % 500 == 0: print(n, flush=True)
print('failed:', len(failed)); open('images_failed.txt', 'w').write('\n'.join(failed))
