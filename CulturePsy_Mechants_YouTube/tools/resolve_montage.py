"""Résout le montage : ancres (phrase / mot) → images, recadrages → pixels, et produit src/data/resolved.json,
que Remotion lit tel quel. Écrit aussi livrables/LISTE_DES_PLANS.md, src/data/usages.json (audit) et src/data/onscreen.json.

    python3 tools/resolve_montage.py

Ancres (dans src/data/montage.json) :
  "Garde ta réponse"                 début de la phrase qui commence ainsi
  "Garde ta réponse|réponse"         début du mot « réponse » dans cette phrase (« ça#2 » = 2e occurrence)
  "Garde ta réponse|réponse>"        fin de ce mot
  "Garde ta réponse|>"               fin de la phrase
  "Garde ta réponse|réponse|+0.3"    avec décalage en secondes
  "t:2.4"   temps absolu · "fin" fin du film · "parole_fin" fin du dernier mot · "chap:2" début du chapitre 2 (0 = premier)
"""
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textlib import ROOT, norm_ws, typo

DATA = ROOT / 'src' / 'data'
PUBLIC = ROOT / 'public'
FPS = 30
W, H = 1920, 1080
LIMIT_LOWRES = 1.8

cues = json.loads((DATA / 'cues.json').read_text(encoding='utf-8'))
chapters = json.loads((DATA / 'chapters.json').read_text(encoding='utf-8'))
subs = json.loads((DATA / 'subs.json').read_text(encoding='utf-8'))
config = json.loads((DATA / 'config.json').read_text(encoding='utf-8'))
sources = json.loads((DATA / 'sources.json').read_text(encoding='utf-8'))['captures']
montage = json.loads((DATA / 'montage.json').read_text(encoding='utf-8'))
SENTS = cues['sentences']
FILM_END = cues['film_end']
warnings = []


