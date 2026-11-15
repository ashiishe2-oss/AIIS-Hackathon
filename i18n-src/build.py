"""Build public/i18n/<code>.json from i18n-src/<code>.txt (numbered lines matching en.txt)."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'public', 'i18n')
en = open(os.path.join(HERE, 'en.txt'), encoding='utf-8').read().splitlines()
ok = True
for fn in sorted(os.listdir(HERE)):
    if not fn.endswith('.txt') or fn == 'en.txt':
        continue
    code = fn[:-4]
    rows = {}
    for ln in open(os.path.join(HERE, fn), encoding='utf-8').read().splitlines():
        if not ln.strip():
            continue
        n, _, t = ln.partition('|')
        rows[int(n)] = t.strip()
    probs = []
    missing = [i for i in range(1, len(en) + 1) if i not in rows]
    extra = [i for i in rows if i > len(en)]
    if missing or extra:
        probs.append(f'missing {missing[:10]} extra {extra[:10]}')
    d = {}
    for i, key in enumerate(en, 1):
        t = rows.get(i)
        if not t:
            continue
        if sorted(re.findall(r'\{\d\}', key)) != sorted(re.findall(r'\{\d\}', t)):
            probs.append(f'{i}: placeholders differ: {key!r} -> {t!r}')
        nums = lambda s: sorted(set(re.findall(r'\d+', re.sub(r'\{\d\}', '', s.replace('24x7', '24')))) - {'7'})
        if nums(key) != nums(t):
            probs.append(f'{i}: numbers differ: {key!r} -> {t!r}')
        d[key] = t
    os.makedirs(OUT, exist_ok=True)
    json.dump(d, open(os.path.join(OUT, code + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(code, len(d), 'keys', 'OK' if not probs else '')
    for p in probs:
        ok = False
        print('   ', p)
sys.exit(0 if ok else 1)
