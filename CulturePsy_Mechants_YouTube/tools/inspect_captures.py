"""Inspection des captures (à lancer dès que les MP4 sont dans public/rushes/) :

    python3 tools/inspect_captures.py            # mesure tout et met à jour src/data/sources.json
    python3 tools/inspect_captures.py --planches # + planches contact (1 image / 0,5 s, numéros d'image) dans controle/captures/

Pour chaque capture : dimensions, nombre d'images, fréquence ; zone active (cropdetect) ; coupes d'origine (détection de
changement de plan) ; images où un sous-titre incrusté occupe la bande basse (≈84–96 % de la hauteur) ; proxys tout-intra.
Les plages propres définitives restent validées à l'œil sur les planches (champ "plages_propres" de sources.json).
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
RUSHES = ROOT / 'public' / 'rushes'
PROXIES = ROOT / 'public' / 'proxies'
CTRL = ROOT / 'controle' / 'captures'


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(f):
    r = run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries',
             'stream=width,height,r_frame_rate,nb_read_packets,pix_fmt,color_space', '-of', 'json', str(f)])
    s = json.loads(r.stdout)['streams'][0]
    num, den = map(int, s['r_frame_rate'].split('/'))
    return {'w': s['width'], 'h': s['height'], 'fps': num / den, 'frames': int(s['nb_read_packets'])}


def cropdetect(f):
    r = run(['ffmpeg', '-v', 'info', '-i', str(f), '-vf', 'cropdetect=limit=24:round=2:reset=0', '-f', 'null', '-'])
    crops = re.findall(r'crop=(\d+):(\d+):(\d+):(\d+)', r.stderr)
    if not crops:
        return None
    w, h, x, y = map(int, crops[-1])
    return [x, y, w, h]


def scene_cuts(f, thr=0.32):
    r = run(['ffmpeg', '-v', 'info', '-i', str(f), '-vf', f"select='gt(scene,{thr})',showinfo", '-f', 'null', '-'])
    return [int(n) for n in re.findall(r'n:\s*(\d+)\s+pts', r.stderr)]


def frames_gray(f, w, h, step=3):
    """Lit la vidéo en niveaux de gris réduits (une image sur `step`)."""
    sw, sh = 320, int(round(320 * h / w / 2) * 2)
    cmd = ['ffmpeg', '-v', 'error', '-i', str(f), '-vf', f"select='not(mod(n\\,{step}))',scale={sw}:{sh}", '-vsync', '0', '-f', 'rawvideo', '-pix_fmt', 'gray', '-']
    raw = subprocess.run(cmd, capture_output=True).stdout
    arr = np.frombuffer(raw, np.uint8)
    n = arr.size // (sw * sh)
    return arr[: n * sw * sh].reshape(n, sh, sw), step


def subtitle_frames(f, w, h):
    """Heuristique : texte clair fortement contrasté dans la bande 84–96 % (sous-titres incrustés)."""
    g, step = frames_gray(f, w, h)
    hh = g.shape[1]
    band = g[:, int(hh * 0.84): int(hh * 0.96), :].astype(np.int16)
    bright = (band > 215).mean(axis=(1, 2))
    edges = np.abs(np.diff(band, axis=2)).mean(axis=(1, 2))
    flag = (bright > 0.006) & (edges > 9)
    ranges, start = [], None
    for i, v in enumerate(flag):
        if v and start is None:
            start = i
        if not v and start is not None:
            ranges.append([start * step, i * step - 1])
            start = None
    if start is not None:
        ranges.append([start * step, len(flag) * step - 1])
    return ranges


def contact_sheets(f, key, info, every=15):
    CTRL.mkdir(parents=True, exist_ok=True)
    tw = 384
    th = int(tw * info['h'] / info['w'])
    tmp = CTRL / f'_{key}'
    tmp.mkdir(exist_ok=True)
    run(['ffmpeg', '-v', 'error', '-y', '-i', str(f), '-vf', f"select='not(mod(n\\,{every}))',scale={tw}:{th}", '-vsync', '0', str(tmp / '%05d.png')])
    files = sorted(tmp.glob('*.png'))
    cols, rows = 5, 6
    for p0 in range(0, len(files), cols * rows):
        sheet = Image.new('RGB', (cols * tw, rows * (th + 22)), (20, 20, 20))
        d = ImageDraw.Draw(sheet)
        for k, fp in enumerate(files[p0: p0 + cols * rows]):
            n = (int(fp.stem) - 1) * every
            x, y = (k % cols) * tw, (k // cols) * (th + 22)
            sheet.paste(Image.open(fp), (x, y + 22))
            d.text((x + 4, y + 4), f'i{n}  {n // 30 // 60:02d}:{n / 30 % 60:05.2f}', fill=(255, 255, 255))
        sheet.save(CTRL / f'{key}_{p0 // (cols * rows) + 1:02d}.png')
    for fp in files:
        fp.unlink()
    tmp.rmdir()


def make_proxy(f):
    PROXIES.mkdir(parents=True, exist_ok=True)
    out = PROXIES / f.name
    if out.exists() and out.stat().st_mtime > f.stat().st_mtime:
        return
    run(['ffmpeg', '-v', 'error', '-y', '-i', str(f), '-map', '0:v:0', '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-g', '1',
         '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-an', str(out)])


def main():
    sheets = '--planches' in sys.argv
    sp = DATA / 'sources.json'
    S = json.loads(sp.read_text(encoding='utf-8'))
    for key, c in S['captures'].items():
        f = RUSHES / c['file']
        if not f.exists():
            c['present'] = False
            print(f'{key} {c["file"]} : ABSENTE')
            continue
        info = probe(f)
        if (info['w'], info['h']) != (c['w'], c['h']):
            print(f'  ! {key} : dimensions {info["w"]}×{info["h"]} au lieu de {c["w"]}×{c["h"]} (mises à jour)')
        c.update({'present': True, 'w': info['w'], 'h': info['h'], 'fps': round(info['fps'], 3), 'frames': info['frames']})
        act = cropdetect(f) or [0, 0, info['w'], info['h']]
        c['active'] = act
        c['coupes'] = scene_cuts(f)
        if c.get('bande_sous_titres'):
            c['sous_titres_detectes'] = subtitle_frames(f, info['w'], info['h'])
        make_proxy(f)
        if sheets:
            contact_sheets(f, key, info)
        print(f"{key} {c['file']} : {info['w']}×{info['h']} · {info['fps']:.3f} i/s · {info['frames']} images · zone active {act} · "
              f"{len(c['coupes'])} coupes · sous-titres détectés : {len(c.get('sous_titres_detectes', []))} plages")
    sp.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
