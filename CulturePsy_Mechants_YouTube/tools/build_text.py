"""Construit tout ce qui dépend du texte et du minutage de la voix.

    python3 tools/build_text.py

Entrées
  script/Culture_Psy_Mechants_YouTube_Voix_off_v3.txt   script de référence (seul le texte hors crochets est dit)
  src/data/pauses.json                                   débit de calage et silences imposés
  src/data/voix_alignement.json  (facultatif)            alignement mot à mot de la voix (tools/align_voice.py)

Sorties
  src/data/cues.json        phrases et mots minutés (le montage s'y accroche)
  src/data/subs.json        sous-titres (incrustés dans la version de calage)
  src/data/chapters.json    chapitres minutés
  livrables/CulturePsy_Mechants_YouTube.srt
  livrables/chapitres_youtube.txt, livrables/description_youtube.txt
  livrables/reperes_voix.txt (Audacity) et livrables/reperes_voix.csv  (version de calage)
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textlib import (NNBSP, ROOT, find_sentence, narration_sentences, norm_ws, spoken_words, syllables, tokens, typo)

DATA = ROOT / 'src' / 'data'
OUT = ROOT / 'livrables'
FPS = 30

MAX_LINE = 42
MAX_CPS = 17.0
MIN_DUR = 1.0
MAX_DUR = 7.0
SUB_TAIL = 1.2  # un sous-titre peut rester jusqu'à 1,2 s après la fin du dernier mot (sans chevaucher le suivant)
SUB_GAP = 2 / FPS  # deux images entre deux sous-titres
SUB_LEAD = 0.25  # entrée anticipée maximale d'un sous-titre, si le débit l'exige


def r3(x):
    return round(x + 1e-9, 3)


def build_pause_table(sents, P):
    after = {}
    for rule in P['apres']:
        s = find_sentence(sents, rule['phrase'])
        after[s['id']] = rule
    return after


def default_gap(prev, cur, P):
    if cur['chapter'] != prev['chapter']:
        return P['entre_paragraphes'] + P['avant_chapitre']
    if cur['paragraph'] != prev['paragraph']:
        return P['entre_paragraphes']
    return P['entre_phrases']


def required_gap(prev, cur, P, after):
    g = default_gap(prev, cur, P)
    if prev['id'] in after:
        base = after[prev['id']]['s']
        g = base + (P['avant_chapitre'] if cur['chapter'] != prev['chapter'] else 0)
        g = max(g, default_gap(prev, cur, P) if cur['chapter'] == prev['chapter'] else g)
    return g


def calage_timing(sents, P, after):
    """Version de calage : 150 mots/min, puis silences de ponctuation et entre phrases."""
    spw = 60.0 / P['debit_mots_par_minute']
    # Débit moyen de 150 mots/min sur tout le texte (hors silences) ; chaque mot dure selon ses syllabes,
    # ce qui allonge naturellement les phrases aux mots longs.
    all_w = [tok['w'] for s in sents for tok in tokens(s['text']) if tok['w']]
    unit = sum(spoken_words(w) for w in all_w) * spw / sum(0.6 + syllables(w) for w in all_w)
    t = P['intro']
    for i, s in enumerate(sents):
        if i > 0:
            t += required_gap(sents[i - 1], s, P, after)
        toks = tokens(s['text'])
        wtoks = [tok for tok in toks if tok['w']]
        # durée de parole de la phrase : débit fixe en mots ; à l'intérieur, chaque mot pèse selon ses syllabes
        weights = [0.6 + syllables(tok['w']) for tok in wtoks]
        wsum = sum(weights)
        total = wsum * unit
        words = []
        cur = t
        for k, tok in enumerate(toks):
            if tok['w']:
                dur = total * weights[len(words)] / wsum
                words.append({'w': tok['w'], 'start': cur, 'end': cur + dur})
                cur += dur
            if k == len(toks) - 1 or not words:
                continue
            # pause de ponctuation entre deux jetons (la plus longue si plusieurs signes)
            txt = tok['t']
            pause = 0.0
            if '…' in txt:
                pause = max(pause, P['points_de_suspension'])
            if txt.endswith(':') or txt == ':':
                pause = max(pause, P['deux_points'])
            if txt.endswith(';'):
                pause = max(pause, P['point_virgule'])
            if txt.endswith(','):
                pause = max(pause, P['virgule'])
            if re.search(r'[.?!]$', txt):
                pause = max(pause, P['entre_phrases'] * 0.6)
            cur += pause
        end = words[-1]['end']
        s['start'] = r3(t)
        s['end'] = r3(end)
        s['words'] = [{'w': w['w'], 'start': r3(w['start']), 'end': r3(w['end'])} for w in words]
        t = end
    return sents


def voice_timing(sents, align):
    """Avec la voix : reprend les temps produits par tools/align_voice.py (déjà placés dans la timeline du film)."""
    by = {a['id']: a for a in align['sentences']}
    for s in sents:
        a = by[s['id']]
        if norm_ws(a['text']) != norm_ws(s['text']):
            raise SystemExit(f'Alignement périmé pour {s["id"]} : relancer tools/align_voice.py')
        s['start'], s['end'], s['words'] = a['start'], a['end'], a['words']
    return sents


# ---------------------------------------------------------------- sous-titres

FUNCTION_WORDS = set('''le la les l’ un une des du de d’ au aux à ce cet cette ces sa son ses mon ma mes ton ta tes leur leurs notre nos
votre vos en ne n’ qu’ que qui se s’ y il elle on tu je j’ nous vous ils elles lui et ou mais par pour sur dans avec sans chez très plus
aussi est a quand si comme'''.split())


def break_cost(tok_text, next_text, sentence_end):
    """Coût d'une coupure de sous-titre après ce jeton."""
    if sentence_end:
        return 0.0
    last = tok_text[-1]
    if last in ',;:…' or tok_text.endswith('»,') or tok_text == '»':
        return 2.0
    nxt = (next_text or '').lower()
    if nxt in ('et', 'mais', 'ou', 'qui', 'que', 'quand', 'pour', 'si', 'parce', 'comme', 'alors', 'puis', 'où'):
        return 5.0
    if tok_text.lower() in FUNCTION_WORDS or tok_text.endswith('’'):
        return 40.0
    if next_text in ('?', '!', ':', ';', '»'):
        return 60.0
    return 10.0


