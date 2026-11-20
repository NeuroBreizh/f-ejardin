"""Pose la voix : alignement forcé mot à mot, coupes sur respiration, placement dans la timeline du film.

    python3 tools/align_voice.py            (lit "voix" dans src/data/config.json, ex. "audio/voix.wav")

1. Alignement forcé du script v3 (texte hors crochets) sur l'enregistrement, en français, avec stable-ts
   (pip install stable-ts ; modèle « medium » par défaut, variable WHISPER_MODEL pour en changer).
   Si stable-ts manque, WhisperX est essayé (pip install whisperx).
2. Silences détectés avec ffmpeg silencedetect (−38 dB, au moins 120 ms).
3. La voix n'est coupée qu'aux endroits où le montage impose un silence plus long que la respiration naturelle
   (src/data/pauses.json : temps de réponse, test, « Qui a levé la main ? », cartes de chapitre…). Chaque coupe
   tombe au milieu d'une respiration détectée, jamais dans un mot.
4. Sorties : src/data/voix_alignement.json (phrases et mots dans le temps du film) et src/data/voix_montage.json
   (segments de voix pour Remotion). Ensuite : python3 tools/build_text.py && python3 tools/resolve_montage.py
"""
import difflib
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textlib import ROOT, find_sentence, narration_sentences, tokens

DATA = ROOT / 'src' / 'data'
PUBLIC = ROOT / 'public'
FPS = 30
SIL_DB = -38
SIL_MIN = 0.12


def norm(w):
    w = unicodedata.normalize('NFD', w.lower().replace("'", '’'))
    w = ''.join(c for c in w if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9’-]', '', w)


def align_stable_ts(wav, text):
    import stable_whisper  # noqa
    model = stable_whisper.load_model(os.environ.get('WHISPER_MODEL', 'medium'))
    res = model.align(str(wav), text, language='fr')
    return [{'w': w.word.strip(), 'start': float(w.start), 'end': float(w.end)} for s in res.segments for w in s.words if w.word.strip()]


def align_whisperx(wav, text):
    import whisperx  # noqa
    device = 'cpu'
    audio = whisperx.load_audio(str(wav))
    dur = len(audio) / 16000
    model, meta = whisperx.load_align_model(language_code='fr', device=device)
    res = whisperx.align([{'text': text, 'start': 0.0, 'end': dur}], model, meta, audio, device)
    return [{'w': w['word'], 'start': w['start'], 'end': w['end']} for w in res['word_segments'] if 'start' in w]


def silences(wav):
    r = subprocess.run(['ffmpeg', '-v', 'info', '-i', str(wav), '-af', f'silencedetect=noise={SIL_DB}dB:d={SIL_MIN}', '-f', 'null', '-'],
                       capture_output=True, text=True)
    st = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', r.stderr)]
    en = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', r.stderr)]
    return list(zip(st, en))


