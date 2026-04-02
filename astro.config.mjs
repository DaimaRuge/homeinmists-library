// @ts-check
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://homeinmists-library.vercel.app',
  build: {
    inlineStylesheets: 'auto',
  },
  vite: {
    build: {
      cssMinify: true,
    },
  },
});