def strip_acc(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def wkey(w):
    w = w.lower().replace("'", '’')
    return w


def find_sentence(key):
    if re.fullmatch(r's\d{3}', key):
        return next(s for s in SENTS if s['id'] == key)
    k = norm_ws(key)
    hits = [s for s in SENTS if norm_ws(s['text']).startswith(k)]
    if not hits:
        hits = [s for s in SENTS if k in norm_ws(s['text'])]
    if len(hits) != 1:
        raise SystemExit(f'Ancre : phrase introuvable ou ambiguë ({len(hits)}) : « {key} »')
    return hits[0]


def anchor_seconds(a):
    if isinstance(a, (int, float)):
        return float(a)
    if not isinstance(a, str):
        raise SystemExit(f'Ancre invalide : {a}')
    a = a.strip()
    if a.startswith('t:'):
        return float(a[2:])
    head, _, rest = a.partition('|')
    if head in ('fin', 'parole_fin'):
        base = FILM_END if head == 'fin' else cues['last_word_end']
        return base + sum(float(x) for x in rest.split('|') if x.strip())
    m = re.fullmatch(r'chap:(\d+)(?:\|([+-][\d.]+))?', a)
    if m:
        return chapters[int(m.group(1))]['start'] + float(m.group(2) or 0)
    parts = a.split('|')
    s = find_sentence(parts[0])
    t = s['start']
    off = 0.0
    for p in parts[1:]:
        p = p.strip()
        if re.fullmatch(r'[+-][\d.]+', p):
            off += float(p)
        elif p == '>':
            t = s['end']
        elif p == '<':
            t = s['start']
        else:
            end = p.endswith('>')
            p = p.rstrip('>')
            nth = 1
            if '#' in p:
                p, n = p.split('#')
                nth = int(n)
            hits = [w for w in s['words'] if wkey(w['w']) == wkey(p) or wkey(w['w']).endswith('’' + wkey(p))]
            if len(hits) < nth:
                raise SystemExit(f'Ancre : mot « {p} » introuvable dans « {s["text"]} »')
            t = hits[nth - 1]['end' if end else 'start']
    return t + off


def F(a):
    return int(round(anchor_seconds(a) * FPS))


def tc_to_frame(v):
    """Image source : entier, ou « mm:ss.cc », ou « mm:ss+ii » (secondes + images)."""
    if isinstance(v, int):
        return v
    m = re.fullmatch(r'(\d+):(\d+(?:\.\d+)?)', v)
    if m:
        return int(round((int(m.group(1)) * 60 + float(m.group(2))) * FPS))
    raise SystemExit(f'Image source invalide : {v}')


SLOTS = {
    'plein': [0, 0, 1920, 1080],
    'gauche': [100, 170, 1000, 562],
    'droite': [820, 170, 1000, 562],
    'duoG': [72, 262, 870, 489],
    'duoD': [978, 262, 870, 489],
    'trioA': [60, 318, 588, 331],
    'trioB': [666, 318, 588, 331],
    'trioC': [1272, 318, 588, 331],
}


def rushes_path(src):
    c = sources[src]
    proxy = PUBLIC / 'proxies' / c['file']
    if c.get('present') and proxy.exists():
        return f"proxies/{c['file']}", False
    if c.get('present'):
        return f"{config.get('rushes', 'rushes')}/{c['file']}", False
    return f"mires/{c['file']}", True


def fit_crop(src, aspect, focus, crop=None, avoid_bottom=False):
    c = sources[src]
    ax, ay, aw, ah = c['active']
    if avoid_bottom and c.get('bande_sous_titres'):
        top_band = c['bande_sous_titres'][0]
        ah = min(ah, top_band - ay)
    if crop:
        x, y, w, h = crop
        if abs((w / h) - aspect) / aspect > 0.004:
            # adapter la hauteur au rapport demandé, sans déformer
            nh = w / aspect
            if nh <= h:
                y += (h - nh) * (focus[1] if focus else 0.5)
                h = nh
            else:
                nw = h * aspect
                x += (w - nw) * (focus[0] if focus else 0.5)
                w = nw
        return [x, y, w, h]
    fx, fy = focus or [0.5, 0.5]
    if aw / ah > aspect:
        w, h = ah * aspect, ah
    else:
        w, h = aw, aw / aspect
    return [ax + (aw - w) * fx, ay + (ah - h) * fy, w, h]


def resolve_clip(spec, start, end, default_dest='plein', plan_id=''):
    src = spec['src']
    c = sources[src]
    path, placeholder = rushes_path(src)
    fit = spec.get('fit', 'crop')
    dest = spec.get('dest', spec.get('layout', default_dest))
    focus = spec.get('focus')
    ax, ay, aw, ah = c['active']
    maxs = spec.get('max_scale', c['max_scale'])
    zoom = spec.get('zoom')
    z1 = max(zoom) if zoom else 1.0
    if dest == 'cadre':
        crop = fit_crop(src, (spec['crop'][2] / spec['crop'][3]) if spec.get('crop') else aw / ah, focus, spec.get('crop'), spec.get('eviter_bas', False))
        s = min(maxs / z1, 1680 / crop[2], 900 / crop[3])
        dw, dh = crop[2] * s, crop[3] * s
        d = [(W - dw) / 2, (H - dh) / 2 + spec.get('dy', 0), dw, dh]
    else:
        d = list(SLOTS[dest]) if isinstance(dest, str) else list(dest)
        if fit == 'contain':
            crop = fit_crop(src, (spec['crop'][2] / spec['crop'][3]) if spec.get('crop') else aw / ah, focus, spec.get('crop'), spec.get('eviter_bas', False))
            nh = d[2] * crop[3] / crop[2]
            if nh > d[3]:
                nw = d[3] * crop[2] / crop[3]
                d = [d[0] + (d[2] - nw) / 2, d[1], nw, d[3]]
            else:
                d = [d[0], d[1] + (d[3] - nh) / 2, d[2], nh]
        else:
            crop = fit_crop(src, d[2] / d[3], focus, spec.get('crop'), spec.get('eviter_bas', False))
    scale = d[2] / crop[2]
    in_f = tc_to_frame(spec['in'])
    rate = spec.get('rate', 1.0)
    if spec.get('freeze'):
        rate = 0.0
    n = end - start
    last = in_f + int(math.ceil(max(0, n - 1) * rate))
    return {
        'src': path,
        'w': c['w'],
        'h': c['h'],
        'crop': {'x': round(crop[0], 2), 'y': round(crop[1], 2), 'w': round(crop[2], 2), 'h': round(crop[3], 2)},
        'dest': {'x': round(d[0], 2), 'y': round(d[1], 2), 'w': round(d[2], 2), 'h': round(d[3], 2)},
        'in': in_f,
        'rate': rate,
        'clean': [in_f, last],
        'from': start,
        'to': end,
        **({'zoom': zoom} if zoom else {}),
        **({'focus': spec['zoom_focus']} if spec.get('zoom_focus') else {}),
        **({'filter': spec['filter']} if spec.get('filter') else {}),
        **({'radius': spec['radius']} if 'radius' in spec else ({'radius': 10} if dest != 'plein' else {})),
        **({'fade': spec['fade']} if spec.get('fade') else {}),
        **({'shadow': True} if dest != 'plein' else {}),
        **({'label': f"{spec.get('note', '')} · {c['file'][:2]} i{in_f}{' (figée)' if rate == 0 else ''}"} if placeholder else {}),
        '_meta': {'capture': src, 'placeholder': placeholder, 'scale': round(scale, 4), 'scale_max': round(scale * z1, 4), 'limit': maxs,
                  'aspect_crop': crop[2] / crop[3], 'aspect_dest': d[2] / d[3], 'plan': plan_id, 'note': spec.get('note', ''),
                  'reprise': spec.get('reprise', False), 'verifier': spec.get('verifier', False)},
    }


def resolve_text(spec, start, end):
    t = {
        'type': 'texte',
        'style': spec.get('style', 'question'),
        'text': typo(spec['text']),
        'x': spec.get('x', 160),
        'y': spec.get('y', 440),
        'w': spec.get('w', 1600),
        'from': F(spec['at']) if 'at' in spec else start,
        'to': F(spec['until']) if 'until' in spec else end,
        'kind': spec.get('kind', spec.get('style', 'question')),
    }
    for k in ('align', 'anchor', 'size', 'color', 'fade', 'fadeOut', 'rise', 'box', 'dimTo'):
        if k in spec:
            t[k] = spec[k]
    if 'dimAt' in spec:
        t['dimAt'] = F(spec['dimAt'])
    if 'strikeAt' in spec:
        t['strikeAt'] = F(spec['strikeAt'])
    if 'highlights' in spec:
        t['highlights'] = [{**h, 'at': F(h['at'])} for h in spec['highlights']]
    return t


def resolve_image(spec, start, end):
    from PIL import Image
    p = PUBLIC / spec['src']
    iw, ih = Image.open(p).size
    d = list(SLOTS[spec['dest']]) if isinstance(spec['dest'], str) else list(spec['dest'])
    aspect = d[2] / d[3]
    fx, fy = spec.get('focus', [0.5, 0.5])
    if iw / ih > aspect:
        w, h = ih * aspect, ih
    else:
        w, h = iw, iw / aspect
    crop = spec.get('crop') or [(iw - w) * fx, (ih - h) * fy, w, h]
    return {'type': 'image', 'src': spec['src'], 'iw': iw, 'ih': ih, 'crop': dict(zip('xywh', crop)), 'dest': dict(zip('xywh', d)),
            'from': F(spec['at']) if 'at' in spec else start, 'to': F(spec['until']) if 'until' in spec else end,
            **{k: spec[k] for k in ('fade', 'zoom', 'filter', 'radius') if k in spec}}


def resolve_layer(spec, start, end, plan_id):
    ty = spec['type']
    s0 = F(spec['at']) if 'at' in spec else start
    s1 = F(spec['until']) if 'until' in spec else end
    if ty == 'clip':
        c = resolve_clip(spec, s0, s1, spec.get('dest', 'gauche'), plan_id)
        return {'type': 'clip', **c}
    if ty == 'texte':
        return resolve_text(spec, start, end)
    if ty == 'image':
        return resolve_image(spec, start, end)
    if ty == 'trait':
        return {'type': 'trait', 'x': spec['x'], 'y': spec['y'], 'h': spec.get('h', 6), 'align': spec.get('align', 'left'), 'from': s0, 'to': s1,
                'widths': [{'at': F(k['at']), 'w': k['w']} for k in spec['widths']]}
    if ty == 'cadre':
        return {'type': 'cadre', 'ref': spec['ref'], 'from': s0, 'to': s1}
    if ty == 'ca':
        return {'type': 'ca', 'quote': spec['quote'], 'pivot': spec['pivot'], 'from': s0, 'to': s1, 'pivotAt': F(spec['pivotAt']), 'y': spec.get('y', 330),
                'comps': [{'text': k['text'], 'at': F(k['at']), 'terrain': k['terrain']} for k in spec['comps']],
                **({'recapAt': F(spec['recapAt'])} if 'recapAt' in spec else {}), **({'eraseAt': F(spec['eraseAt'])} if 'eraseAt' in spec else {})}
    raise SystemExit(f'Calque inconnu : {ty}')


def main():
    total = int(round(FILM_END * FPS))
    vis = montage['visuel']
    starts = [F(p['at']) for p in vis]
    for i in range(1, len(starts)):
        if starts[i] <= starts[i - 1]:
            raise SystemExit(f"Plans dans le désordre ou de durée nulle : {vis[i - 1].get('id')} → {vis[i].get('id')} ({starts[i - 1]} → {starts[i]})")
    plans, usages = [], []
    for i, p in enumerate(vis):
        pid = p.get('id', f'P{i + 1:03d}')
        a = starts[i]
        b = starts[i + 1] if i + 1 < len(vis) else total
        r = {'id': pid, 'from': a, 'to': b, 'type': p['type']}
        for k in ('fade', 'treatment', 'backdrop'):
            if k in p:
                r[k] = p[k]
        if p['type'] == 'clip':
            c = resolve_clip(p, a, b, p.get('layout', 'plein'), pid)
            r['clip'] = c
            if 'backdrop' not in r:
                r['backdrop'] = 'aucun' if c['dest']['w'] >= 1919 and c['dest']['h'] >= 1079 else 'flou'
            usages.append(c)
        elif p['type'] == 'compose':
            r['layers'] = [resolve_layer(l, a, b, pid) for l in p['layers']]
            for l in r['layers']:
                if l['type'] == 'clip':
                    usages.append(l)
        elif p['type'] == 'chapitre':
            ch = chapters[p['num'] - 1]
            r['type'] = 'compose'
            r['layers'] = [
                resolve_text({'style': 'etiquette', 'text': f"Chapitre {p['num']}", 'x': 170, 'y': 404, 'w': 1500, 'kind': 'chapitre', 'fade': 12}, a, b),
                resolve_text({'style': 'grand', 'text': ch['title'], 'x': 170, 'y': 462, 'w': 1600, 'size': 104, 'kind': 'chapitre', 'fade': 14, 'rise': 24}, a, b),
            ]
            r['layers'][0]['from'] = a + 2
            r['layers'][1]['from'] = a + 4
            r['_note'] = f"Carte de chapitre : {ch['title']}"
        elif p['type'] == 'planche':
            exists = (PUBLIC / p['image']).exists()
            r['planche'] = {'src': p['image'], 'missing': not exists, 'title': p.get('title', '')}
            if not exists:
                warnings.append(f"planche manquante : {p['image']}")
        r['_note'] = p.get('note', '')
        plans.append(r)
    # cadres vides : reprennent la zone exacte d'un plan de référence
    for r in plans:
        for l in r.get('layers', []):
            if l['type'] == 'cadre':
                ref = next(q for q in plans if q['id'] == l['ref'])
                l['dest'] = ref['clip']['dest']

    overlays = []
    for o in montage.get('incrustations', []):
        overlays.append(resolve_text(o, 0, total) if o.get('type', 'texte') == 'texte' else resolve_layer(o, 0, total, 'overlay'))

    # audio
    sfx = []
    for s in montage.get('sons', []):
        p = PUBLIC / s['fichier']
        if not p.exists():
            warnings.append(f"son manquant : {s['fichier']}")
            continue
        sfx.append({'src': s['fichier'], 'from': F(s['at']), 'dur': int(round(s.get('duree_max', 2.0) * FPS)), 'volume': s.get('volume', 0.3)})
    voice = []
    vj = DATA / 'voix_montage.json'
    if config.get('voix') and vj.exists():
        voice = json.loads(vj.read_text(encoding='utf-8'))['segments']
    music = None
    if config.get('musique'):
        env = [{'f': F(e['at']), 'v': e['v']} for e in montage['musique']['enveloppe']]
        music = {'src': config['musique'], 'volume': config.get('musiqueVolume', 1.0), 'env': env}
    calage = cues['mode'] == 'calage'
    burn = config.get('sousTitresIncrustes')
    burn = calage if burn is None else burn
    out = {
        'fps': FPS,
        'durationInFrames': total,
        'calage': calage and burn,
        'mires': sum(1 for u in usages if u['_meta']['placeholder']),
        'plans': plans,
        'overlays': overlays,
        'subs': [{'from': int(round(e['start'] * FPS)), 'to': int(round(e['end'] * FPS)), 'lines': e['lines']} for e in subs],
        'banners': {'spoiler': {'from': 0, 'to': F(montage['bandeau_spoilers']['until']), 'text': montage['bandeau_spoilers']['text']}, 'calage': calage},
        'audio': {'voice': voice, 'sfx': sfx, 'music': music},
    }
    (DATA / 'resolved.json').write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    (DATA / 'usages.json').write_text(json.dumps([{**u['_meta'], 'from': u['from'], 'to': u['to'], 'in': u['in'], 'last': u['clean'][1], 'rate': u['rate'],
                                                   'crop': u['crop'], 'dest': u['dest'], 'file': sources[u['_meta']['capture']]['file']} for u in usages],
                                                 ensure_ascii=False, indent=1), encoding='utf-8')
    # textes à l'écran (audit)
    ons = []
    for t in overlays + [l for p in plans for l in p.get('layers', []) if l['type'] == 'texte']:
        ons.append({'kind': t.get('kind', t['style']), 'text': t['text'], 'from': t['from'], 'to': t['to'], 'style': t['style'], 'size': t.get('size')})
    for p in plans:
        for l in p.get('layers', []):
            if l['type'] == 'ca':
                ons.append({'kind': 'mot', 'text': l['quote'], 'from': l['from'], 'to': l['to'], 'style': 'citation', 'size': 92})
                for k in l['comps']:
                    ons.append({'kind': 'mot', 'text': k['text'], 'from': k['at'], 'to': l['to'], 'style': 'liste', 'size': 60})
        if p['type'] == 'planche':
            ons.append({'kind': 'planche', 'text': p['planche']['title'], 'from': p['from'], 'to': p['to'], 'style': 'planche', 'size': None})
    ons.append({'kind': 'bandeau', 'text': montage['bandeau_spoilers']['text'], 'from': 0, 'to': out['banners']['spoiler']['to'], 'style': 'bandeau', 'size': 30})
    for c in chapters:
        pass
    (DATA / 'onscreen.json').write_text(json.dumps(ons, ensure_ascii=False, indent=1), encoding='utf-8')
    write_shot_list(plans, usages, total)
    ph = sum(1 for u in usages if u['_meta']['placeholder'])
    print(f'{len(plans)} plans · {len(usages)} utilisations d’extraits ({ph} sur mire de calage) · {len(overlays)} incrustations · {len(sfx)} sons · {total} images ({total / FPS:.2f} s)')
    for w in warnings:
        print('  !', w)


def fmt(fr):
    t = fr / FPS
    m, s = divmod(t, 60)
    return f'{int(m):02d}:{s:05.2f}'


def write_shot_list(plans, usages, total):
    L = ['# Culture Psy — « Pourquoi défend-on les méchants ? » · YouTube 16:9', '',
         f"## Liste des plans · {'version de calage' if cues['mode'] == 'calage' else 'master'} · {fmt(total)} · 1920 × 1080 · 30 i/s", '',
         '**Entrée → sortie** : images de la capture source (30 i/s), avec le temps mm:ss.cc. **Montage** : position dans le film. '
         'Recadrage : zone de la capture (x, y, largeur × hauteur en px source) et agrandissement.', '',
         '| # | Montage | Fichier | Entrée → sortie | Vitesse | Recadrage · échelle | Plan |', '|---|---|---|---|---|---|---|']
    for k, u in enumerate(sorted(usages, key=lambda u: u['from']), 1):
        m = u['_meta']
        c = u['crop']
        sp = 'figée' if u['rate'] == 0 else f"×{u['rate']:g}".replace('.', ',')
        flag = ' ⚠ mire de calage' if m['placeholder'] else ''
        L.append(f"| {k} | {fmt(u['from'])} → {fmt(u['to'])} | {sources[m['capture']]['file']} | {fmt(u['in'])} → {fmt(u['clean'][1])} (i{u['in']}–{u['clean'][1]}) | {sp} | "
                 f"{c['x']:.0f}, {c['y']:.0f}, {c['w']:.0f} × {c['h']:.0f} · ×{m['scale_max']:.2f} | {m['note']}{flag} |")
    L += ['', '### Autres formes (compositions, planches, cartes)', '']
    for p in plans:
        if p['type'] != 'clip':
            desc = p['_note'] or (p.get('planche') or {}).get('title', '') or p['type']
            L.append(f"- {fmt(p['from'])} → {fmt(p['to'])} · {p['type']} · {desc}")
    (ROOT / 'livrables' / 'LISTE_DES_PLANS.md').write_text('\n'.join(L) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
