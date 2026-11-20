import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, random, staticFile} from 'remotion';
import {ANTHRACITE, IVORY, RED, SANS, SERIF, anthracite, ivory, typo} from '../lib/theme';
import {BlurBackdrop, ClipLayer, ClipR, Rect} from './Clip';

// ------------------------------------------------------------------ texte

export type Highlight = {mot: string; at: number; color?: string; underline?: boolean};
export type TextR = {
  type: 'texte';
  style: 'question' | 'citation' | 'mot' | 'etiquette' | 'credit' | 'liste' | 'note' | 'grand';
  text: string;
  x: number;
  y: number;
  w: number;
  align?: 'left' | 'center' | 'right';
  anchor?: 'top' | 'center' | 'bottom';
  size?: number;
  color?: string;
  from: number;
  to: number;
  fade?: number;
  fadeOut?: number;
  rise?: number;
  dimAt?: number;
  dimTo?: number;
  strikeAt?: number;
  highlights?: Highlight[];
  box?: boolean; // pavé sombre derrière le texte (lisibilité sur image)
  kind?: string; // pour l'audit des textes à l'écran
};

const STYLES: Record<TextR['style'], React.CSSProperties> = {
  question: {fontFamily: SERIF, fontWeight: 500, fontSize: 68, lineHeight: 1.18, letterSpacing: '-0.005em'},
  citation: {fontFamily: SERIF, fontWeight: 400, fontStyle: 'italic', fontSize: 64, lineHeight: 1.2},
  grand: {fontFamily: SERIF, fontWeight: 500, fontSize: 120, lineHeight: 1.05, letterSpacing: '-0.01em'},
  mot: {fontFamily: SANS, fontWeight: 700, fontSize: 58, lineHeight: 1.15, letterSpacing: '-0.01em'},
  liste: {fontFamily: SANS, fontWeight: 600, fontSize: 54, lineHeight: 1.2},
  etiquette: {fontFamily: SANS, fontWeight: 600, fontSize: 28, letterSpacing: '0.22em', textTransform: 'uppercase', lineHeight: 1.2},
  credit: {fontFamily: SANS, fontWeight: 600, fontSize: 48, lineHeight: 1.2},
  note: {fontFamily: SANS, fontWeight: 500, fontSize: 36, lineHeight: 1.3},
};

