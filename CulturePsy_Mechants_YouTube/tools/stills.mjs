// Images de contrôle : node tools/stills.mjs <dossier> <image> [<image> …]   (une image peut s'écrire « s:12.5 » en secondes)
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import path from 'path';
import fs from 'fs';
const [outDir, ...args] = process.argv.slice(2);
const frames = args.map((a) => (a.startsWith('s:') ? Math.round(parseFloat(a.slice(2)) * 30) : Number(a)));
const browserExecutable = process.env.REMOTION_CHROME || '/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell';
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts'), publicDir: path.resolve('public')});
const composition = await selectComposition({serveUrl, id: 'CulturePsyMechantsYouTube', browserExecutable});
fs.mkdirSync(outDir, {recursive: true});
for (const f of frames) {
  const output = path.join(outDir, `f${String(f).padStart(5, '0')}.png`);
  await renderStill({composition, serveUrl, output, frame: f, imageFormat: 'png', browserExecutable, chromiumOptions: {gl: 'swangle'}});
  console.log(output);
}
