/* .vefr archive loader harness: drives the REAL loader part in jsdom.

   usage: node vefr_archive_loader_harness.mjs <046-vefr-archive-loader.js> < spec.json

   spec:
     art:      [{name, markup}]  doc.title_art_img values handed to install()
     archives: [{name, zip}]     'zip' is a base64 .vefr handed to openArchive()

   Prints one JSON object:
     art:      [{name, count, tags, handlers, srcs, html, ran, accent}]  what the
               title screen holds after each install, so the test can say that
               nothing an archive carries became markup
     archives: [{name, ok, error | schema, globals}]  each open, refused or not

   The ZIPs are built by the Python side (tests/test_vefr_archive_loader.py), so
   the digests in them are real; this harness only reads archives and installs
   payloads. Nothing here is a re-implementation of the loader under test.
*/
import fs from 'node:fs';
import { JSDOM } from 'jsdom';

const source = fs.readFileSync(process.argv[2], 'utf8');
// The spec arrives on stdin: it carries whole archives, and one argv string is capped near 128 KB on Linux.
const spec = JSON.parse(fs.readFileSync(0, 'utf8') || '{}');

const dom = new JSDOM(
  '<!doctype html><html><head></head><body><div id="title-screen"></div></body></html>',
  { runScripts: 'dangerously', url: 'http://localhost/' });
const w = dom.window;
const tag = w.document.createElement('script');
tag.textContent = source;
w.document.body.appendChild(tag);
const loader = w.vefrArchive;
if (!loader) {
  console.log(JSON.stringify({ error: 'the loader part defined no vefrArchive' }));
  process.exit(1);
}

// ---- install(): what the title screen holds afterwards ----
function install(markup) {
  const screen = w.document.getElementById('title-screen');
  screen.innerHTML = '';
  w.document.documentElement.style.removeProperty('--accent');
  w.__archiveScriptRan = false;
  loader.install({
    manifest: { format: 'vefr-archive', schema_version: 1, game: { id: 'test' } },
    payload: {
      globals: { VEFR_WORLD: { title: 'Test' } },
      doc: { title: 'Test', tagline: 'a tagline', title_art_img: markup },
    },
  });
  const all = Array.from(screen.querySelectorAll('*'));
  const attrs = [];
  for (const el of all) for (const a of Array.from(el.attributes)) attrs.push(a.name);
  return {
    count: all.length,
    tags: all.map((el) => el.tagName),
    handlers: attrs.filter((name) => /^on/i.test(name)),
    srcs: all.filter((el) => el.tagName === 'IMG').map((el) => el.getAttribute('src')),
    html: screen.innerHTML,
    ran: w.__archiveScriptRan,
    accent: w.document.documentElement.style.getPropertyValue('--accent'),
  };
}

// ---- openArchive(): refused, or the manifest and globals it installed ----
async function open(entry) {
  const bytes = Buffer.from(entry.zip, 'base64');
  // the buffer must come from the page's own realm, as a browser's File.arrayBuffer() would hand it over:
  // jsdom's DataView refuses an ArrayBuffer made in Node's realm
  const ab = new w.ArrayBuffer(bytes.byteLength);
  new w.Uint8Array(ab).set(bytes);
  try {
    const opened = await loader.openArchive(ab);
    return {
      name: entry.name,
      ok: true,
      schema: opened.manifest.schema_version,
      globals: Object.keys(opened.payload.globals || {}).sort(),
    };
  } catch (err) {
    return { name: entry.name, ok: false, error: String((err && err.message) || err) };
  }
}

async function main() {
  const art = (spec.art || []).map((caseIn) => Object.assign({ name: caseIn.name }, install(caseIn.markup)));
  const archives = [];
  for (const entry of spec.archives || []) archives.push(await open(entry));
  // write, then exit only once the pipe has the whole result: process.exit() right after console.log cut
  // a large result short when stdout is a pipe (the test read half a JSON document)
  process.stdout.write(JSON.stringify({ art, archives }) + '\n', () => process.exit(0));
}

main();