const renderWithHighlights = (text: string, hl: Highlight[] | undefined, frame: number) => {
  const t = typo(text);
  if (!hl || hl.length === 0) return t;
  // découpe successive sur chaque mot mis en relief (première occurrence restante)
  type Part = {s: string; h?: Highlight};
  let parts: Part[] = [{s: t}];
  for (const h of hl) {
    const m = typo(h.mot);
    const next: Part[] = [];
    let done = false;
    for (const p of parts) {
      const i = p.h || done ? -1 : p.s.indexOf(m);
      if (i < 0) {
        next.push(p);
        continue;
      }
      next.push({s: p.s.slice(0, i)}, {s: m, h}, {s: p.s.slice(i + m.length)});
      done = true;
    }
    parts = next;
  }
  return parts.map((p, i) => {
    if (!p.h) return <React.Fragment key={i}>{p.s}</React.Fragment>;
    const k = interpolate(frame, [p.h.at, p.h.at + 8], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
    const col = p.h.color ?? RED;
    return (
      <span
        key={i}
        style={{
          color: k > 0.5 ? col : undefined,
          transition: 'none',
          backgroundImage: p.h.underline ? `linear-gradient(${col}, ${col})` : undefined,
          backgroundRepeat: 'no-repeat',
          backgroundPosition: '0 100%',
          backgroundSize: p.h.underline ? `${k * 100}% 5px` : undefined,
          opacity: 1,
        }}
      >
        {p.s}
      </span>
    );
  });
};

export const TextLayer: React.FC<{t: TextR; frame: number}> = ({t, frame}) => {
  if (frame < t.from || frame >= t.to) return null;
  const fi = t.fade ?? 10;
  const fo = t.fadeOut ?? 8;
  const enter = interpolate(frame, [t.from, t.from + fi], [0, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const exit = interpolate(frame, [t.to - fo, t.to], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const dim = t.dimAt !== undefined ? interpolate(frame, [t.dimAt, t.dimAt + 10], [1, t.dimTo ?? 0.32], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1;
  const rise = (1 - enter) * (t.rise ?? 18);
  const strike = t.strikeAt !== undefined ? interpolate(frame, [t.strikeAt, t.strikeAt + 9], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)}) : 0;
  const st = STYLES[t.style];
  const anchorY = t.anchor === 'center' ? '-50%' : t.anchor === 'bottom' ? '-100%' : '0%';
  const isLabel = t.style === 'etiquette';
  const isCredit = t.style === 'credit';
  const content = renderWithHighlights(t.text, t.highlights, frame);
  return (
    <div
      style={{
        position: 'absolute',
        left: t.x,
        top: t.y,
        width: t.w,
        transform: `translate(0, calc(${anchorY} + ${rise}px))`,
        opacity: enter * exit * dim,
        textAlign: t.align ?? 'left',
        textWrap: 'balance' as any,
        color: t.color ?? (isLabel ? ivory(0.78) : IVORY),
        ...st,
        fontSize: t.size ?? st.fontSize,
      }}
    >
      {isCredit || isLabel ? (
        <div style={{display: 'inline-flex', alignItems: 'stretch', gap: isLabel ? 16 : 22}}>
          <div style={{width: isLabel ? 5 : 7, borderRadius: 3, background: RED, flex: 'none'}} />
          <div
            style={{
              padding: t.box ? (isLabel ? '8px 16px' : '10px 20px') : 0,
              background: t.box ? anthracite(0.62) : undefined,
              borderRadius: 6,
              textShadow: t.box ? undefined : `0 2px 18px ${anthracite(0.9)}`,
            }}
          >
            {content}
          </div>
        </div>
      ) : (
        <span
          style={{
            display: 'inline',
            padding: t.box ? '0.08em 0.3em' : 0,
            background: t.box ? anthracite(0.62) : undefined,
            boxDecorationBreak: 'clone',
            WebkitBoxDecorationBreak: 'clone',
            borderRadius: 6,
            textShadow: t.box ? undefined : `0 3px 22px ${anthracite(0.85)}`,
            backgroundImage: strike > 0 ? `linear-gradient(${RED}, ${RED})` : undefined,
            backgroundRepeat: 'no-repeat',
            backgroundPosition: '0 58%',
            backgroundSize: strike > 0 ? `${strike * 100}% 0.085em` : undefined,
          }}
        >
          {content}
        </span>
      )}
    </div>
  );
};

// ------------------------------------------------------------------ images, traits

export type ImageR = {type: 'image'; src: string; iw: number; ih: number; crop: Rect; dest: Rect; from: number; to: number; fade?: number; zoom?: [number, number]; filter?: string; radius?: number};

export const ImageLayer: React.FC<{im: ImageR; frame: number}> = ({im, frame}) => {
  if (frame < im.from || frame >= im.to) return null;
  const p = (frame - im.from) / Math.max(1, im.to - im.from);
  const z = im.zoom ? interpolate(Easing.inOut(Easing.sin)(p), [0, 1], im.zoom) : 1;
  const cw = im.crop.w / z;
  const ch = im.crop.h / z;
  const cx = im.crop.x + (im.crop.w - cw) / 2;
  const cy = im.crop.y + (im.crop.h - ch) / 2;
  const k = im.dest.w / cw;
  const o = im.fade ? interpolate(frame, [im.from, im.from + im.fade], [0, 1], {extrapolateRight: 'clamp'}) : 1;
  return (
    <div style={{position: 'absolute', left: im.dest.x, top: im.dest.y, width: im.dest.w, height: im.dest.h, overflow: 'hidden', opacity: o, borderRadius: im.radius ?? 0}}>
      <Img src={staticFile(im.src)} style={{position: 'absolute', left: -cx * k, top: -cy * k, width: im.iw * k, height: im.ih * k, maxWidth: 'none', filter: im.filter}} />
    </div>
  );
};

export type RuleR = {type: 'trait'; x: number; y: number; h: number; color?: string; from: number; to: number; widths: {at: number; w: number}[]; align?: 'left' | 'center'};

export const RuleLayer: React.FC<{r: RuleR; frame: number}> = ({r, frame}) => {
  if (frame < r.from || frame >= r.to) return null;
  const ks = r.widths;
  let w = 0;
  if (ks.length) {
    const fr = ks.flatMap((k) => [k.at, k.at + 12]);
    const vs = ks.flatMap((k, i) => [i === 0 ? 0 : ks[i - 1].w, k.w]);
    w = interpolate(frame, fr, vs, {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)});
  }
  const left = r.align === 'center' ? r.x - w / 2 : r.x;
  const o = interpolate(frame, [r.to - 8, r.to], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <div style={{position: 'absolute', left, top: r.y, width: w, height: r.h, background: r.color ?? RED, borderRadius: r.h / 2, opacity: o}} />;
};

// ------------------------------------------------------------------ fond et grain

export const Grain: React.FC<{frame: number; opacity?: number}> = ({frame, opacity = 0.07}) => {
  const seed = Math.floor(random(`g${frame % 24}`) * 1000);
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity, mixBlendMode: 'overlay'}}>
      <svg width="1920" height="1080">
        <filter id={`n${seed}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed={seed} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="1920" height="1080" filter={`url(#n${seed})`} />
      </svg>
    </AbsoluteFill>
  );
};

export const Vignette: React.FC<{strength?: number}> = ({strength = 0.55}) => (
  <AbsoluteFill style={{background: `radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,${strength}) 100%)`, pointerEvents: 'none'}} />
);

export const PaperBg: React.FC<{frame: number}> = ({frame}) => (
  <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 42%, #18212a 0%, ${ANTHRACITE} 62%, #06090c 100%)`}} />
);

// ------------------------------------------------------------------ composition générique

export type FrameR = {type: 'cadre'; dest: Rect; from: number; to: number};
export type Layer = (ClipR & {type: 'clip'}) | TextR | ImageR | RuleR | FrameR | (CaR & {type: 'ca'});

// Cadre vide : la place exacte où le plan va jouer (le test « même cadrage »).
export const FrameLayer: React.FC<{f: FrameR; frame: number}> = ({f, frame}) => {
  if (frame < f.from || frame >= f.to) return null;
  const o = interpolate(frame, [f.from, f.from + 10], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <div
      style={{
        position: 'absolute',
        left: f.dest.x,
        top: f.dest.y,
        width: f.dest.w,
        height: f.dest.h,
        borderRadius: 10,
        border: `2px solid ${ivory(0.28)}`,
        background: 'rgba(0,0,0,0.35)',
        opacity: o,
      }}
    />
  );
};

export type CaR = {
  quote: string; // « Il fait ça pour sa famille. »
  pivot: string; // ça
  from: number;
  to: number;
  pivotAt: number;
  y: number;
  comps: {text: string; at: number; terrain: number}[];
  recapAt?: number;
  eraseAt?: number;
};

// « Il fait ça pour sa famille » : le pronom reste à la même place, le complément évolue dessous.
export const CaLayer: React.FC<{c: CaR; frame: number}> = ({c, frame}) => {
  if (frame < c.from || frame >= c.to) return null;
  const q = typo(c.quote);
  const p = typo(c.pivot);
  const i = q.indexOf(p);
  const left = q.slice(0, i);
  const right = q.slice(i + p.length);
  const enter = interpolate(frame, [c.from, c.from + 12], [0, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const exit = interpolate(frame, [c.to - 10, c.to], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const piv = interpolate(frame, [c.pivotAt, c.pivotAt + 8], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const erase = c.eraseAt !== undefined ? interpolate(frame, [c.eraseAt, c.eraseAt + 12], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1;
  const fontSize = 92;
  const shown = c.comps.filter((k) => frame >= k.at);
  const recap = c.recapAt !== undefined && frame >= c.recapAt;
  const terrain = shown.length ? shown[shown.length - 1].terrain : 0;
  const ks = c.comps.map((k) => k.at);
  const tw = shown.length
    ? interpolate(frame, ks.flatMap((a) => [a, a + 12]), c.comps.flatMap((k, j) => [j === 0 ? 0 : c.comps[j - 1].terrain, k.terrain]), {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.inOut(Easing.cubic),
      })
    : 0;
  return (
    <AbsoluteFill style={{opacity: enter * exit}}>
      <div style={{position: 'absolute', top: c.y, left: 0, width: 1920, display: 'flex', alignItems: 'baseline', fontFamily: SERIF, fontStyle: 'italic', fontSize, color: IVORY, fontWeight: 400}}>
        <div style={{width: 960 - 40, textAlign: 'right', whiteSpace: 'pre', opacity: 1 - 0.55 * piv}}>{left}</div>
        <div style={{width: 80, textAlign: 'center', color: piv > 0.5 ? RED : IVORY, fontWeight: piv > 0.5 ? 600 : 400}}>{p}</div>
        <div style={{width: 960 - 40, textAlign: 'left', whiteSpace: 'pre', opacity: 1 - 0.55 * piv}}>{right}</div>
      </div>
      {/* accolade sous « ça » : elle couvre de plus en plus de terrain */}
      <div style={{position: 'absolute', top: c.y + fontSize * 1.32, left: 960 - tw / 2, width: tw, height: 6, background: RED, borderRadius: 3, opacity: erase}} />
      <div style={{position: 'absolute', top: c.y + fontSize * 1.32 - 22, left: 960 - tw / 2, width: 6, height: 28, background: RED, borderRadius: 3, opacity: tw > 10 ? erase : 0}} />
      <div style={{position: 'absolute', top: c.y + fontSize * 1.32 - 22, left: 960 + tw / 2 - 6, width: 6, height: 28, background: RED, borderRadius: 3, opacity: tw > 10 ? erase : 0}} />
      <div style={{position: 'absolute', top: c.y + fontSize * 1.32 + 34, left: 0, width: 1920, textAlign: 'center', fontFamily: SANS, color: IVORY, opacity: erase}}>
        {c.comps.map((k, j) => {
          if (frame < k.at) return null;
          const isLast = shown[shown.length - 1] === k;
          const a = interpolate(frame, [k.at, k.at + 10], [0, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
          const keep = recap || isLast;
          if (!keep) return null;
          return (
            <div
              key={j}
              style={{
                fontSize: isLast ? 60 : 44,
                fontWeight: isLast ? 700 : 600,
                lineHeight: 1.35,
                opacity: a * (isLast ? 1 : 0.45),
                transform: `translateY(${(1 - a) * 16}px)`,
              }}
            >
              {typo(k.text)}
            </div>
          );
        })}
      </div>
      {terrain === 0 ? null : null}
    </AbsoluteFill>
  );
};

export const LayerView: React.FC<{l: Layer; frame: number}> = ({l, frame}) => {
  switch (l.type) {
    case 'clip':
      return <ClipLayer c={l} frame={frame} />;
    case 'texte':
      return <TextLayer t={l} frame={frame} />;
    case 'image':
      return <ImageLayer im={l} frame={frame} />;
    case 'trait':
      return <RuleLayer r={l} frame={frame} />;
    case 'ca':
      return <CaLayer c={l} frame={frame} />;
    case 'cadre':
      return <FrameLayer f={l} frame={frame} />;
    default:
      return null;
  }
};

export {BlurBackdrop};
