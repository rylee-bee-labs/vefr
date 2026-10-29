// The light rig: lightrig.js 1.0.1, the shared per-pixel light (WebGL2) that Lamplight (505-lamplight.js) uses.
// A pinned copy, byte for byte, with `export ` taken off its one export because the player is one classic
// script; tests/test_lamplight_player.py holds its sha256 and says how to move to a new version. Wrapped so
// only createLightRig reaches the player's scope. Edit the rig upstream, never here.
var createLightRig = (function () {
// -- lightrig.js 1.0.1 start --
// lightrig.js 1.0.1: light a stack of painted planes with a few point lights. WebGL2, no libraries, no build step.
//
// A shared light rig: one module that games keep a copy of, pinned by sha256.
//
// World units are whatever the game
// uses (px); x right, y down, z toward the viewer (up, for a top-down map). Per pixel: each light is a point with
// height, a grey height paint rakes it (relief), and planes nearer the light shadow the ones behind (the ray to the
// light meets each caster plane; the caster's mipmaps soften the edge by the gap). Left out on purpose: one game's own
// materials (vellum, photo, eye, rain), memory mask, flame sprite and embers, picture-box lean, page fit.

const VS = `#version 300 es
layout(location = 0) in vec2 a; uniform vec3 uO, uU, uV; uniform vec4 uCam; uniform vec2 uVP; out vec2 vUV; out vec3 vP;
void main() {
  vec3 P = uO + a.x * uU + a.y * uV; vUV = a; vP = P;
  float w = uCam.w > 0.0 ? (uCam.w - P.z) / uCam.w : 1.0;
  gl_Position = vec4((P.x - uCam.x) * uCam.z * 2.0 / uVP.x, -(P.y - uCam.y) * uCam.z * 2.0 / uVP.y, 0.0, w);
}`;

const FS = (NL, NC) => `#version 300 es
precision highp float; precision highp sampler2DArray;
in vec2 vUV; in vec3 vP; out vec4 o;
uniform sampler2D uAlb, uH; uniform sampler2DArray uSh;
uniform bool uHasH, uHasN, uTone; uniform vec2 uTx; uniform float uRelief, uZK, uShN;
uniform vec3 uU, uV, uAmb; uniform int uSelf, uNC, uNL;
uniform vec4 uL[${NL}], uLC[${NL}], uLE[${NL}];
uniform vec3 uCO[${NC}], uCU[${NC}], uCV[${NC}]; uniform float uCS[${NC}], uCT[${NC}];
// A caster is a flat sheet, or (thickness > 0) a block standing under it, sampled as three slices (its foot is
// never needed: the ground under it is lit as the block's top).
float shade(vec3 P, vec3 L, float size) {
  float lit = 1.0;
  vec3 d = L - P;
  for (int i = 0; i < ${NC}; i++) {
    if (i >= uNC) break;
    if (i == uSelf) continue;
    vec3 N = cross(uCU[i], uCV[i]);
    float den = dot(d, N), occ = 0.0;
    if (abs(den) < 1e-5) continue;
    for (int k = 0; k < 3; k++) {
      vec3 O = uCO[i] - normalize(N) * uCT[i] * float(k) / 3.0;
      float t = dot(O - P, N) / den;
      if (t > 0.002 && t < 1.0) {
        vec3 H = P + t * d - O;
        vec2 uv = vec2(dot(H, uCU[i]) / dot(uCU[i], uCU[i]), dot(H, uCV[i]) / dot(uCV[i], uCV[i]));
        if (uv.x >= 0.0 && uv.y >= 0.0 && uv.x <= 1.0 && uv.y <= 1.0)
          occ = max(occ, textureLod(uSh, vec3(uv, float(i)), log2(max(size * t * uShN / length(uCU[i]), 1.0))).a);
      }
      if (uCT[i] <= 0.0) break;
    }
    lit *= 1.0 - occ * uCS[i];
  }
  return lit;
}
void main() {
  vec4 alb = texture(uAlb, vUV);
  if (alb.a < 0.003) discard;
  vec3 Np = normalize(cross(uU, uV)), N = Np;
  if (uHasN) {
    vec3 n = texture(uH, vUV).rgb * 2.0 - 1.0;   // lab-kit's normal map: tangent space, +Y up the picture
    N = normalize(n.x * uRelief * normalize(uU) - n.y * uRelief * normalize(uV) + n.z * Np);
  } else if (uHasH) {
    float hx = texture(uH, vUV + vec2(uTx.x, 0.0)).r - texture(uH, vUV - vec2(uTx.x, 0.0)).r;
    float hy = texture(uH, vUV + vec2(0.0, uTx.y)).r - texture(uH, vUV - vec2(0.0, uTx.y)).r;
    N = normalize(-hx * uRelief * normalize(uU) - hy * uRelief * normalize(uV) + Np);
  }
  vec3 light = vec3(0.0);
  for (int i = 0; i < ${NL}; i++) {
    if (i >= uNL) break;
    vec3 d = uL[i].xyz - vP; d.z *= uZK;
    float dist = max(length(d), 1e-4), r = dist / uLC[i].w;
    float win = clamp(1.0 - r * r * r * r / 256.0, 0.0, 1.0);   // gone by 4 x reach
    float at = uL[i].w / (1.0 + r * r) * win * win;
    float diff = max(0.0, (dot(N, d / dist) + 0.3) / 1.3);
    if (at * diff < 0.004) continue;   // too faint to see: no shadow test
    float sh = uLE[i].w > 0.0 ? shade(vP, uL[i].xyz, uLE[i].w) : 1.0;
    light += mix(uLE[i].rgb, uLC[i].rgb, clamp(at / max(uL[i].w, 1e-4), 0.0, 1.0)) * at * diff * sh;
  }
  vec3 c = alb.rgb * (uAmb + light);
  if (uTone) c = mix(c, 0.8 + 0.2 * (1.0 - exp((0.8 - c) * 5.0)), step(0.8, c));   // a soft shoulder, not a white clip
  o = vec4(c, alb.a);
}`;

// The glow around a light: an additive soft disc, no texture.
const GVS = `#version 300 es
layout(location = 0) in vec2 a; uniform vec4 uQ; out vec2 vQ;
void main() { vQ = a * 2.0 - 1.0; gl_Position = vec4(uQ.xy + vQ * uQ.zw, 0.0, 1.0); }`;
const GFS = `#version 300 es
precision mediump float; in vec2 vQ; out vec4 o; uniform vec4 uG;
void main() { float f = max(0.0, 1.0 - length(vQ)); f *= f; o = vec4(uG.rgb * uG.a * f, 0.0); }`;

function createLightRig(canvas, opts = {}) {
  const NL = opts.maxLights || 4, NC = opts.maxCasters || 4, SN = opts.shadowSize || 512;
  const gl = canvas.getContext('webgl2', { alpha: false, antialias: false, premultipliedAlpha: true,
    preserveDrawingBuffer: !!opts.preserveDrawingBuffer });
  if (!gl) throw new Error('no WebGL2');
  if (gl.isContextLost()) throw new Error('the WebGL2 context is lost; make the rig on a fresh canvas');
  // A lost context stays lost (no preventDefault, so the browser doesn't restore it under a rig whose textures are
  // gone): the game hears onLost and keeps its own drawing.
  canvas.addEventListener('webglcontextlost', () => { opts.onLost?.(); });
  const doc = canvas.ownerDocument;
  const prog = program(gl, VS, FS(NL, NC)), gprog = program(gl, GVS, GFS);
  const u = uniforms(gl, prog), gu = uniforms(gl, gprog);
  const quad = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, quad);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), gl.STATIC_DRAW);
  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

  // The shadow casters: each one's alpha, squeezed into one layer of a texture array.
  const sh = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D_ARRAY, sh);
  gl.texStorage3D(gl.TEXTURE_2D_ARRAY, Math.log2(SN) + 1, gl.RGBA8, SN, SN, NC);
  for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR],
    [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D_ARRAY, k, v);
  const squeeze = doc.createElement('canvas');
  squeeze.width = squeeze.height = SN;
  const sx = squeeze.getContext('2d');

  let planes = [];
  function geometry(p) {
    if (p.O) return { O: p.O, U: p.U, V: p.V };
    const [x, y, w, h] = p.rect, z = p.z || 0;
    return { O: [x, y, z], U: [w, 0, 0], V: [0, h, 0] };
  }
  // A phone caps textures (often at 4096): a bigger picture is refused here, never drawn as a silent black plane.
  const maxTex = gl.getParameter(gl.MAX_TEXTURE_SIZE);
  function fits(pic, what) {
    if (pic.width > maxTex || pic.height > maxTex)
      throw new Error(`the ${what} (${pic.width}x${pic.height}) is too big for this GPU (at most ${maxTex} px a side)`);
  }
  function upload(R, src) {
    if (src.albedo) fits(src.albedo, 'picture');
    if (src.normal || src.height) fits(src.normal || src.height, src.normal ? 'normal map' : 'height paint');
    if (src.albedo) {
      R.alb = tex(gl, src.albedo, true, R.mips, R.nearest, R.alb);
      R.tw = src.albedo.width; R.th = src.albedo.height;
      if (R.caster >= 0) {
        sx.clearRect(0, 0, SN, SN);
        sx.drawImage(src.albedo, 0, 0, SN, SN);
        gl.bindTexture(gl.TEXTURE_2D_ARRAY, sh);
        gl.texSubImage3D(gl.TEXTURE_2D_ARRAY, 0, 0, 0, R.caster, SN, SN, 1, gl.RGBA, gl.UNSIGNED_BYTE, squeeze);
        R.dirty = true;
      }
    }
    const bump = src.normal || src.height;
    if (bump) {
      R.h = tex(gl, bump, false, R.mips, R.nearest, R.h);
      R.hw = bump.width; R.hh = bump.height; R.isN = !!src.normal;
    }
  }
  function mipShadows() {
    if (!planes.some((R) => R.dirty)) return;
    gl.bindTexture(gl.TEXTURE_2D_ARRAY, sh);
    gl.generateMipmap(gl.TEXTURE_2D_ARRAY);
    planes.forEach((R) => { R.dirty = false; });
  }

  // planes: [{ albedo, normal? or height?, rect: [x, y, w, h], z?, casts? (0..1), thickness?, relief?, mips?, nearest? }],
  // back first. normal: a tangent-space normal map (+Y up, lab-kit's); height: grey, lighter = raised (4 taps a pixel).
  function setPlanes(list) {
    // Check everything before changing anything, so a refused list leaves the last good planes drawing.
    if (list.filter((p) => (p.casts || 0) > 0).length > NC) throw new Error('too many shadow casters');
    for (const p of list) {
      if (p.albedo) fits(p.albedo, 'picture');
      if (p.normal || p.height) fits(p.normal || p.height, p.normal ? 'normal map' : 'height paint');
    }
    planes.forEach((R) => { gl.deleteTexture(R.alb); if (R.h) gl.deleteTexture(R.h); });
    let c = 0;
    planes = list.map((p) => {
      const R = { ...geometry(p), casts: p.casts || 0, thickness: p.thickness || 0, relief: p.relief ?? (p.normal ? 1 : 2), mips: p.mips ?? true, nearest: !!p.nearest, caster: -1, alb: null, h: null, hidden: false };
      if (R.casts > 0) { if (c >= NC) throw new Error('too many shadow casters'); R.caster = c++; }
      upload(R, p);
      return R;
    });
    mipShadows();
  }
  // A plane's art changed (the game redrew it): send only what changed.
  function updatePlane(i, src) {
    const R = planes[i];
    if (src.rect || src.O) Object.assign(R, geometry({ ...src, z: src.z ?? R.O[2] }));
    if ('hidden' in src) R.hidden = !!src.hidden;
    upload(R, src);
    mipShadows();
  }

  // camera: { x, y, zoom = 1 (device px per world unit), depth = 0 (0: straight down, no perspective) }
  // lights: [{ x, y, z, color, edge?, intensity = 1, reach = 200, size = 24 (0: no shadows), glow = 0 }]
  function render({ camera, lights = [], ambient = [0.12, 0.14, 0.2], clear = [0.02, 0.027, 0.043], shoulder = true }) {
    const vw = canvas.width, vh = canvas.height, z = camera.zoom || 1;
    gl.viewport(0, 0, vw, vh);
    gl.clearColor(clear[0], clear[1], clear[2], 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.useProgram(prog);
    gl.bindVertexArray(vao);
    gl.uniform4f(u.uCam, camera.x, camera.y, z, camera.depth || 0);
    gl.uniform2f(u.uVP, vw, vh);
    gl.uniform3fv(u.uAmb, ambient);
    gl.uniform1f(u.uZK, opts.depthWeight ?? 1);
    gl.uniform1f(u.uShN, SN);
    gl.uniform1i(u.uTone, shoulder ? 1 : 0);
    const n = Math.min(lights.length, NL), L = new Float32Array(NL * 4), LC = new Float32Array(NL * 4), LE = new Float32Array(NL * 4);
    for (let i = 0; i < n; i++) {
      const l = lights[i], c = l.color || [1, 0.82, 0.55], e = l.edge || c;
      L.set([l.x, l.y, l.z || 0, l.intensity ?? 1], i * 4);
      LC.set([c[0], c[1], c[2], l.reach || 200], i * 4);
      LE.set([e[0], e[1], e[2], l.size ?? 24], i * 4);
    }
    gl.uniform4fv(u['uL[0]'], L); gl.uniform4fv(u['uLC[0]'], LC); gl.uniform4fv(u['uLE[0]'], LE);
    gl.uniform1i(u.uNL, n);
    const CO = new Float32Array(NC * 3), CU = new Float32Array(NC * 3), CV = new Float32Array(NC * 3), CS = new Float32Array(NC), CT = new Float32Array(NC);
    let nc = 0;
    for (const R of planes) if (R.caster >= 0) {
      CO.set(R.O, R.caster * 3); CU.set(R.U, R.caster * 3); CV.set(R.V, R.caster * 3);
      CS[R.caster] = R.hidden ? 0 : R.casts; CT[R.caster] = R.thickness; nc = Math.max(nc, R.caster + 1);
    }
    gl.uniform3fv(u['uCO[0]'], CO); gl.uniform3fv(u['uCU[0]'], CU); gl.uniform3fv(u['uCV[0]'], CV);
    gl.uniform1fv(u['uCS[0]'], CS); gl.uniform1fv(u['uCT[0]'], CT);
    gl.uniform1i(u.uNC, nc);
    gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D_ARRAY, sh);
    gl.uniform1i(u.uSh, 2); gl.uniform1i(u.uAlb, 0); gl.uniform1i(u.uH, 1);
    for (const R of planes) {
      if (R.hidden) continue;
      gl.uniform3fv(u.uO, R.O); gl.uniform3fv(u.uU, R.U); gl.uniform3fv(u.uV, R.V);
      gl.uniform1i(u.uSelf, R.caster);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, R.alb);
      gl.uniform1i(u.uHasH, R.h && !R.isN ? 1 : 0);
      gl.uniform1i(u.uHasN, R.h && R.isN ? 1 : 0);
      if (R.h) {
        gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, R.h);
        gl.uniform2f(u.uTx, 1 / R.hw, 1 / R.hh);
        gl.uniform1f(u.uRelief, R.relief);
      }
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    // The glows, added over everything.
    gl.useProgram(gprog);
    gl.blendFunc(gl.ONE, gl.ONE);
    for (let i = 0; i < n; i++) {
      const l = lights[i];
      if (!(l.glow > 0)) continue;
      const w = camera.depth ? (camera.depth - (l.z || 0)) / camera.depth : 1, k = z / w;
      const X = (l.x - camera.x) * k * 2 / vw, Y = -(l.y - camera.y) * k * 2 / vh, r = (l.glowRadius || 48) * k;
      gl.uniform4f(gu.uQ, X, Y, r * 2 / vw, r * 2 / vh);
      const c = l.color || [1, 0.82, 0.55];
      gl.uniform4f(gu.uG, c[0], c[1], c[2], l.glow * (l.intensity ?? 1));
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
  }

  return {
    canvas, gl, setPlanes, updatePlane, render,
    info: () => gl.getParameter(gl.getExtension('WEBGL_debug_renderer_info')?.UNMASKED_RENDERER_WEBGL ?? gl.RENDERER),
    destroy: () => { gl.getExtension('WEBGL_lose_context')?.loseContext(); },
  };
}

function program(gl, vs, fs) {
  const p = gl.createProgram();
  for (const [type, src] of [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fs]]) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    gl.attachShader(p, s);
  }
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  return p;
}

function uniforms(gl, p) {
  const out = {};
  for (let i = 0; i < gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS); i++) {
    const nm = gl.getActiveUniform(p, i).name;
    out[nm] = gl.getUniformLocation(p, nm);
  }
  return out;
}

// A texture of a picture (re-used when one is passed back in). Albedo is premultiplied, so planes blend like paper.
function tex(gl, src, premultiply, mips, nearest, t) {
  t = t || gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, t);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, premultiply);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, src);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
  if (mips) gl.generateMipmap(gl.TEXTURE_2D);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, mips ? gl.LINEAR_MIPMAP_LINEAR : gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, nearest ? gl.NEAREST : gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  return t;
}
// -- lightrig.js 1.0.1 end --
  return createLightRig;
})();
