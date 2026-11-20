import {Config} from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(92);
Config.setCodec('h264');
Config.setCrf(17);
Config.setPixelFormat('yuv420p');
Config.setColorSpace('bt709');
Config.setOverwriteOutput(true);
Config.setEntryPoint('src/index.ts');
