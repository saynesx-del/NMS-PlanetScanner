"use strict";
/* Procedural planet portraits, drawn from each planet's real colours (water, sky, grass, plants, leaves, rock),
   its biome, clouds, rings and moons. Deterministic: a planet (its id) always gets the same picture.
   renderPlanet(p, cssSize) -> data: URL (cached). Pure canvas, no library. */

const PlanetArt = (() => {
  const cache = new Map();

  // ----- small deterministic helpers -----
  function hash(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function rng(seed) {
    let s = seed >>> 0 || 1;
    return () => ((s = Math.imul(s ^ (s >>> 15), 2246822507) + 0x6d2b79f5 >>> 0) / 4294967296);
  }
  function rgb(hex, fallback) {
    const h = /^#[0-9a-f]{6}$/i.test(hex || "") ? hex : fallback;
    const n = parseInt(h.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
  const scale = (c, k) => [c[0] * k, c[1] * k, c[2] * k];
  const clamp01 = (x) => (x < 0 ? 0 : x > 1 ? 1 : x);
  const smooth = (e0, e1, x) => { const t = clamp01((x - e0) / (e1 - e0)); return t * t * (3 - 2 * t); };
  const lum = (c) => 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2];

  // 3D value noise (seamless on a sphere) + fractal sum.
  function makeNoise(seed) {
    const r = rng(seed), perm = new Uint8Array(512), vals = new Float32Array(256);
    const p = [...Array(256).keys()];
    for (let i = 255; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [p[i], p[j]] = [p[j], p[i]]; }
    for (let i = 0; i < 512; i++) perm[i] = p[i & 255];
    for (let i = 0; i < 256; i++) vals[i] = r();
    const v = (i, j, k) => vals[perm[perm[perm[i & 255] + (j & 255)] + (k & 255)]];
    return (x, y, z) => {
      const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
      let fx = x - xi, fy = y - yi, fz = z - zi;
      fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy); fz = fz * fz * (3 - 2 * fz);
      const a = v(xi, yi, zi) + (v(xi + 1, yi, zi) - v(xi, yi, zi)) * fx;
      const b = v(xi, yi + 1, zi) + (v(xi + 1, yi + 1, zi) - v(xi, yi + 1, zi)) * fx;
      const c = v(xi, yi, zi + 1) + (v(xi + 1, yi, zi + 1) - v(xi, yi, zi + 1)) * fx;
      const d = v(xi, yi + 1, zi + 1) + (v(xi + 1, yi + 1, zi + 1) - v(xi, yi + 1, zi + 1)) * fx;
      const e = a + (b - a) * fy, f = c + (d - c) * fy;
      return e + (f - e) * fz;
    };
  }
  function fbm(n, x, y, z, oct) {
    let a = 0.5, f = 1, s = 0, norm = 0;
    for (let i = 0; i < oct; i++) { s += a * n(x * f, y * f, z * f); norm += a; f *= 2.07; a *= 0.5; }
    return s / norm;
  }

  // ----- what a planet looks like, from its data -----
  function style(p) {
    const pal = (p.details && p.details.palettes) || {};
    const slot = (name, k = 0) => pal[name] && pal[name].c && pal[name].c[k];
    const biome = p.biome || "Barren";
    const grass = rgb(p.grass_hex || slot("Grass"), "#6F8F4E");
    const plant = rgb(p.plant_hex || slot("Plant"), "#4E7A3A");
    const leaf = rgb(p.leaf_hex || slot("Leaf"), "#7FA05A");
    const rockDefault = lum(grass) > 120 ? scale(mix(grass, [120, 110, 100], 0.65), 0.75) : mix(grass, [95, 88, 80], 0.6);
    const rock = slot("Rock") ? rgb(slot("Rock")) : rockDefault;
    const sand = slot("Sand") ? rgb(slot("Sand")) : mix(rock, [214, 196, 160], 0.45);
    const water = p.has_water === 0 ? null : rgb(p.water_hex || slot("Water"), "#1E4E7A");
    const sky = rgb(p.sky_hex || slot("Sky"), "#8FC4F2");
    const ring = slot("PlanetRing") ? rgb(slot("PlanetRing")) : mix(sky, [220, 210, 190], 0.5);
    const cloudy = p.cloudiness === "CloudyWithClearSpells" ? 0.6 : p.cloudiness === "ClearWithCloudySpells" ? 0.35 : 0.25;
    let sea = water ? 0.48 : -1;
    if (biome === "Waterworld") sea = 0.6;
    if (biome === "Swamp" && water) sea = 0.52;
    if (biome === "Frozen" || biome === "Blue") sea = water ? 0.44 : -1;
    const noAir = biome === "Dead" || p.size === "Moon" && !water;
    return { biome, grass, plant, leaf, rock, sand, water, sky, ring, cloudy: noAir ? 0 : cloudy, sea, noAir };
  }

  // Colour of the ground at a point: h = height (0-1), m = moisture, lat = latitude (-1..1), n2 = detail noise.
  function ground(s, h, m, lat, n2) {
    switch (s.biome) {
      case "Frozen": {
        const ice = [226, 238, 246], rockc = mix(s.rock, [150, 165, 180], 0.4);
        return h > 0.62 || Math.abs(lat) > 0.55 ? mix(ice, [255, 255, 255], n2 * 0.4) : mix(rockc, ice, smooth(0.35, 0.6, h + n2 * 0.25));
      }
      case "Lava": case "Scorched": {
        const base = s.biome === "Lava" ? mix(s.rock, [40, 26, 20], 0.55) : mix(s.sand, s.rock, 0.4);
        return mix(base, s.rock, smooth(0.5, 0.8, h));
      }
      case "Dead": case "Barren": {
        const base = s.biome === "Dead" ? mix(s.rock, [150, 145, 140], 0.6) : mix(s.sand, s.rock, 0.35);
        // broad highlands/lowlands from the height, only a light grain from the detail noise
        return scale(mix(scale(base, 0.8), mix(base, [255, 250, 240], 0.12), smooth(0.35, 0.7, h)), 0.92 + n2 * 0.16);
      }
      case "Toxic": case "Radioactive": {
        const low = mix(s.grass, s.plant, m);
        return h > 0.72 ? mix(s.rock, low, 0.25) : mix(low, s.leaf, smooth(0.55, 0.9, n2) * 0.5);
      }
      default: {  // Lush, Weird, coloured worlds, swamps, oceans' islands
        const t = s.sea > 0 ? (h - s.sea) / (1 - s.sea) : h;
        if (t < 0.06 && s.water) return s.sand;
        let c = mix(s.grass, s.plant, smooth(0.3, 0.7, m));
        c = mix(c, s.leaf, smooth(0.6, 0.95, n2) * 0.6);
        if (t > 0.55) c = mix(c, s.rock, smooth(0.55, 0.85, t));
        if (t > 0.9 && Math.abs(lat) > 0.3) c = mix(c, [240, 244, 248], 0.7);
        return c;
      }
    }
  }

  // Draw one sphere (planet or moon) into ImageData.
  function sphere(s, seed, R, opts = {}) {
    const S = Math.ceil(R * 2) + 2, img = new ImageData(S, S), d = img.data;
    const n1 = makeNoise(seed), n2 = makeNoise(seed + 101), n3 = makeNoise(seed + 202);
    const r = rng(seed + 7);
    const rot = r() * Math.PI * 2, tilt = (r() - 0.5) * 0.5;
    const off = [r() * 50, r() * 50, r() * 50];
    const L = [-0.55, -0.42, 0.72], Ln = Math.hypot(...L); L[0] /= Ln; L[1] /= Ln; L[2] /= Ln;
    const craters = [];
    if (s.biome === "Dead" || opts.moon || s.biome === "Barren") {
      for (let i = 0; i < (opts.moon ? 7 : 5); i++) {
        const u = r() * 2 - 1, t2 = r() * Math.PI * 2, q = Math.sqrt(1 - u * u);
        craters.push([q * Math.cos(t2), u, q * Math.sin(t2), 0.12 + r() * 0.22]);
      }
    }
    const cr = Math.cos(rot), sr = Math.sin(rot), ct = Math.cos(tilt), st = Math.sin(tilt);
    for (let y = 0; y < S; y++) {
      for (let x = 0; x < S; x++) {
        const dx = (x + 0.5 - S / 2) / R, dy = (y + 0.5 - S / 2) / R, d2 = dx * dx + dy * dy;
        if (d2 > 1) continue;
        const nz = Math.sqrt(1 - d2);
        // texture coordinates: rotate the view normal (spin + axial tilt)
        let tx = dx * cr + nz * sr, tz = -dx * sr + nz * cr, ty = dy;
        const ty2 = ty * ct - tz * st; tz = ty * st + tz * ct; ty = ty2;
        const lat = ty;
        let col, emissive = 0, wet = false;
        if (s.biome === "GasGiant") {
          const turb = fbm(n1, tx * 2 + off[0], ty * 2 + off[1], tz * 2 + off[2], 4);
          const band = Math.sin(ty * 9 + turb * 4.5) * 0.5 + 0.5;
          col = mix(mix(s.grass, s.leaf, band), s.sky, smooth(0.6, 1, fbm(n2, tx * 4, ty * 14, tz * 4, 3)) * 0.35);
        } else {
          const h = fbm(n1, tx * 1.7 + off[0], ty * 1.7 + off[1], tz * 1.7 + off[2], 5);
          const m = fbm(n2, tx * 2.4 + off[1], ty * 2.4 + off[2], tz * 2.4 + off[0], 3);
          const det = n3(tx * 9 + off[2], ty * 9, tz * 9 + off[0]);
          if (s.sea > 0 && h < s.sea) {
            const depth = clamp01((s.sea - h) / 0.18);
            const shallow = mix(s.water, [255, 255, 255], 0.3), deepc = mix(scale(s.water, 0.75), s.sky, 0.08);
            col = mix(shallow, deepc, Math.sqrt(depth));
            wet = true;
          } else {
            col = ground(s, h, m, lat, det);
          }
          if (s.biome === "Lava") {
            const ridge = 1 - Math.abs(2 * fbm(n3, tx * 3 + 5, ty * 3, tz * 3, 3) - 1);
            emissive = smooth(0.93, 0.99, ridge);
          }
          for (const [cx, cy, cz, rad] of craters) {
            const dist = Math.hypot(tx - cx, ty - cy, tz - cz);
            if (dist < rad) col = scale(col, dist > rad * 0.8 ? 1.18 : 0.78 + 0.2 * dist / rad);
          }
        }
        // light: soft terminator, a little ambient
        const lam = Math.max(0, dx * L[0] + dy * L[1] + nz * L[2]);
        let shade = 0.1 + 0.95 * Math.pow(lam, 0.85);
        let c = scale(col, shade);
        if (wet) {  // sun glint on water
          const hx = L[0], hy = L[1], hz = L[2] + 1, hn = Math.hypot(hx, hy, hz);
          const spec = Math.pow(Math.max(0, (dx * hx + dy * hy + nz * hz) / hn), 60) * 0.55;
          c = mix(c, [255, 255, 255], spec);
        }
        // clouds
        if (s.cloudy > 0) {
          const warp = fbm(n2, tx * 1.3 + 3, ty * 1.3, tz * 1.3 - 3, 2) * 1.6;
          const cl = fbm(n3, tx * 2.2 + warp + off[0] + 9, ty * 5 + off[1], tz * 2.2 - warp + off[2], 5);
          const a = smooth(0.58 - s.cloudy * 0.18, 0.78 - s.cloudy * 0.12, cl) * (0.35 + s.cloudy * 0.45);
          c = mix(c, scale([250, 252, 255], 0.15 + 0.9 * lam), a);
        }
        if (emissive) c = mix(c, [255, 90 + emissive * 90, 30], emissive * 0.95);
        // atmosphere: the rim takes the sky colour
        if (!s.noAir) c = mix(c, scale(s.sky, 0.35 + 0.8 * lam), Math.pow(1 - nz, 2.2) * 0.75);
        const i = (y * S + x) * 4;
        // anti-aliased edge
        const edge = clamp01((1 - Math.sqrt(d2)) * R * 1.4);
        d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2]; d[i + 3] = 255 * edge;
      }
    }
    const cv = document.createElement("canvas"); cv.width = cv.height = S;
    cv.getContext("2d").putImageData(img, 0, 0);
    return cv;
  }

  function drawRings(ctx, s, cx, cy, R, front) {
    const [r, g, b] = s.ring;
    for (const [w, a, k] of [[R * 0.22, 0.28, 1.0], [R * 0.08, 0.55, 0.93], [R * 0.05, 0.4, 1.08]]) {
      ctx.save();
      ctx.translate(cx, cy); ctx.rotate(-0.32); ctx.scale(1, 0.26);
      ctx.beginPath();
      if (front) ctx.ellipse(0, 0, R * 1.75 * k, R * 1.75 * k, 0, 0, Math.PI);
      else ctx.ellipse(0, 0, R * 1.75 * k, R * 1.75 * k, 0, Math.PI, Math.PI * 2);
      ctx.restore();
      ctx.lineWidth = w; ctx.strokeStyle = `rgba(${r | 0},${g | 0},${b | 0},${a})`; ctx.stroke();
    }
  }

  function render(p, cssSize) {
    const key = `${p.id}|${cssSize}|${p.water_hex}|${p.has_water}|${p.own_moons}`;
    if (cache.has(key)) return cache.get(key);
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const W = Math.round(cssSize * dpr), s = style(p), seed = hash(String(p.id || p.glyphs || p.name || "x"));
    const sizeK = { Moon: 0.62, Small: 0.8, Medium: 0.9, Large: 1, Giant: 1.08 }[p.size] || 0.9;
    const moons = Math.min(2, p.own_moons || 0);
    const R = W * (p.rings ? 0.27 : moons ? 0.32 : 0.4) * sizeK;
    const cx = W / 2 - (moons ? W * 0.06 : 0), cy = W / 2 + (moons ? W * 0.04 : 0);
    const cv = document.createElement("canvas"); cv.width = cv.height = W;
    const ctx = cv.getContext("2d");
    if (!s.noAir) {  // atmosphere halo
      const g = ctx.createRadialGradient(cx, cy, R * 0.92, cx, cy, R * 1.28);
      const [r, gg, b] = s.sky;
      g.addColorStop(0, `rgba(${r | 0},${gg | 0},${b | 0},0.5)`); g.addColorStop(1, `rgba(${r | 0},${gg | 0},${b | 0},0)`);
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, R * 1.3, 0, Math.PI * 2); ctx.fill();
    }
    if (p.rings) drawRings(ctx, s, cx, cy, R, false);
    const body = sphere(s, seed, R);
    ctx.drawImage(body, cx - body.width / 2, cy - body.height / 2);
    if (p.rings) drawRings(ctx, s, cx, cy, R, true);
    const moonStyle = { ...s, biome: "Dead", noAir: true, cloudy: 0, sea: -1, rock: mix(s.rock, [170, 168, 165], 0.6), sand: [190, 186, 180] };
    const spots = [[1.28, -0.72, 0.3], [-1.12, 0.82, 0.22]];
    for (let i = 0; i < moons; i++) {
      const [ox, oy, k] = spots[i];
      const mcv = sphere(moonStyle, seed + 991 * (i + 1), Math.max(3, R * k), { moon: true });
      ctx.drawImage(mcv, cx + R * ox - mcv.width / 2, cy + R * oy - mcv.height / 2);
    }
    const url = cv.toDataURL();
    if (cache.size > 600) cache.clear();
    cache.set(key, url);
    return url;
  }

  // Star portrait for the system page.
  function star(type, cssSize) {
    const key = `star|${type}|${cssSize}`;
    if (cache.has(key)) return cache.get(key);
    const C = { Yellow: [255, 214, 110], Red: [255, 110, 90], Green: [110, 230, 140], Blue: [120, 190, 255], Purple: [190, 130, 255] }[type] || [255, 214, 110];
    const dpr = Math.min(2, window.devicePixelRatio || 1), W = Math.round(cssSize * dpr), cx = W / 2, R = W * 0.24;
    const cv = document.createElement("canvas"); cv.width = cv.height = W;
    const ctx = cv.getContext("2d");
    const glow = ctx.createRadialGradient(cx, cx, R * 0.5, cx, cx, W / 2);
    glow.addColorStop(0, `rgba(${C},0.55)`); glow.addColorStop(0.45, `rgba(${C},0.14)`); glow.addColorStop(1, `rgba(${C},0)`);
    ctx.fillStyle = glow; ctx.fillRect(0, 0, W, W);
    const core = ctx.createRadialGradient(cx - R * 0.25, cx - R * 0.25, R * 0.1, cx, cx, R);
    core.addColorStop(0, "rgb(255,255,245)"); core.addColorStop(0.55, `rgb(${C})`); core.addColorStop(1, `rgb(${C.map((v) => v * 0.7 | 0)})`);
    ctx.fillStyle = core; ctx.beginPath(); ctx.arc(cx, cx, R, 0, Math.PI * 2); ctx.fill();
    const url = cv.toDataURL();
    cache.set(key, url);
    return url;
  }

  return { render, star };
})();
