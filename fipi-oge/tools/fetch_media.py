"""Скачивает картинки и вложения, на которые ссылаются задания и общие тексты (out/*.json),
в каталог images/ через curl с переиспользованием соединения. Нужен ca-with-gs.pem (см. README)."""
import json, glob, os, subprocess
imgs, files = set(), set()
for f in glob.glob('out/*.json'):
    if f.endswith('_stats.json'): continue
    d = json.load(open(f, encoding='utf-8'))
    for t in d['tasks'] + d['documents']:
        imgs.update(t['images']); files.update(t['files'])
def run(paths, par):
    cfg = []
    for p in sorted(paths):
        dest = os.path.join('images', p)
        if os.path.exists(dest) and os.path.getsize(dest) > 0: continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        cfg.append(f'url = "https://oge.fipi.ru/{p}"\noutput = "{dest}"\n')
    if not cfg: return
    open('curl.cfg', 'w').write(''.join(cfg))
    subprocess.run(['curl', '-sS', '--cacert', 'ca-with-gs.pem', '--retry', '5', '--retry-all-errors', '--retry-delay', '2',
                    '--parallel', '--parallel-max', str(par), '--config', 'curl.cfg'])
run(imgs, 6)    # картинки: мелкие png/gif/jpg
run(files, 3)   # вложения: mp3 (аудирование, изложение), zip/rar (файлы к заданиям по информатике)
missing = [p for p in imgs | files if not os.path.exists(os.path.join('images', p))]
print('missing:', len(missing)); open('media_missing.txt', 'w').write('\n'.join(sorted(missing)))
