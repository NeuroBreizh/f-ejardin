"""Test de la pose de la voix sans aligneur : fabrique un enregistrement synthétique (un bruit par mot, des respirations
entre les phrases) et son alignement mot à mot connu, puis enchaîne align_voice → build_text → resolve_montage → audit_text
dans une copie temporaire du projet. Vérifie : aucune coupe dans un mot, silences imposés respectés, SRT identique au script.

    python3 tools/test_voix_synthetique.py
"""
import json
import random
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def main():
    tmp = Path(tempfile.mkdtemp(prefix='voixtest_'))
    for d in ('tools', 'script', 'src'):
        shutil.copytree(ROOT / d, tmp / d)
    (tmp / 'public' / 'audio').mkdir(parents=True)
    (tmp / 'livrables').mkdir()
    for d in ('sfx', 'visuels'):
        shutil.copytree(ROOT / 'public' / d, tmp / 'public' / d)
    for f in ('voix_alignement.json', 'voix_montage.json', 'voix_mots_bruts.json'):
        (tmp / 'src' / 'data' / f).unlink(missing_ok=True)
    sys.path.insert(0, str(tmp / 'tools'))
    from textlib import narration_sentences, tokens  # noqa

    random.seed(3)
    _, sents = narration_sentences()
    sr, t = 48000, 0.8
    words, chunks = [], [np.zeros(int(sr * 0.8))]
    for i, s in enumerate(sents):
        for tok in [x for x in tokens(s['text']) if x['w']]:
            d = 0.12 + 0.055 * len(tok['w'])
            chunks.append(np.random.default_rng(len(words)).standard_normal(int(sr * d)) * 0.08)
            words.append({'w': ' ' + tok['t'], 'start': round(t, 3), 'end': round(t + d, 3)})
            t += d
            chunks.append(np.zeros(int(sr * 0.03)))
            t += 0.03
        g = random.uniform(0.25, 0.55) if i + 1 < len(sents) and sents[i + 1]['paragraph'] == s['paragraph'] else random.uniform(0.5, 0.9)
        chunks.append(np.zeros(int(sr * g)))
        t += g
    pcm = (np.clip(np.concatenate(chunks), -1, 1) * 32767).astype(np.int16)
    with wave.open(str(tmp / 'public' / 'audio' / 'voix_test.wav'), 'wb') as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(sr), w.writeframes(pcm.tobytes())
    words[5]['w'] = ' paje'  # un mot mal reconnu, comme le ferait un aligneur
    cfg = json.loads((tmp / 'src' / 'data' / 'config.json').read_text(encoding='utf-8'))
    cfg['voix'] = 'audio/voix_test.wav'
    (tmp / 'src' / 'data' / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False), encoding='utf-8')
    (tmp / 'src' / 'data' / 'voix_mots_bruts.json').write_text(json.dumps(words, ensure_ascii=False), encoding='utf-8')

    ok = True
    for step in ('align_voice.py', 'build_text.py', 'resolve_montage.py', 'audit_text.py'):
        r = subprocess.run([sys.executable, '-I', str(tmp / 'tools' / step)], capture_output=True, text=True)
        print(f'--- {step}\n' + '\n'.join(r.stdout.strip().splitlines()[-4:]))
        if r.returncode != 0 or 'MANQUE' in r.stdout or 'ATTENTION' in r.stdout:
            ok = False
            print(r.stderr[-800:])
    segs = json.loads((tmp / 'src' / 'data' / 'voix_montage.json').read_text())['segments']
    inside = sum(1 for g in segs[:-1] for w in words if w['start'] < g['trimAfter'] / 30 < w['end'])
    print(f'{len(segs)} segments de voix · coupes dans un mot : {inside}')
    ok = ok and inside == 0
    shutil.rmtree(tmp)
    print('TEST VOIX :', 'OK' if ok else 'ÉCHEC')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
