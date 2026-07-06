import { mkdirSync, writeFileSync, copyFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
const dist = 'dist';
mkdirSync(join(dist, 'assets'), { recursive: true });
for (const file of ['static-app.js', 'styles.css']) copyFileSync(join('src', file), join(dist, 'assets', file === 'static-app.js' ? 'app.js' : 'style.css'));
for (const file of ['labDefinitions.js', 'badgeDefinitions.js', 'scenarioLibrary.js']) copyFileSync(join('src', 'data', file), join(dist, 'assets', file));
writeFileSync(join(dist, 'index.html'), `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>Gibson CICS Banking Training Console</title><link rel="stylesheet" href="/assets/style.css"></head><body><div id="root"></div><script type="module" src="/assets/app.js"></script></body></html>`);
if (!existsSync(join(dist, 'index.html'))) process.exit(2);
console.log('React8999 guided-labs static build complete: dist/index.html');
