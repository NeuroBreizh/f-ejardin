import React from 'react';
import {Composition} from 'remotion';
import {FILM_FRAMES, Film} from './Film';

export const RemotionRoot: React.FC = () => (
  <Composition id="CulturePsyMechantsYouTube" component={Film} durationInFrames={FILM_FRAMES} fps={30} width={1920} height={1080} />
);
