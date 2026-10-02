#!/usr/bin/env bash
# Скачивает архивы демоверсий, спецификаций и кодификаторов ОГЭ с doc.fipi.ru
# за указанные годы (по умолчанию 2026 и 2027). Список ссылок берётся со страницы
# https://fipi.ru/oge/demoversii-specifikacii-kodifikatory
set -euo pipefail
YEARS=${*:-"2027 2026"}
PAGE=$(mktemp)
curl -sSL https://fipi.ru/oge/demoversii-specifikacii-kodifikatory -o "$PAGE"
for y in $YEARS; do
  mkdir -p "dl/$y"
  grep -oE "href=\"[^\"]*/$y/[^\"]*\"" "$PAGE" | sed 's/href="//;s/"$//' | sort -u | while read -r url; do
    echo "$url"; curl -sSL --retry 3 -o "dl/$y/$(basename "$url")" "$url"
  done
done
# распаковка: имена файлов внутри архивов в кодировке cp866, поэтому используем python
python3 - "$YEARS" <<'PY'
import sys, zipfile, os, glob
for y in sys.argv[1].split():
    for z in glob.glob(f'dl/{y}/*.zip'):
        out = f'ex/{y}/{os.path.basename(z)[:-4]}'
        with zipfile.ZipFile(z) as zf:
            for info in zf.infolist():
                if info.is_dir(): continue
                n = info.filename
                if not (info.flag_bits & 0x800):
                    try: n = n.encode('cp437').decode('cp866')
                    except Exception: pass
                dest = os.path.join(out, *[p[:80] for p in n.split('/')])
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with zf.open(info) as s, open(dest, 'wb') as d: d.write(s.read())
PY
# текстовый слой: pdftotext (poppler-utils)
find ex -name '*.pdf' -not -path '*Доп. файлы*' -exec sh -c 'pdftotext -enc UTF-8 "$1" "${1%.pdf}.txt"' _ {} \;
