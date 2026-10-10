// Builds the single-file page published as a Claude Artifact:
//   VITE_TARGET=artifact vite build --outDir dist-artifact, then inline CSS + JS.
// Usage: node scripts/build-artifact.mjs <out.html>
import { execSync } from 'node:child_process'
import { readFileSync, readdirSync, writeFileSync } from 'node:fs'

execSync('npx vite build --outDir dist-artifact', { stdio: 'inherit', env: { ...process.env, VITE_TARGET: 'artifact' } })
const dir = 'dist-artifact/assets'
const files = readdirSync(dir)
const css = files.filter(f => f.endsWith('.css')).map(f => readFileSync(`${dir}/${f}`, 'utf8')).join('\n')
const js = files.filter(f => f.endsWith('.js'))
if (js.length !== 1) throw new Error(`expected one JS bundle, got ${js.join(', ')}`)
const code = readFileSync(`${dir}/${js[0]}`, 'utf8').replace(/<\/script/g, '<\\/script')
writeFileSync(process.argv[2] || 'dist-artifact/birth-plan.html', `<title>שאלון תכנית לידה</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700;800&display=swap" rel="stylesheet" crossorigin="anonymous">
<style>${css}</style>
<div id="root" dir="rtl" lang="he"></div>
<script type="module">${code}</script>
`)
