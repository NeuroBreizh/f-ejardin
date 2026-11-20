import {staticFile} from 'remotion';

export const W = 1920;
export const H = 1080;
export const ANTHRACITE = '#0B1015';
export const IVORY = '#F8EEDC';
export const RED = '#E44953';
export const ivory = (a: number) => `rgba(248,238,220,${a})`;
export const anthracite = (a: number) => `rgba(11,16,21,${a})`;

// Polices : Inter (titres, étiquettes, crédits) et Newsreader (questions, paroles prêtées au spectateur).
// Les sous-ensembles web n'ont pas l'espace fine insécable U+202F : elle est prise dans Inter OTF (InterCP).
export const SANS = "'InterW', 'InterCP', sans-serif";
export const SERIF = "'NewsreaderW', 'InterCP', serif";

const face = (family: string, file: string, weight: number, style = 'normal') =>
  `@font-face{font-family:'${family}';src:url('${staticFile('fonts/' + file)}');font-weight:${weight};font-style:${style};font-display:block;}`;

export const fontFaces = [
  face('InterCP', 'Inter-SemiBold.otf', 600),
  face('InterCP', 'Inter-Bold.otf', 700),
  face('InterCP', 'Inter-ExtraBold.otf', 800),
  face('InterCP', 'Inter-SemiBold.otf', 400),
  face('InterCP', 'Inter-SemiBold.otf', 400, 'italic'),
  face('InterCP', 'Inter-SemiBold.otf', 500),
  face('InterCP', 'Inter-SemiBold.otf', 500, 'italic'),
  face('InterW', 'inter-latin-400-normal.woff2', 400),
  face('InterW', 'inter-latin-400-italic.woff2', 400, 'italic'),
  face('InterW', 'inter-latin-500-normal.woff2', 500),
  face('InterW', 'inter-latin-500-italic.woff2', 500, 'italic'),
  face('InterW', 'inter-latin-600-normal.woff2', 600),
  face('InterW', 'inter-latin-700-normal.woff2', 700),
  face('InterW', 'Inter-ExtraBold.otf', 800),
  face('NewsreaderW', 'newsreader-latin-400-normal.woff2', 400),
  face('NewsreaderW', 'newsreader-latin-400-italic.woff2', 400, 'italic'),
  face('NewsreaderW', 'newsreader-latin-500-normal.woff2', 500),
  face('NewsreaderW', 'newsreader-latin-500-italic.woff2', 500, 'italic'),
  face('NewsreaderW', 'newsreader-latin-600-normal.woff2', 600),
  face('NewsreaderW', 'newsreader-latin-600-italic.woff2', 600, 'italic'),
].join('\n');

// Typographie française : espace fine insécable avant ? ! : ; et à l'intérieur des « », apostrophe typographique.
export const typo = (t: string) =>
  t
    .replace(/'/g, '’')
    .replace(/[   ]*([?!:;»])/g, ' $1')
    .replace(/«[   ]*/g, '« ')
    .replace(/^ /, '');