def line_break(text):
    """Coupe un texte en 1 ou 2 lignes de 42 caractères au plus. Retourne None si impossible."""
    if len(text) <= MAX_LINE:
        return [text]
    best = None
    words = text.split(' ')
    for k in range(1, len(words)):
        a = ' '.join(words[:k])
        b = ' '.join(words[k:])
        if len(a) > MAX_LINE or len(b) > MAX_LINE:
            continue
        cost = abs(len(a) - len(b)) * 0.25
        la = words[k - 1]
        if la[-1] in '.?!':
            cost -= 14
        elif la[-1] in ',;:…' or la.endswith('»'):
            cost -= 6
        if la.lower() in FUNCTION_WORDS or la.endswith('’'):
            cost += 25
        if len(a) > len(b):
            cost += 1.5  # légère préférence pour une pyramide (ligne du bas plus longue)
        if best is None or cost < best[0]:
            best = (cost, [a, b])
    return best[1] if best else None


def make_subtitles(sents, P):
    """Programmation dynamique par paragraphe : coupures aux ponctuations, 2 × 42 caractères, 17 car./s, 1 à 7 s."""
    # jetons d'affichage avec temps
    paras = {}
    for s in sents:
        toks = tokens(s['text'])
        wi = 0
        items = []
        for k, tok in enumerate(toks):
            if tok['w']:
                w = s['words'][wi]
                wi += 1
                items.append({'t': tok['t'], 'start': w['start'], 'end': w['end'], 'sid': s['id']})
            else:  # ponctuation isolée (« » : ? …) : rattachée au mot voisin
                if items and tok['t'] != '«':
                    items[-1] = {**items[-1], 't': items[-1]['t'] + ' ' + tok['t'], 'end': items[-1]['end']}
                else:
                    items.append({'t': tok['t'], 'start': None, 'end': None, 'sid': s['id'], 'lead': True})
            if k == len(toks) - 1:
                items[-1]['sentence_end'] = True
        # fusionner les « ouvrants avec le mot suivant
        merged = []
        carry = None
        for it in items:
            if it.get('lead'):
                carry = it['t'] if carry is None else carry + ' ' + it['t']
                continue
            if carry:
                it = {**it, 't': carry + ' ' + it['t']}
                carry = None
            merged.append(it)
        paras.setdefault((s['chapter'], s['paragraph']), []).extend(merged)

    keys = sorted(paras.keys(), key=lambda k: k[1])
    events = []
    para_starts = [paras[k][0]['start'] for k in keys]
    for pi, key in enumerate(keys):
        items = paras[key]
        n = len(items)
        next_para_start = para_starts[pi + 1] if pi + 1 < len(keys) else items[-1]['end'] + 3.0
        INF = float('inf')
        best = [INF] * (n + 1)
        prev = [-1] * (n + 1)
        best[0] = 0.0
        for j in range(1, n + 1):
            for i in range(max(0, j - 30), j):
                if best[i] == INF:
                    continue
                seg = items[i:j]
                text = typo(' '.join(x['t'] for x in seg))
                lines = line_break(text)
                if lines is None:
                    continue
                start = seg[0]['start']
                speech_end = seg[-1]['end']
                nxt = items[j]['start'] if j < n else next_para_start
                end = min(speech_end + SUB_TAIL, nxt - SUB_GAP)
                end = max(end, speech_end)
                dur = end - start + (SUB_LEAD if i > 0 else 0.0)
                chars = len(text)
                if dur > MAX_DUR + 1e-6:
                    continue
                cps = chars / max(dur, 1e-3)
                cost = break_cost(seg[-1]['t'], items[j]['t'] if j < n else None, seg[-1].get('sentence_end', False)) if j < n else 0.0
                if cps > MAX_CPS:
                    cost += 400 + (cps - MAX_CPS) * 100
                if dur < MIN_DUR:
                    cost += 400 + (MIN_DUR - dur) * 300
                if chars < 18 and j < n:
                    cost += 6
                if len(lines) == 2:
                    cost += 1.0
                # préférer des sous-titres qui ne chevauchent pas deux phrases, sauf phrases très courtes
                if len({x['sid'] for x in seg}) > 1:
                    cost += 3
                c = best[i] + cost + 1.0
                if c < best[j]:
                    best[j] = c
                    prev[j] = i
        if best[n] == INF:
            raise SystemExit(f'Paragraphe impossible à sous-titrer : {key}')
        cuts = []
        j = n
        while j > 0:
            cuts.append((prev[j], j))
            j = prev[j]
        cuts.reverse()
        for (i, j) in cuts:
            seg = items[i:j]
            text = typo(' '.join(x['t'] for x in seg))
            start = seg[0]['start']
            prev_end = events[-1]['end'] if events else 0.0
            nxt = items[j]['start'] if j < n else next_para_start
            end = max(min(seg[-1]['end'] + SUB_TAIL, nxt - SUB_GAP), seg[-1]['end'])
            # durée minimale : prolonger si possible
            if end - start < MIN_DUR:
                end = min(start + MIN_DUR, nxt - SUB_GAP)
            # 17 car./s : prolonger dans le silence si besoin, puis anticiper l'entrée de 0,25 s au plus
            need = len(text) / MAX_CPS
            if end - start < need:
                end = min(start + need, nxt - SUB_GAP)
            if end - start < need:
                start = max(end - need, start - SUB_LEAD, prev_end + SUB_GAP)
            events.append({'start': r3(start), 'end': r3(end), 'speech_end': r3(seg[-1]['end']), 'text': text, 'lines': line_break(text), 'sids': sorted({x['sid'] for x in seg})})
    # rien après le noir final : le dernier sous-titre s'arrête au plus tard au noir
    stop = sents[-1]['end'] + P['silence_final']
    for e in events:
        e['end'] = min(e['end'], stop)
    # snap aux images
    for e in events:
        e['start'] = round(round(e['start'] * FPS) / FPS, 3)
        e['end'] = round(round(e['end'] * FPS) / FPS, 3)
    return events


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def hms(t):
    t = int(t + 1e-6)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f'{h:d}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'


