import React from 'react';
import {Easing, Freeze, OffthreadVideo, interpolate, staticFile} from 'remotion';

export type Rect = {x: number; y: number; w: number; h: number};

// Plan résolu par tools/resolve_montage.py : tout est déjà en images et en pixels.
export type ClipR = {
  src: string; // fichier dans public/ (proxy tout-intra si présent)
  w: number; // dimensions de la capture
  h: number;
  crop: Rect; // zone de la capture affichée (px source), même rapport que dest
  dest: Rect; // zone de l'image 1920×1080
  in: number; // image source au début
  rate: number; // 0 = image figée
  clean: [number, number]; // plage d'images autorisée
  from: number; // image du film où ce calque commence
  to: number;
  zoom?: [number, number];
  focus?: [number, number];
  filter?: string;
  radius?: number;
  fade?: number; // fondu d'entrée en images
  fadeOut?: number;
  shadow?: boolean;
  label?: string; // capture absente : description du plan prévu, affichée sur la mire
};

export const sourceFrame = (c: ClipR, frame: number) => {
  const raw = Math.round(c.in + (frame - c.from) * c.rate);
  return Math.max(c.clean[0], Math.min(c.clean[1], raw));
};

export const ClipLayer: React.FC<{c: ClipR; frame: number; extraFilter?: string; style?: React.CSSProperties; noRadius?: boolean}> = ({
  c,
  frame,
  extraFilter,
  style,
  noRadius,
}) => {
  if (frame < c.from || frame >= c.to) return null;
  const dur = Math.max(1, c.to - c.from);
  const p = Math.min(1, Math.max(0, (frame - c.from) / dur));
  const z = c.zoom ? interpolate(Easing.inOut(Easing.sin)(p), [0, 1], c.zoom) : 1;
  const [fx, fy] = c.focus ?? [0.5, 0.5];
  const cw = c.crop.w / z;
  const ch = c.crop.h / z;
  const cx = c.crop.x + (c.crop.w - cw) * fx;
  const cy = c.crop.y + (c.crop.h - ch) * fy;
  const k = c.dest.w / cw; // même rapport : aucune déformation
  const left = -cx * k;
  const top = -cy * k;
  const fadeIn = c.fade ? interpolate(frame, [c.from, c.from + c.fade], [0, 1], {extrapolateRight: 'clamp'}) : 1;
  const fadeOut = c.fadeOut ? interpolate(frame, [c.to - c.fadeOut, c.to], [1, 0], {extrapolateLeft: 'clamp'}) : 1;
  const filter = [c.filter, extraFilter].filter(Boolean).join(' ') || undefined;
  return (
    <div
      style={{
        position: 'absolute',
        left: c.dest.x,
        top: c.dest.y,
        width: c.dest.w,
        height: c.dest.h,
        overflow: 'hidden',
        borderRadius: noRadius ? 0 : c.radius ?? 0,
        opacity: fadeIn * fadeOut,
        boxShadow: c.shadow ? '0 0 0 1.5px rgba(248,238,220,0.14), 0 30px 80px rgba(0,0,0,0.6)' : undefined,
        ...style,
      }}
    >
      <Freeze frame={sourceFrame(c, frame)}>
        <OffthreadVideo
          src={staticFile(c.src)}
          muted
          style={{position: 'absolute', left, top, width: c.w * k, height: c.h * k, maxWidth: 'none', filter}}
        />
      </Freeze>
      {c.label ? (
        <div
          style={{
            position: 'absolute',
            left: '6%',
            right: '6%',
            top: '50%',
            transform: 'translateY(-50%)',
            textAlign: 'center',
            fontFamily: "'InterW', 'InterCP', sans-serif",
            fontWeight: 600,
            fontSize: Math.max(18, Math.min(44, c.dest.w / 34)),
            lineHeight: 1.25,
            color: '#F8EEDC',
            textShadow: '0 2px 10px rgba(0,0,0,0.9)',
          }}
        >
          {c.label}
        </div>
      ) : null}
    </div>
  );
};

// Fond flou tiré de la même image, pour les plans présentés dans un cadre intégré.
export const BlurBackdrop: React.FC<{c: ClipR; frame: number; dim?: number}> = ({c, frame, dim = 0.3}) => {
  const k = Math.max(1920 / c.crop.w, 1080 / c.crop.h) * 1.15;
  const dest = {x: (1920 - c.crop.w * k) / 2, y: (1080 - c.crop.h * k) / 2, w: c.crop.w * k, h: c.crop.h * k};
  return (
    <ClipLayer
      c={{...c, dest, zoom: undefined, radius: 0, fade: undefined, fadeOut: undefined, shadow: false, label: undefined}}
      frame={frame}
      extraFilter={`blur(48px) brightness(${dim}) saturate(1.15)`}
      noRadius
    />
  );
};
