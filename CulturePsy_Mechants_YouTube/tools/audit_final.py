"""Audits §7.2, 7.4, 7.5, 7.6 et 7.7 sur le film rendu.

    python3 tools/audit_final.py livrables/<film>.mp4 [--planches]

- 7.7 Fichier : H.264 High, yuv420p, bt709, 1920 × 1080, 30 i/s, AAC 48 kHz, +faststart ; couleurs d'une image du rendu
       comparées à un renderStill de la même image (controle/couleurs/).
- 7.6 Son : LUFS intégrés et crête vraie ; explosion brève ; fin : œil, une seconde de silence, noir.
- 7.5 Lecture : durée et corps de chaque texte à l'écran ; temps de réponse avant « oui, oui, non » ;
       silence après « Qui a levé la main ? » ; passage Gretchen conforme aux fichiers présents.
- 7.2 / 7.4 (--planches) : pour chaque plan, première / médiane / dernière image dans le recadrage réel (controle/plans/),
       et paires d'images avant / après chaque coupe (controle/coupes/).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'src' / 'data'
CTRL = ROOT / 'controle'
FPS = 30
fails, notes = [], []


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def frame_at(mp4, n, w=1920, h=1080):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-vf', f"select='eq(n\\,{n})'", '-vsync', '0', '-frames:v', '1',
                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(h, w, 3)


def check_file(mp4):
    r = json.loads(sh(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(mp4)]).stdout)
    v = next(s for s in r['streams'] if s['codec_type'] == 'video')
    a = next((s for s in r['streams'] if s['codec_type'] == 'audio'), None)
    exp = {'codec_name': 'h264', 'profile': 'High', 'pix_fmt': 'yuv420p', 'width': 1920, 'height': 1080, 'color_space': 'bt709',
           'color_transfer': 'bt709', 'color_primaries': 'bt709', 'r_frame_rate': '30/1'}
    for k, e in exp.items():
        got = v.get(k)
        ok = got == e
        print(f"[fichier] {k} = {got} {'✓' if ok else '✗ attendu ' + str(e)}")
        if not ok:
            fails.append(f'fichier : {k} = {got}')
    if not a or a['codec_name'] != 'aac' or a['sample_rate'] != '48000':
        fails.append(f"fichier : audio {a and a['codec_name']} {a and a['sample_rate']}")
    print(f"[fichier] audio = {a and a['codec_name']} {a and a['sample_rate']} Hz {a and a.get('channels')} canaux")
    # +faststart : l'atome moov précède mdat
    with open(mp4, 'rb') as f:
        head = f.read(1 << 20)
    moov, mdat = head.find(b'moov'), head.find(b'mdat')
    fs = moov != -1 and (mdat == -1 or moov < mdat)
    print(f"[fichier] +faststart : {'✓' if fs else '✗'}")
    if not fs:
        fails.append('fichier : moov après mdat (+faststart absent)')
    return float(r['format']['duration'])


def check_colors(mp4, frame):
    out = CTRL / 'couleurs'
    out.mkdir(parents=True, exist_ok=True)
    r = sh(['node', 'tools/stills.mjs', str(out), str(frame)])
    still = np.asarray(Image.open(out / f'f{frame:05d}.png').convert('RGB')).astype(np.int16)
    vid = frame_at(mp4, frame).astype(np.int16)
    Image.fromarray(vid.astype(np.uint8)).save(out / f'rendu_{frame:05d}.png')
    d = np.abs(still - vid).mean(axis=(0, 1))
    mean = still.mean(axis=(0, 1)) - vid.mean(axis=(0, 1))
    print(f"[couleurs] image {frame} : écart moyen R {d[0]:.2f} V {d[1]:.2f} B {d[2]:.2f} · décalage moyen {mean.round(2).tolist()}")
    if abs(mean).max() > 3:
        fails.append(f'couleurs : décalage moyen {mean.round(2).tolist()} entre renderStill et le MP4')


def check_audio(mp4):
    r = sh(['ffmpeg', '-v', 'info', '-i', str(mp4), '-map', '0:a:0', '-af', 'ebur128=peak=true', '-f', 'null', '-'])
    I = re.findall(r'I:\s+(-?[\d.]+) LUFS', r.stderr)
    TP = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', r.stderr)
    I = float(I[-1]) if I else None
    TP = float(TP[-1]) if TP else None
    cues = json.loads((DATA / 'cues.json').read_text(encoding='utf-8'))
    print(f"[son] intégré {I} LUFS · crête vraie {TP} dBTP")
    if cues['mode'] == 'voix' and (I is None or abs(I + 14) > 0.5):
        fails.append(f'son : {I} LUFS (cible −14)')
    if TP is not None and TP > -1.0:
        fails.append(f'son : crête vraie {TP} dBTP (> −1)')
    if cues['mode'] == 'calage':
        notes.append('version de calage : pas de voix, le niveau intégré ne porte que sur les accents ; la cible −14 LUFS s’applique au master')


def check_reading(resolved, cues):
    ons = json.loads((DATA / 'onscreen.json').read_text(encoding='utf-8'))
    short = []
    for t in ons:
        dur = (t['to'] - t['from']) / FPS
        need = max(1.5, len(t['text']) / 15 + 0.6)
        if t['kind'] in ('planche',):
            continue
        if dur < need:
            short.append(f"« {t['text'][:50]} » {dur:.1f} s < {need:.1f} s")
        if t['kind'] in ('mot', 'question', 'spectateur') and t.get('size') and t['size'] < 54:
            short.append(f"« {t['text'][:50]} » corps {t['size']} px < 54")
    print(f"[lecture] {len(ons)} textes à l'écran · {len(ons) - len(short)} conformes (durée ≥ 15 car./s + 0,6 s, corps ≥ 54 px)")
    for s in short:
        fails.append('lecture : ' + s)
    S = {s['id']: s for s in cues['sentences']}
    byt = {s['text']: s for s in cues['sentences']}
    q = next(s for s in cues['sentences'] if s['text'] == 'Qui a levé la main ?')
    nxt = cues['sentences'][cues['sentences'].index(q) + 1]
    gap = nxt['start'] - q['end']
    print(f"[lecture] silence après « Qui a levé la main ? » : {gap:.2f} s")
    if gap < 1.0:
        fails.append('lecture : moins d’une seconde de silence après « Qui a levé la main ? »')
    q3 = next(s for s in cues['sentences'] if s['text'].startswith('Est-ce que tu aurais trouvé sa conduite'))
    o = cues['sentences'][cues['sentences'].index(q3) + 1]
    print(f"[lecture] temps de réponse avant « oui, oui, non » : {o['start'] - q3['end']:.2f} s")
    if o['start'] - q3['end'] < 2.0:
        fails.append('lecture : temps de réponse trop court avant « oui, oui, non »')
    gretchen = (ROOT / 'public' / 'rushes' / 'Gretchen.mp4').exists()
    print(f"[lecture] Gretchen : {'capture présente' if gretchen else 'pas de capture → résumé barré sur fond anthracite (§2)'}")


def check_end(mp4, resolved, cues):
    last = cues['last_word_end']
    plans = resolved['plans']
    eye = next(p for p in plans if p['id'] == 'G06')
    black = next(p for p in plans if p['type'] == 'noir')
    lw = int(round(last * FPS))
    print(f"[fin] œil d’Eren : {eye['from'] / FPS:.2f} → {eye['to'] / FPS:.2f} s · dernier mot fini à {last:.2f} s · noir à {black['from'] / FPS:.2f} s")
    if not (eye['from'] < lw < eye['to']):
        fails.append('fin : le dernier mot n’est pas sur l’œil')
    if abs((black['from'] - lw) / FPS - 1.0) > 0.05:
        fails.append(f"fin : silence sur l’œil de {(black['from'] - lw) / FPS:.2f} s (attendu 1,0 s)")
    boom = [s for s in resolved['audio']['sfx'] if 'boom' in s['src']]
    for b in boom:
        print(f"[son] explosion : {b['dur'] / FPS:.2f} s")
        if b['dur'] / FPS > 1.5:
            fails.append('son : explosion trop longue')


def sheets(mp4, resolved):
    U = json.loads((DATA / 'usages.json').read_text(encoding='utf-8'))
    out = CTRL / 'plans'
    out.mkdir(parents=True, exist_ok=True)
    tw, th = 480, 270
    for k, u in enumerate(sorted(U, key=lambda u: u['from']), 1):
        fr = [u['from'], (u['from'] + u['to']) // 2, u['to'] - 1]
        S = Image.new('RGB', (tw * 3, th + 26), (18, 18, 18))
        d = ImageDraw.Draw(S)
        for j, n in enumerate(fr):
            S.paste(Image.fromarray(frame_at(mp4, n)).resize((tw, th)), (j * tw, 26))
        d.text((6, 6), f"{k:03d} {u['plan']} · {u['file']} · i{u['in']}–{u['last']} · {u['note']}"[:180], fill=(255, 255, 255))
        S.save(out / f"{k:03d}_{u['plan']}.png")
    out = CTRL / 'coupes'
    out.mkdir(parents=True, exist_ok=True)
    for p in resolved['plans'][1:]:
        a, b = p['from'] - 1, p['from']
        S = Image.new('RGB', (tw * 2 + 8, th), (228, 73, 83))
        S.paste(Image.fromarray(frame_at(mp4, a)).resize((tw, th)), (0, 0))
        S.paste(Image.fromarray(frame_at(mp4, b)).resize((tw, th)), (tw + 8, 0))
        S.save(out / f"{b:05d}_{p['id']}.png")
    print(f'[planches] {len(U)} planches de plans dans controle/plans · {len(resolved["plans"]) - 1} paires de coupe dans controle/coupes')


def main():
    mp4 = Path(sys.argv[1])
    resolved = json.loads((DATA / 'resolved.json').read_text(encoding='utf-8'))
    cues = json.loads((DATA / 'cues.json').read_text(encoding='utf-8'))
    dur = check_file(mp4)
    print(f"[fichier] durée {dur:.2f} s (attendu {resolved['durationInFrames'] / FPS:.2f} s)")
    check_colors(mp4, int(resolved['durationInFrames'] * 0.37))
    check_audio(mp4)
    check_reading(resolved, cues)
    check_end(mp4, resolved, cues)
    if '--planches' in sys.argv:
        sheets(mp4, resolved)
    for n in notes:
        print('  note :', n)
    for f in fails:
        print('  ÉCHEC :', f)
    print('AUDIT FINAL :', 'OK' if not fails else f'ÉCHEC ({len(fails)})')
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
