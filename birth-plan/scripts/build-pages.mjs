// Builds the static site GitHub Pages serves from the repo's /docs folder
// (Settings → Pages → Deploy from a branch → this branch, /docs).
import { execSync } from 'node:child_process'
import { writeFileSync } from 'node:fs'

execSync('npx vite build --outDir ../docs --emptyOutDir', { stdio: 'inherit', env: { ...process.env, VITE_TARGET: 'pages' } })
writeFileSync('../docs/.nojekyll', '')