def main():
    config = json.loads((DATA / 'config.json').read_text(encoding='utf-8'))
    if not config.get('voix'):
        raise SystemExit('Indique le fichier de ta voix dans src/data/config.json, champ "voix" (ex. "audio/voix.wav").')
    src = PUBLIC / config['voix']
    wav = PUBLIC / 'audio' / '_voix_48k_mono.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-ac', '1', '-ar', '48000', str(wav)], check=True)
    P = json.loads((DATA / 'pauses.json').read_text(encoding='utf-8'))
    data, sents = narration_sentences()
    text = '\n'.join(p['text'] for p in data['paragraphs'])

    raw_path = DATA / 'voix_mots_bruts.json'
    if raw_path.exists() and raw_path.stat().st_mtime > src.stat().st_mtime:
        aligned = json.loads(raw_path.read_text(encoding='utf-8'))
    else:
        try:
            aligned = align_stable_ts(wav, text)
        except ImportError:
            try:
                aligned = align_whisperx(wav, text)
            except ImportError:
                raise SystemExit('Installe stable-ts (pip install stable-ts) ou WhisperX (pip install whisperx), puis relance.')
        raw_path.write_text(json.dumps(aligned, ensure_ascii=False, indent=0), encoding='utf-8')

    # correspondance mots du script ↔ mots alignés
    script_words = [(s['id'], tok['w']) for s in sents for tok in tokens(s['text']) if tok['w']]
    a = [norm(w) for _, w in script_words]
    b = [norm(x['w']) for x in aligned]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    times = [None] * len(a)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            times[blk.a + k] = (aligned[blk.b + k]['start'], aligned[blk.b + k]['end'])
    missing = sum(t is None for t in times)
    # interpolation des mots non retrouvés
    for i, t in enumerate(times):
        if t is None:
            prev = next((times[j][1] for j in range(i - 1, -1, -1) if times[j]), 0.0)
            nxt = next((times[j][0] for j in range(i + 1, len(times)) if times[j]), prev + 0.4)
            times[i] = (prev, max(prev + 0.05, min(nxt, prev + 0.4)))
    print(f'{len(a)} mots du script · {len(b)} mots alignés · {missing} interpolés')

    k = 0
    for s in sents:
        ws = []
        for tok in tokens(s['text']):
            if tok['w']:
                ws.append({'w': tok['w'], 'start': times[k][0], 'end': times[k][1]})
                k += 1
        s['src_words'] = ws
        s['src_start'], s['src_end'] = ws[0]['start'], ws[-1]['end']

    after = {}
    for rule in P['apres']:
        after[find_sentence(sents, rule['phrase'])['id']] = rule['s']
    sil = silences(wav)

    # coupes et décalages
    shift = P['intro'] - sents[0]['src_start']
    seg_start = max(0.0, sents[0]['src_start'] - 0.25)
    segments, report = [], []
    for i, s in enumerate(sents):
        s['shift'] = shift
        if i + 1 == len(sents):
            break
        n = sents[i + 1]
        natural = n['src_start'] - s['src_end']
        need = after.get(s['id'], 0.0)
        if n['chapter'] != s['chapter']:
            need = max(need, P['entre_paragraphes']) + P['avant_chapitre']
        if need > natural + 0.02:
            gap_sil = [(x, y) for x, y in sil if x < n['src_start'] and y > s['src_end']]
            if gap_sil:
                x, y = max(gap_sil, key=lambda q: min(q[1], n['src_start']) - max(q[0], s['src_end']))
                cut = (max(x, s['src_end']) + min(y, n['src_start'])) / 2
                ok = True
            else:
                cut = (s['src_end'] + n['src_start']) / 2
                ok = natural >= 0.06
            segments.append({'src_in': seg_start, 'src_out': cut, 'shift': shift})
            shift += need - natural
            seg_start = cut
            report.append(f"{s['id']} → {n['id']} : silence porté de {natural:.2f} à {need:.2f} s" + ('' if ok else ' — ATTENTION : pas de respiration détectée'))
    last = sents[-1]
    seg_end = last['src_end'] + 0.35
    segments.append({'src_in': seg_start, 'src_out': seg_end, 'shift': shift})

    out_s = []
    for s in sents:
        sh = s['shift']
        out_s.append({'id': s['id'], 'text': s['text'], 'start': round(s['src_start'] + sh, 3), 'end': round(s['src_end'] + sh, 3),
                      'words': [{'w': w['w'], 'start': round(w['start'] + sh, 3), 'end': round(w['end'] + sh, 3)} for w in s['src_words']]})
    film_end = out_s[-1]['end'] + P['silence_final'] + P['noir_final']
    (DATA / 'voix_alignement.json').write_text(json.dumps({'sentences': out_s, 'film_end': round(film_end, 3)}, ensure_ascii=False, indent=1), encoding='utf-8')
    segs = [{'src': config['voix'], 'from': int(round((g['src_in'] + g['shift']) * FPS)), 'trimBefore': int(round(g['src_in'] * FPS)),
             'trimAfter': int(round(g['src_out'] * FPS)), 'volume': config.get('voixVolume', 1.0)} for g in segments]
    (DATA / 'voix_montage.json').write_text(json.dumps({'segments': segs}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(segs)} segments de voix · fin du film {film_end:.2f} s')
    for r in report:
        print('  ', r)


if __name__ == '__main__':
    main()
