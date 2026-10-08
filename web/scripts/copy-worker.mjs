// MapLibre 6 loads its worker from next to its module. After the Next bundle, the worker is not there ("worker
// failed to load"). Copy it to public/; the map sets it with setWorkerUrl.
import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
mkdirSync(join(root, 'public'), { recursive: true });
copyFileSync(join(root, 'node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs'), join(root, 'public/maplibre-gl-worker.mjs'));
