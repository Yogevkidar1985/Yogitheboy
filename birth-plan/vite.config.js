import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// VITE_TARGET=artifact builds the single-file copy published as a Claude
// Artifact, so the on-demand PDF chunks are folded into the one bundle.
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  build: process.env.VITE_TARGET === 'artifact' ? { rollupOptions: { output: { inlineDynamicImports: true } } } : {},
}))
