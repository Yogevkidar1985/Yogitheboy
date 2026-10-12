import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// VITE_TARGET=artifact builds the single-file copy published as a Claude
// Artifact, so the on-demand PDF chunks are folded into the one bundle.
// VITE_TARGET=pages builds the static site GitHub Pages serves from /docs,
// with relative asset paths so it works under /<repo>/.
const target = process.env.VITE_TARGET
export default defineConfig({
  plugins: [react()],
  base: target === 'pages' ? './' : '/',
  build: target === 'artifact' ? { rollupOptions: { output: { inlineDynamicImports: true } } } : {},
})
