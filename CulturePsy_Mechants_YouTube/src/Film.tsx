import React from 'react';
import {AbsoluteFill, Audio, Img, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import resolved from './data/resolved.json';
import {ANTHRACITE, IVORY, RED, SANS, anthracite, fontFaces, ivory, typo} from './lib/theme';
import {BlurBackdrop, ClipLayer, ClipR} from './components/Clip';
import {Grain, Layer, LayerView, PaperBg, Vignette} from './components/Layers';

type PlanR = {
  id: string;
  from: number;
  to: number;
  type: 'clip' | 'compose' | 'planche' | 'noir';
  clip?: ClipR;
  backdrop?: 'flou' | 'anthracite' | 'aucun';
  layers?: Layer[];
  planche?: {src: string; missing: boolean; title: string};
  fade?: number; // fondu enchaîné avec le plan précédent (images)
  treatment?: 'flashback' | 'reconstitution' | 'souvenir';
};

type Resolved = {
  fps: number;
  durationInFrames: number;
  calage: boolean;
  plans: PlanR[];
  overlays: Layer[];
  subs: {from: number; to: number; lines: string[]}[];
  banners: {spoiler: {from: number; to: number; text: string}; calage: boolean};
  audio: {
    voice: {src: string; from: number; trimBefore: number; trimAfter: number; volume: number}[];
    sfx: {src: string; from: number; dur: number; volume: number}[];
    music: null | {src: string; volume: number; env: {f: number; v: number}[]};
  };
};

const R = resolved as unknown as Resolved;
export const FILM_FRAMES = R.durationInFrames;

const TREAT: Record<string, string> = {
  flashback: 'sepia(0.28) saturate(0.78) contrast(0.96) brightness(0.97)',
  reconstitution: 'saturate(0.85)',
  souvenir: 'sepia(0.15) saturate(0.9)',
};

const PlanView: React.FC<{p: PlanR; frame: number}> = ({p, frame}) => {
  if (p.type === 'noir') return <AbsoluteFill style={{background: '#000'}} />;
  if (p.type === 'planche' && p.planche) {
    if (p.planche.missing) {
      return (
        <AbsoluteFill style={{background: ANTHRACITE, alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 18}}>
          <div style={{fontFamily: SANS, fontWeight: 600, fontSize: 30, letterSpacing: '0.2em', color: RED}}>PLANCHE MANQUANTE</div>
          <div style={{fontFamily: SANS, fontWeight: 600, fontSize: 52, color: IVORY}}>{p.planche.title}</div>
          <div style={{fontFamily: SANS, fontWeight: 500, fontSize: 28, color: ivory(0.6)}}>{p.planche.src}</div>
        </AbsoluteFill>
      );
    }
    const o = interpolate(frame, [p.from, p.from + 10], [0, 1], {extrapolateRight: 'clamp'});
    return (
      <AbsoluteFill style={{background: ANTHRACITE}}>
        <Img src={staticFile(p.planche.src)} style={{width: 1920, height: 1080, opacity: o}} />
      </AbsoluteFill>
    );
  }
  const filter = p.treatment ? TREAT[p.treatment] : undefined;
  return (
    <AbsoluteFill style={{background: ANTHRACITE, filter}}>
      {p.type === 'clip' && p.clip ? (
        <>
          {p.backdrop === 'flou' ? <BlurBackdrop c={p.clip} frame={frame} /> : p.backdrop === 'anthracite' ? <PaperBg frame={frame} /> : null}
          <ClipLayer c={p.clip} frame={frame} />
        </>
      ) : null}
      {p.type === 'compose' ? (
        <>
          {p.backdrop === 'flou' && p.layers?.[0]?.type === 'clip' ? <BlurBackdrop c={p.layers[0] as ClipR} frame={frame} dim={0.22} /> : <PaperBg frame={frame} />}
          {p.layers?.map((l, i) => <LayerView key={i} l={l} frame={frame} />)}
        </>
      ) : null}
      {p.treatment === 'flashback' ? <Vignette strength={0.5} /> : null}
    </AbsoluteFill>
  );
};

const Subtitles: React.FC<{frame: number}> = ({frame}) => {
  const s = R.subs.find((e) => frame >= e.from && frame < e.to);
  if (!s) return null;
  return (
    <div style={{position: 'absolute', left: 160, right: 160, bottom: 64, display: 'flex', justifyContent: 'center'}}>
      <div
        style={{
          fontFamily: SANS,
          fontWeight: 600,
          fontSize: 46,
          lineHeight: 1.25,
          color: IVORY,
          textAlign: 'center',
          background: anthracite(0.72),
          padding: '8px 22px 10px',
          borderRadius: 10,
        }}
      >
        {s.lines.map((l, i) => (
          <div key={i}>{l}</div>
        ))}
      </div>
    </div>
  );
};

export const Film: React.FC = () => {
  const frame = useCurrentFrame();
  const idx = R.plans.findIndex((p) => frame >= p.from && frame < p.to);
  const p = R.plans[idx];
  const prev = idx > 0 ? R.plans[idx - 1] : undefined;
  const fading = p && p.fade && prev && frame < p.from + p.fade;
  const fadeK = fading ? interpolate(frame, [p.from, p.from + p.fade!], [0, 1]) : 1;
  const sp = R.banners.spoiler;
  const spO = interpolate(frame, [sp.from, sp.from + 1, sp.to - 12, sp.to], [1, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const musicVol = (f: number) => {
    const m = R.audio.music;
    if (!m || m.env.length === 0) return 0;
    return interpolate(f, m.env.map((e) => e.f), m.env.map((e) => e.v), {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) * m.volume;
  };
  return (
    <AbsoluteFill style={{background: ANTHRACITE}}>
      <style>{fontFaces}</style>
      {fading && prev ? <PlanView p={prev} frame={frame} /> : null}
      {p ? (
        <AbsoluteFill style={{opacity: fadeK}}>
          <PlanView p={p} frame={frame} />
        </AbsoluteFill>
      ) : null}
      {p && p.type !== 'noir' && p.type !== 'planche' ? <Grain frame={frame} opacity={0.055} /> : null}

      {R.overlays.map((l, i) => (
        <LayerView key={`o${i}`} l={l} frame={frame} />
      ))}

      {frame < sp.to ? (
        <div style={{position: 'absolute', left: 64, top: 52, opacity: spO, display: 'flex', alignItems: 'center', gap: 14, fontFamily: SANS, fontWeight: 600, fontSize: 30, color: IVORY}}>
          <div style={{padding: '9px 18px', borderRadius: 999, background: anthracite(0.66), border: `1.5px solid ${ivory(0.28)}`}}>{typo(sp.text)}</div>
        </div>
      ) : null}

      {R.calage && p?.type !== 'noir' ? <Subtitles frame={frame} /> : null}
      {R.banners.calage && p?.type !== 'noir' ? (
        <div
          style={{
            position: 'absolute',
            right: 56,
            top: 52,
            fontFamily: SANS,
            fontWeight: 700,
            fontSize: 22,
            letterSpacing: '0.16em',
            color: ivory(0.62),
            border: `1.5px solid ${ivory(0.32)}`,
            borderRadius: 8,
            padding: '6px 12px',
            background: anthracite(0.4),
          }}
        >
          VERSION DE CALAGE
        </div>
      ) : null}

      {R.audio.voice.map((v, i) => (
        <Sequence key={`v${i}`} from={v.from} durationInFrames={v.trimAfter - v.trimBefore}>
          <Audio src={staticFile(v.src)} trimBefore={v.trimBefore} durationInFrames={v.trimAfter - v.trimBefore} volume={v.volume} />
        </Sequence>
      ))}
      {R.audio.sfx.map((s, i) => (
        <Sequence key={`s${i}`} from={s.from} durationInFrames={s.dur}>
          <Audio src={staticFile(s.src)} volume={(f) => s.volume * interpolate(f, [s.dur - 6, s.dur], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})} />
        </Sequence>
      ))}
      {R.audio.music ? <Audio src={staticFile(R.audio.music.src)} volume={(f) => musicVol(f)} /> : null}
    </AbsoluteFill>
  );
};
