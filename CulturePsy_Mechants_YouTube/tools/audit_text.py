"""Audit §7.1 : la narration hors crochets et les sous-titres sont identiques (diff automatique),
et les sous-titres respectent 2 lignes × 42 caractères, 17 caractères/s, 1 à 7 s.
Vérifie aussi que les textes incrustés à l'écran (src/data/onscreen.json, produit par le rendu) ne contiennent
aucun mot entre crochets ni aucune référence, sauf les crédits [À l'écran : …] repris à l'identique.

    python3 tools/audit_text.py
"""
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textlib import ROOT, narration_sentences, norm_ws, parse_script, typo

DATA = ROOT / 'src' / 'data'


def parse_srt(path):
    blocks = re.split(r'\n\s*\n', path.read_text(encoding='utf-8').strip())
    out = []
    for b in blocks:
        ls = b.splitlines()
        m = re.match(r'(\d\d):(\d\d):(\d\d),(\d{3}) --> (\d\d):(\d\d):(\d\d),(\d{3})', ls[1])
        g = list(map(int, m.groups()))
        s = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        out.append({'n': int(ls[0]), 'start': s, 'end': e, 'lines': ls[2:]})
    return out


def main():
    ok = True
    data, sents = narration_sentences()
    narration = norm_ws(' '.join(p['text'] for p in data['paragraphs']))
    srt = parse_srt(ROOT / 'livrables' / 'CulturePsy_Mechants_YouTube.srt')
    subs_text = norm_ws(' '.join(' '.join(e['lines']) for e in srt))
    a, b = narration.split(' '), subs_text.split(' ')
    diff = [d for d in difflib.unified_diff(a, b, 'narration', 'srt', lineterm='', n=2)]
    print(f'[texte] narration : {len(a)} jetons · SRT : {len(b)} jetons · diff : {"IDENTIQUE" if not diff else "DIFFÉRENT"}')
    if diff:
        ok = False
        print('\n'.join(diff[:60]))

    # mots entre crochets ou références dans les sous-titres
    bracket_text = ' '.join(n['text'] for n in data['notes']) + ' ' + ' '.join(data['refs'])
    for marker in ('doi.org', 'pubmed', 'http', '[', ']', 'CHAPITRE', 'Références'):
        if marker in subs_text:
            ok = False
            print(f'[texte] ÉCHEC : « {marker} » présent dans les sous-titres')

    # normes de sous-titrage
    bad = []
    for i, e in enumerate(srt):
        dur = e['end'] - e['start']
        chars = sum(len(l) for l in e['lines']) + (len(e['lines']) - 1)
        cps = chars / dur
        probs = []
        if len(e['lines']) > 2:
            probs.append(f'{len(e["lines"])} lignes')
        for l in e['lines']:
            if len(l) > 42:
                probs.append(f'ligne de {len(l)} car.')
        if cps > 17.0 + 1e-6:
            probs.append(f'{cps:.1f} car./s')
        if dur < 1.0 - 1e-6 or dur > 7.0 + 1e-6:
            probs.append(f'durée {dur:.2f} s')
        if i + 1 < len(srt) and srt[i + 1]['start'] < e['end'] - 1e-6:
            probs.append('chevauchement')
        if probs:
            bad.append((e['n'], probs, ' / '.join(e['lines'])))
    print(f'[srt] {len(srt)} sous-titres · {len(srt) - len(bad)} conformes (2 × 42 car., ≤ 17 car./s, 1–7 s)')
    for n, probs, t in bad:
        ok = False
        print(f'   n°{n} : {", ".join(probs)} — {t}')
    cps_all = [(sum(len(l) for l in e['lines']) + len(e['lines']) - 1) / (e['end'] - e['start']) for e in srt]
    print(f'[srt] car./s max {max(cps_all):.2f} · moyenne {sum(cps_all) / len(cps_all):.2f} · durée min {min(e["end"] - e["start"] for e in srt):.2f} s · max {max(e["end"] - e["start"] for e in srt):.2f} s')

    # typographie : espaces fines insécables
    raw = (ROOT / 'livrables' / 'CulturePsy_Mechants_YouTube.srt').read_text(encoding='utf-8')
    if re.search(r'[  ][?!:;»]', raw) or re.search(r'«[  ]', raw) or "'" in raw:
        ok = False
        print('[typo] ÉCHEC : espace ordinaire avant ? ! : ; » ou après «, ou apostrophe droite')
    else:
        print('[typo] espaces fines insécables et apostrophes typographiques : conformes')

    # textes à l'écran (exportés par le montage)
    ons = DATA / 'onscreen.json'
    if ons.exists():
        items = json.loads(ons.read_text(encoding='utf-8'))
        credits = {norm_ws(typo(c['text'])) for c in data['credits']}
        for it in items:
            t = norm_ws(it['text'])
            if it['kind'] == 'credit' and t not in credits:
                ok = False
                print(f'[écran] ÉCHEC : crédit différent du script : {it["text"]}')
            for marker in ('doi.org', 'pubmed', 'http', '[', ']'):
                if marker in t:
                    ok = False
                    print(f'[écran] ÉCHEC : « {marker} » dans {it["text"]}')
        print(f'[écran] {len(items)} textes incrustés vérifiés ; crédits du script : {len(credits)} attendus, '
              f'{len({norm_ws(i["text"]) for i in items if i["kind"] == "credit"})} présents')
        missing = credits - {norm_ws(i['text']) for i in items if i['kind'] == 'credit'}
        if missing:
            ok = False
            print('[écran] ÉCHEC : crédits absents :', missing)
    print('AUDIT TEXTE :', 'OK' if ok else 'ÉCHEC')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
