import { defineConfig } from 'vite';
export default defineConfig({ publicDir: false, build: {
  outDir: 'public/share', emptyOutDir: true,
  lib: { entry: 'web/standalone.js', name: 'PainterViewer', formats: ['iife'], fileName: () => 'viewer.js' },
  minify: true,
} });
