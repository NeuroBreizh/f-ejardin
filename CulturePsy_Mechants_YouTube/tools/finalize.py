"""Finalise le MP4 rendu par Remotion : niveau sonore et conteneur.

    python3 tools/finalize.py livrables/<nom>_brut.mp4

- Avec la voix : normalisation en deux passes à −14 LUFS intégrés, crête vraie ≤ −1 dBTP (ffmpeg loudnorm, linéaire si possible).
- Version de calage (pas de voix) : le niveau n'est pas remonté (seuls de brefs accents existent) ; la crête est plafonnée à −1 dBTP.
- Audio AAC 48 kHz ; vidéo copiée telle quelle (H.264 High, yuv420p, bt709) ; « +faststart ».
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def measure(f):
    r = subprocess.run(['ffmpeg', '-v', 'info', '-i', str(f), '-map', '0:a:0', '-af', 'loudnorm=I=-14:TP=-1:LRA=11:print_format=json', '-f', 'null', '-'],
                       capture_output=True, text=True)
    m = re.search(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr, re.S)
    return json.loads(m.group(0)) if m else None


def main():
    src = Path(sys.argv[1])
    out = src.with_name(src.name.replace('_brut', '')) if '_brut' in src.name else src.with_name(src.stem + '_final.mp4')
    cues = json.loads((ROOT / 'src' / 'data' / 'cues.json').read_text(encoding='utf-8'))
    m = measure(src)
    if cues['mode'] == 'voix' and m:
        af = (f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
              f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true:print_format=summary,aresample=48000")
    else:
        af = 'alimiter=limit=0.89:level=false,aresample=48000'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-map', '0:v:0', '-map', '0:a:0', '-c:v', 'copy', '-af', af,
                    '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-movflags', '+faststart', str(out)], check=True)
    print(out)


if __name__ == '__main__':
    main()
