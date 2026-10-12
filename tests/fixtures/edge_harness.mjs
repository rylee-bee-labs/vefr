/* Edges harness: runs the REAL window.edgeMask from web/packaged.html (between its own marker comments) in a
   node vm sandbox over the map given as JSON in argv[3], and prints the mask of every cell as JSON rows.
   Usage: node edge_harness.mjs <packaged.html> '<["row", ...]>' */
import fs from 'node:fs';
import vm from 'node:vm';

const [htmlPath, mapJson] = process.argv.slice(2);
if (!htmlPath || !mapJson) throw new Error('usage: edge_harness.mjs <packaged.html> <map json>');
const html = fs.readFileSync(htmlPath, 'utf8');
const start = html.indexOf('// -- edgeMask start --');
const end = html.indexOf('// -- edgeMask end --');
if (start === -1 || end === -1 || end < start) throw new Error('edgeMask markers not found');

const ctx = { Math };
ctx.globalThis = ctx;
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(html.slice(start, end), ctx, { timeout: 5000 });
if (typeof ctx.edgeMask !== 'function') throw new Error('the block did not define edgeMask');

const map = JSON.parse(mapJson);
console.log(JSON.stringify(map.map((row, y) => [...row].map((_, x) => ctx.edgeMask(map, x, y)))));
