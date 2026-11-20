// Rendu du film.
//   node tools/render.mjs                      film entier → livrables/…_brut.mp4, puis python3 tools/finalize.py
//   node tools/render.mjs --frames=0-1440      rendu d'essai (images 0 à 1440) → controle/essais/
//   node tools/render.mjs --chapitre=3         rendu d'essai d'un chapitre (1 = premier)
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import fs from 'fs';
import os from 'os';
import path from 'path';

const args = Object.fromEntries(process.argv.slice(2).map((a) => a.replace(/^--/, '').split('=')));
const resolved = JSON.parse(fs.readFileSync('src/data/resolved.json', 'utf8'));
const chapters = JSON.parse(fs.readFileSync('src/data/chapters.json', 'utf8'));
const browserExecutable = process.env.REMOTION_CHROME || '/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell';

let frameRange = null;
let out;
if (args.frames) {
  const [a, b] = args.frames.split('-').map(Number);
  frameRange = [a, b];
  out = `controle/essais/essai_${a}-${b}.mp4`;
} else if (args.chapitre) {
  const i = Number(args.chapitre) - 1;
  const a = Math.round(chapters[i].start * 30);
  const b = i + 1 < chapters.length ? Math.round(chapters[i + 1].start * 30) - 1 : resolved.durationInFrames - 1;
  frameRange = [a, b];
  out = `controle/essais/chapitre_${i + 1}.mp4`;
} else {
  // Tant qu'une capture manque (mire de calage), le fichier porte le suffixe _MIRES : ce n'est pas un livrable.
  const name = (resolved.calage ? 'CulturePsy_Mechants_YouTube_VERSION_DE_CALAGE' : 'CulturePsy_Mechants_YouTube_master') + (resolved.mires ? '_MIRES' : '');
  out = `livrables/${name}_brut.mp4`;
}
fs.mkdirSync(path.dirname(out), {recursive: true});

const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts'), publicDir: path.resolve('public')});
const composition = await selectComposition({serveUrl, id: 'CulturePsyMechantsYouTube', browserExecutable});
let last = -1;
await renderMedia({
  composition,
  serveUrl,
  codec: 'h264',
  outputLocation: out,
  frameRange,
  crf: 17,
  pixelFormat: 'yuv420p',
  colorSpace: 'bt709',
  imageFormat: 'jpeg',
  jpegQuality: 92,
  audioCodec: 'aac',
  enforceAudioTrack: true,
  audioBitrate: '320k',
  browserExecutable,
  chromiumOptions: {gl: 'swangle'},
  concurrency: Math.max(1, Math.min(8, os.cpus().length - 1)),
  offthreadVideoCacheSizeInBytes: 2 * 1024 * 1024 * 1024,
  onProgress: ({progress}) => {
    const p = Math.floor(progress * 100);
    if (p !== last && p % 5 === 0) {
      last = p;
      console.log(`${p} %`);
    }
  },
});
console.log(out);