def main():
    P = json.loads((DATA / 'pauses.json').read_text(encoding='utf-8'))
    data, sents = narration_sentences()
    after = build_pause_table(sents, P)
    align_path = DATA / 'voix_alignement.json'
    cfg = json.loads((DATA / 'config.json').read_text(encoding='utf-8'))
    with_voice = bool(cfg.get('voix')) and align_path.exists()
    if with_voice:
        align = json.loads(align_path.read_text(encoding='utf-8'))
        sents = voice_timing(sents, align)
        film_end = align['film_end']
    else:
        sents = calage_timing(sents, P, after)
        film_end = sents[-1]['end'] + P['silence_final'] + P['noir_final']

    # vérification des silences imposés (avec la voix comme en calage)
    pauses_report = []
    for i in range(1, len(sents)):
        a, b = sents[i - 1], sents[i]
        if a['id'] in after:
            gap = b['start'] - a['end']
            pauses_report.append({'apres': a['id'], 'texte': a['text'], 'silence': r3(gap), 'minimum': after[a['id']]['s'], 'ok': gap + 1e-3 >= after[a['id']]['s'], 'raison': after[a['id']]['raison']})

    # chapitres : la carte de chapitre précède la première phrase du chapitre
    chapters = []
    for c in data['chapters']:
        first = next(s for s in sents if s['chapter'] == c['index'])
        t = 0.0 if c['index'] == 0 else first['start'] - P['avant_chapitre']
        chapters.append({'index': c['index'], 'title': c['title'], 'script_label': c['script_label'], 'start': r3(t), 'first_sentence': first['id']})

    cues = {
        'fps': FPS,
        'mode': 'voix' if with_voice else 'calage',
        'film_end': r3(film_end),
        'last_word_end': sents[-1]['end'],
        'silence_final': P['silence_final'],
        'sentences': [{k: s[k] for k in ('id', 'text', 'chapter', 'paragraph', 'start', 'end', 'words')} for s in sents],
        'pauses_imposees': pauses_report,
    }
    (DATA / 'cues.json').write_text(json.dumps(cues, ensure_ascii=False, indent=1), encoding='utf-8')
    (DATA / 'chapters.json').write_text(json.dumps(chapters, ensure_ascii=False, indent=1), encoding='utf-8')
    (DATA / 'credits.json').write_text(json.dumps(data['credits'], ensure_ascii=False, indent=1), encoding='utf-8')

    subs = make_subtitles(sents, P)
    (DATA / 'subs.json').write_text(json.dumps(subs, ensure_ascii=False, indent=1), encoding='utf-8')
    OUT.mkdir(exist_ok=True)
    with open(OUT / 'CulturePsy_Mechants_YouTube.srt', 'w', encoding='utf-8', newline='\n') as f:
        for k, e in enumerate(subs, 1):
            f.write(f"{k}\n{srt_time(e['start'])} --> {srt_time(e['end'])}\n" + '\n'.join(e['lines']) + '\n\n')

    # chapitres YouTube
    ch_lines = [f"{hms(c['start'])} {typo(c['title'])}" for c in chapters]
    (OUT / 'chapitres_youtube.txt').write_text('\n'.join(ch_lines) + '\n', encoding='utf-8')

    # description YouTube : chapitres + références (sans crochets)
    refs = data['refs']
    desc = [
        typo('Pourquoi défend-on les méchants ?'),
        '',
        'Spoilers • L’Attaque des Titans, Breaking Bad et Star Wars',
        '',
        'Chapitres',
        *ch_lines,
        '',
        'Références',
        *[r for r in refs],
        '',
    ]
    (OUT / 'description_youtube.txt').write_text('\n'.join(desc), encoding='utf-8')

    # repères de remplacement audio (version de calage)
    for old in ('reperes_voix.txt', 'reperes_voix.csv'):
        (OUT / old).unlink(missing_ok=True)
    if not with_voice:
        with open(OUT / 'reperes_voix.txt', 'w', encoding='utf-8', newline='\n') as f:
            for s in sents:
                f.write(f"{s['start']:.6f}\t{s['end']:.6f}\t{s['id']} · {s['text']}\n")
        with open(OUT / 'reperes_voix.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(['id', 'debut_s', 'fin_s', 'debut', 'fin', 'chapitre', 'silence_min_apres_s', 'raison_du_silence', 'phrase'])
            for s in sents:
                rule = after.get(s['id'])
                w.writerow([s['id'], f"{s['start']:.3f}", f"{s['end']:.3f}", srt_time(s['start']), srt_time(s['end']), chapters[s['chapter']]['title'],
                            f"{rule['s']:.2f}" if rule else '', rule['raison'] if rule else '', s['text']])

    print(f"mode {cues['mode']} · {len(sents)} phrases · {len(subs)} sous-titres · fin du film {hms(film_end)} ({film_end:.2f} s)")
    for c in chapters:
        print(f"  {hms(c['start'])}  {c['title']}")
    bad = [p for p in pauses_report if not p['ok']]
    print(f"silences imposés : {len(pauses_report) - len(bad)}/{len(pauses_report)} respectés")
    for p in bad:
        print('  MANQUE', p)


if __name__ == '__main__':
    main()
