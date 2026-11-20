"""Audit §7.3 : règles de montage vérifiées par script, sur src/data/usages.json (produit par resolve_montage.py).

  - chaque utilisation d'extrait dure au plus 6,0 s ;
  - aucune utilisation contiguë d'une même scène (même plan d'origine prolongé d'un plan du film au suivant) ;
  - aucune répétition d'un même passage, sauf reprise déclarée et non adjacente ;
  - les onze captures complémentaires (01 à 11) sont utilisées ; la 12 (seconde prise) jamais pour le même moment que la 08 ;
  - aucun recadrage ne déforme l'image ; le recadrage reste dans la zone utile ;
  - 05, 06 et 07 ne sont pas agrandies plus de 1,8 fois ;
  - les images utilisées sont dans les plages propres validées ;
  - le test : deux passages identiques (même entrée, durée, cadrage, vitesse) ;
  - aucune mire de calage (capture absente) dans une livraison.

    python3 tools/audit_montage.py [--livraison]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'src' / 'data'
FPS = 30
MAX_USE = 6.0
OFFSET_12_TO_08 = None  # décalage temporel 12 → 08, mesuré sur les captures (sources.json : "decalage_12_vers_08")


def main():
    delivery = '--livraison' in sys.argv
    U = json.loads((DATA / 'usages.json').read_text(encoding='utf-8'))
    S = json.loads((DATA / 'sources.json').read_text(encoding='utf-8'))['captures']
    M = json.loads((DATA / 'montage.json').read_text(encoding='utf-8'))
    fails, warns = [], []
    U.sort(key=lambda u: (u['from'], u['plan']))

    # 1. durée de chaque utilisation
    for u in U:
        d = (u['to'] - u['from']) / FPS
        if d > MAX_USE + 1e-6:
            fails.append(f"{u['plan']} {u['file']} : {d:.2f} s > 6,0 s")
    longest = max((u['to'] - u['from']) / FPS for u in U)

    # 2. continuité : un plan du film qui prolonge le plan précédent (même capture, passage contigu ou chevauchant)
    for a, b in zip(U, U[1:]):
        if a['capture'] != b['capture'] or b['from'] > a['to'] + 1:
            continue
        gap = b['in'] - a['last']
        same_shot = not any(a['last'] < c <= b['in'] for c in S[a['capture']].get('coupes', [])) if S[a['capture']].get('coupes') else None
        if -1 <= gap < 30 and same_shot is not False:
            fails.append(f"{a['plan']} → {b['plan']} ({a['file']}) : passage contigu (écart de {gap} images dans la source)")
        elif same_shot:
            warns.append(f"{a['plan']} → {b['plan']} ({a['file']}) : même plan d’origine sur deux plans successifs (écart {gap / FPS:.1f} s) — vérifier la lecture nouvelle")

    # 3. répétitions
    for i, a in enumerate(U):
        for b in U[i + 1:]:
            if a['capture'] != b['capture']:
                continue
            overlap = min(a['last'], b['last']) - max(a['in'], b['in'])
            if overlap >= 0:
                if not (b.get('reprise') or a.get('reprise')):
                    fails.append(f"{a['plan']} et {b['plan']} ({a['file']}) : même passage réutilisé sans reprise déclarée")
                elif abs(b['from'] - a['to']) <= 1 and a['plan'] != b['plan']:
                    fails.append(f"{a['plan']} et {b['plan']} ({a['file']}) : reprise adjacente (boucle)")

    # 4. captures utilisées
    used = sorted({u['capture'] for u in U})
    missing = [k for k in [f'{i:02d}' for i in range(1, 12)] if k not in used]
    if missing:
        fails.append(f"captures complémentaires non utilisées : {', '.join(missing)}")
    # 12 et 08 : jamais pour le même moment
    off = S.get('12', {}).get('decalage_12_vers_08')
    if off is not None:
        for a in [u for u in U if u['capture'] == '08']:
            for b in [u for u in U if u['capture'] == '12']:
                lo, hi = b['in'] + off, b['last'] + off
                if min(a['last'], hi) >= max(a['in'], lo):
                    fails.append(f"{a['plan']} (08) et {b['plan']} (12) montrent le même moment")
    else:
        warns.append('décalage 12 → 08 non mesuré (captures absentes) : contrôle « même moment » à refaire')

    # 5. géométrie
    for u in U:
        ar = abs(u['aspect_crop'] - u['aspect_dest']) / u['aspect_dest']
        if ar > 0.005:
            fails.append(f"{u['plan']} {u['file']} : déformation {ar * 100:.2f} %")
        ax, ay, aw, ah = S[u['capture']]['active']
        c = u['crop']
        if c['x'] < ax - 0.5 or c['y'] < ay - 0.5 or c['x'] + c['w'] > ax + aw + 0.5 or c['y'] + c['h'] > ay + ah + 0.5:
            fails.append(f"{u['plan']} {u['file']} : recadrage hors de la zone utile")
        if u['capture'] in ('05', '06', '07') and u['scale_max'] > 1.8 + 1e-3:
            fails.append(f"{u['plan']} {u['file']} : agrandi ×{u['scale_max']:.2f} (> 1,8)")
        if u['scale_max'] > u['limit'] + 1e-3:
            fails.append(f"{u['plan']} {u['file']} : agrandi ×{u['scale_max']:.2f} (> limite {u['limit']})")

    # 6. plages propres
    for u in U:
        ranges = S[u['capture']].get('plages_propres') or []
        if not ranges:
            warns.append(f"{u['plan']} {u['file']} : plages propres pas encore validées sur la capture") if S[u['capture']].get('present') else None
            continue
        if not any(r[0] <= u['in'] and u['last'] <= r[1] for r in ranges):
            fails.append(f"{u['plan']} {u['file']} : images {u['in']}–{u['last']} hors des plages propres validées")

    # 7. le test
    tests = {x.get('test'): x['id'] for x in M['visuel'] if x.get('test')}
    if 1 in tests and 2 in tests:
        t1 = next(u for u in U if u['plan'] == tests[1])
        t2 = next(u for u in U if u['plan'] == tests[2])
        same = all(t1[k] == t2[k] for k in ('in', 'last', 'rate', 'crop', 'dest', 'file')) and (t1['to'] - t1['from']) == (t2['to'] - t2['from'])
        dur = (t1['to'] - t1['from']) / FPS
        print(f"[test] passage 1 : {t1['in']}–{t1['last']} · {dur:.2f} s · passage 2 : {t2['in']}–{t2['last']} · {(t2['to'] - t2['from']) / FPS:.2f} s · {'IDENTIQUES' if same else 'DIFFÉRENTS'}")
        if not same or abs(dur - 3.0) > 1e-6:
            fails.append('test : les deux passages ne sont pas identiques ou ne durent pas 3,0 s')

    # 8. mires
    ph = [u for u in U if u['placeholder']]
    if ph:
        (fails if delivery else warns).append(f"{len(ph)} utilisations sur mire de calage (captures absentes)")

    print(f"[montage] {len(U)} utilisations · plus longue {longest:.2f} s · captures utilisées : {', '.join(used)}")
    for w in [w for w in warns if w]:
        print('  attention :', w)
    for f in fails:
        print('  ÉCHEC :', f)
    print('AUDIT MONTAGE :', 'OK' if not fails else f'ÉCHEC ({len(fails)})')
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
