/* Deterministic 1920 × 1080 canvas scenes. The caller owns clearing, captions,
   evidence footage, font loading, and crossfades; every drawing preserves alpha. */
(function () {
  "use strict";

  const W = 1920;
  const H = 1080;
  const C = Object.freeze({
    ink: "#020b0e",
    teal: "#005670",
    lime: "#c0e021",
    paper: "#f3f7f5",
    muted: "#a9c2c7",
    quiet: "#668790",
    amber: "#ebbd73",
    red: "#ee8178",
    panel: "#071b22",
  });
  const DISPLAY = '"Barlow Condensed", sans-serif';
  const BODY = '"DM Sans", sans-serif';
  const clamp = (v, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v));
  const lerp = (a, b, p) => a + (b - a) * p;
  const ease = (v) => {
    const p = clamp(v);
    return p * p * p * (p * (p * 6 - 15) + 10);
  };
  const at = (t, start, length = 0.6) => ease((t - start) / length);
  const spring = (v) => {
    const p = clamp(v);
    const response = (x) => 1 - Math.exp(-7 * x) * (Math.cos(8 * x) + 0.4 * Math.sin(8 * x));
    return response(p) / response(1);
  };
  const duration = (s) => Math.max(0.1, Number(s.duration || s.targetSeconds) || 4);
  const rgba = (hex, a) => {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${clamp(a)})`;
  };
  const normalize = (s) => String(s).toLowerCase().replace(/[’']/g, "").replace(/[^a-z0-9]+/g, " ").trim();

  // Word timings are narration-relative, not offsets into the complete film.
  function cue(s, phrase, fallback, occurrence = 0) {
    const wanted = normalize(phrase).split(" ");
    const words = [];
    for (const entry of s.words || []) {
      const start = Number(entry.start);
      if (!Number.isFinite(start)) continue;
      for (const word of normalize(entry.word).split(" ")) {
        if (word) words.push({ word, start });
      }
    }
    for (let i = 0; i <= words.length - wanted.length; i += 1) {
      if (wanted.every((word, j) => words[i + j].word === word)) {
        if (occurrence-- === 0) return clamp(words[i].start, 0, duration(s));
      }
    }
    return duration(s) * fallback;
  }

  function alpha(ctx, amount, draw) {
    if (amount <= 0) return;
    ctx.save();
    ctx.globalAlpha *= clamp(amount);
    draw();
    ctx.restore();
  }

  function reveal(ctx, amount, draw, lift = 22, blur = 3) {
    if (amount <= 0) return;
    ctx.save();
    ctx.globalAlpha *= clamp(amount);
    ctx.translate(0, (1 - amount) * lift);
    if (amount < 0.995 && blur) ctx.filter = `blur(${((1 - amount) * blur).toFixed(3)}px)`;
    draw();
    ctx.restore();
  }

  function round(ctx, x, y, w, h, r = 20, begin = true) {
    r = Math.max(0, Math.min(r, w / 2, h / 2));
    if (begin) ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  function polygon(ctx, points) {
    ctx.beginPath();
    points.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
  }

  function line(ctx, points, color, width = 2) {
    ctx.save();
    ctx.beginPath();
    points.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.stroke();
    ctx.restore();
  }

  function text(ctx, value, x, y, size, color = C.paper, options = {}) {
    ctx.save();
    const family = options.body ? BODY : DISPLAY;
    const weight = options.body && !options.bold ? 400 : 700;
    ctx.font = `${weight} ${size}px ${family}`;
    if (options.maxWidth) {
      const measured = ctx.measureText(value).width;
      if (measured > options.maxWidth) {
        size *= options.maxWidth / measured;
        ctx.font = `${weight} ${size}px ${family}`;
      }
    }
    ctx.textAlign = options.align || "left";
    ctx.textBaseline = "alphabetic";
    ctx.fillStyle = color;
    ctx.fillText(value, x, y);
    ctx.restore();
  }

  function label(ctx, value, x, y, color = C.muted, size = 19, tracking = 2.5) {
    ctx.save();
    ctx.font = `700 ${size}px ${BODY}`;
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
    ctx.fillStyle = color;
    for (const letter of value) {
      ctx.fillText(letter, x, y);
      x += ctx.measureText(letter).width + tracking;
    }
    ctx.restore();
  }

  function wrapped(ctx, value, x, y, maxWidth, size, color, leading = 1.4, bold = false) {
    ctx.save();
    ctx.font = `${bold ? 700 : 400} ${size}px ${BODY}`;
    let row = "";
    let baseline = y;
    for (const word of value.split(" ")) {
      const candidate = row ? `${row} ${word}` : word;
      if (row && ctx.measureText(candidate).width > maxWidth) {
        text(ctx, row, x, baseline, size, color, { body: true, bold });
        baseline += size * leading;
        row = word;
      } else {
        row = candidate;
      }
    }
    if (row) text(ctx, row, x, baseline, size, color, { body: true, bold });
    ctx.restore();
    return baseline;
  }

  function glow(ctx, x, y, rx, ry, color, amount) {
    if (amount <= 0) return;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(rx, ry);
    const g = ctx.createRadialGradient(0, 0, 0, 0, 0, 1);
    g.addColorStop(0, rgba(color, amount));
    g.addColorStop(0.4, rgba(color, amount * 0.42));
    g.addColorStop(1, rgba(color, 0));
    ctx.fillStyle = g;
    ctx.fillRect(-1, -1, 2, 2);
    ctx.restore();
  }

  function camera(ctx, pose, draw) {
    ctx.save();
    ctx.translate(W / 2, H / 2);
    ctx.scale(pose.zoom || 1, pose.zoom || 1);
    ctx.rotate(pose.roll || 0);
    ctx.translate(-(pose.x === undefined ? W / 2 : pose.x), -(pose.y === undefined ? H / 2 : pose.y));
    draw();
    ctx.restore();
  }

  // Orthographic plane axes plus depth scaling keep type crisp on oblique faces.
  function plane(ctx, p, draw) {
    const yaw = p.yaw || 0;
    const pitch = p.pitch || 0;
    const roll = p.roll || 0;
    const scale = (p.scale || 1) * 1800 / (1800 + (p.z || 0));
    const cr = Math.cos(roll);
    const sr = Math.sin(roll);
    const ux = Math.cos(yaw);
    const vx = Math.sin(yaw) * Math.sin(pitch);
    const vy = Math.cos(pitch);
    ctx.save();
    ctx.transform(
      ux * cr * scale,
      ux * sr * scale,
      (vx * cr - vy * sr) * scale,
      (vx * sr + vy * cr) * scale,
      p.x, p.y
    );
    ctx.translate(-p.w / 2, -p.h / 2);
    draw(p.w, p.h);
    ctx.restore();
  }

  function panel(ctx, p, draw) {
    alpha(ctx, p.alpha === undefined ? 1 : p.alpha, () => {
      plane(ctx, p, (w, h) => {
        const r = p.radius || 24;
        const depth = p.depth === undefined ? 13 : p.depth;
        round(ctx, -depth * 0.45, depth * 0.7, w + depth * 0.5, h, r);
        ctx.fillStyle = p.light ? "#b3c8c8" : "#021116";
        ctx.fill();
        const material = ctx.createLinearGradient(0, 0, w * 0.9, h);
        material.addColorStop(0, p.light ? "#ffffff" : "#0e303a");
        material.addColorStop(0.52, p.light ? C.paper : C.panel);
        material.addColorStop(1, p.light ? "#dce8e5" : "#031016");
        round(ctx, 0, 0, w, h, r);
        ctx.shadowColor = "rgba(0,0,0,0.46)";
        ctx.shadowBlur = 44;
        ctx.shadowOffsetY = 25;
        ctx.fillStyle = material;
        ctx.fill();
        ctx.shadowColor = "rgba(0,0,0,0)";
        ctx.shadowBlur = 0;
        ctx.shadowOffsetY = 0;
        const edge = ctx.createLinearGradient(0, 0, w, h);
        edge.addColorStop(0, rgba(p.accent || C.paper, p.light ? 0.85 : 0.47));
        edge.addColorStop(0.42, rgba(C.muted, 0.08));
        edge.addColorStop(1, rgba(p.accent || C.teal, 0.32));
        ctx.strokeStyle = edge;
        ctx.lineWidth = 1.6;
        ctx.stroke();
        ctx.save();
        round(ctx, 1, 1, w - 2, h - 2, r - 1);
        ctx.clip();
        draw(w, h);
        ctx.restore();
      });
    });
  }

  function ring(ctx, x, y, w, h, thickness, radius) {
    round(ctx, x, y, w, h, radius);
    round(ctx, x + thickness, y + thickness, w - thickness * 2, h - thickness * 2, Math.max(8, radius - thickness * 0.65), false);
  }

  function gate(ctx, p) {
    const light = p.light === undefined ? 0.7 : p.light;
    alpha(ctx, p.alpha === undefined ? 1 : p.alpha, () => {
      glow(ctx, p.x, p.y + p.h * 0.52, p.w * 0.78, 62, C.teal, light * 0.24);
      plane(ctx, p, (w, h) => {
        const thickness = p.thickness || 34;
        const depth = p.depth === undefined ? 44 : p.depth;
        const radius = Math.min(40, h * 0.09);
        ring(ctx, depth * 0.72, -depth * 0.55, w, h, thickness, radius);
        ctx.fillStyle = "#06212a";
        ctx.fill("evenodd");
        ctx.strokeStyle = rgba(C.teal, 0.48);
        ctx.lineWidth = 1.6;
        ctx.stroke();
        polygon(ctx, [[radius, 0], [w - radius, 0], [w - radius + depth * 0.72, -depth * 0.55], [radius + depth * 0.72, -depth * 0.55]]);
        ctx.fillStyle = "#17434c";
        ctx.fill();
        polygon(ctx, [[w, radius], [w, h - radius], [w + depth * 0.72, h - radius - depth * 0.55], [w + depth * 0.72, radius - depth * 0.55]]);
        ctx.fillStyle = "#03171d";
        ctx.fill();
        const face = ctx.createLinearGradient(0, 0, w, h);
        face.addColorStop(0, "#254b51");
        face.addColorStop(0.3, "#0c303c");
        face.addColorStop(0.7, "#04181e");
        face.addColorStop(1, "#15404a");
        ring(ctx, 0, 0, w, h, thickness, radius);
        ctx.fillStyle = face;
        ctx.shadowColor = "rgba(0,0,0,0.4)";
        ctx.shadowBlur = 35;
        ctx.shadowOffsetY = 15;
        ctx.fill("evenodd");
        ctx.shadowColor = "rgba(0,0,0,0)";
        ctx.shadowBlur = 0;
        ctx.shadowOffsetY = 0;
        const rim = ctx.createLinearGradient(0, h, w, 0);
        rim.addColorStop(0, rgba(C.teal, 0.14));
        rim.addColorStop(0.45, rgba(C.paper, 0.1 + light * 0.18));
        rim.addColorStop(0.78, rgba(C.lime, light * 0.86));
        rim.addColorStop(1, rgba(C.paper, light * 0.84));
        ctx.strokeStyle = rim;
        ctx.lineWidth = 2;
        ctx.stroke();
        round(ctx, thickness + 7, thickness + 7, w - thickness * 2 - 14, h - thickness * 2 - 14, radius - 9);
        ctx.strokeStyle = rgba(C.lime, light * 0.2);
        ctx.lineWidth = 1;
        ctx.stroke();
        if (p.sweep !== undefined && p.sweep > 0 && p.sweep < 1) {
          ctx.save();
          ring(ctx, 0, 0, w, h, thickness, radius);
          ctx.clip("evenodd");
          const x = lerp(-w, w * 2, p.sweep);
          const sweep = ctx.createLinearGradient(x - 130, 0, x + 130, h * 0.3);
          sweep.addColorStop(0, rgba(C.paper, 0));
          sweep.addColorStop(0.48, rgba(C.paper, 0.025));
          sweep.addColorStop(0.57, rgba(C.paper, 0.27));
          sweep.addColorStop(1, rgba(C.paper, 0));
          ctx.fillStyle = sweep;
          ctx.fillRect(0, 0, w, h);
          ctx.restore();
        }
        if (p.barrier) {
          line(ctx, [[thickness + 8, h * 0.55], [w - thickness - 8, h * 0.55]], rgba(C.amber, p.barrier * 0.9), 2.5);
        }
      });
    });
  }

  function tokenPath(ctx, w, h) {
    const r = w * 0.09;
    ctx.beginPath();
    ctx.moveTo(r, 0);
    ctx.lineTo(w * 0.69, 0);
    ctx.lineTo(w, h * 0.235);
    ctx.lineTo(w, h - r);
    ctx.quadraticCurveTo(w, h, w - r, h);
    ctx.lineTo(r, h);
    ctx.quadraticCurveTo(0, h, 0, h - r);
    ctx.lineTo(0, r);
    ctx.quadraticCurveTo(0, 0, r, 0);
    ctx.closePath();
  }

  function mark(ctx, x, y, size, color) {
    ctx.save();
    ctx.translate(x, y);
    ctx.fillStyle = color;
    round(ctx, -size * 0.3, -size * 0.4, size * 0.17, size * 0.8, size * 0.04);
    ctx.fill();
    round(ctx, size * 0.1, -size * 0.4, size * 0.17, size * 0.53, size * 0.04);
    ctx.fill();
    polygon(ctx, [[size * 0.1, size * 0.23], [size * 0.27, size * 0.23], [size * 0.46, size * 0.4], [size * 0.1, size * 0.4]]);
    ctx.fill();
    ctx.restore();
  }

  function token(ctx, x, y, size, options = {}) {
    const color = options.color || C.lime;
    alpha(ctx, options.alpha === undefined ? 1 : options.alpha, () => {
      glow(ctx, x, y + size * 0.15, size * 0.9, size * 0.78, color, 0.1);
      plane(ctx, {
        x, y, w: size * 0.78, h: size,
        yaw: options.yaw === undefined ? -0.22 : options.yaw,
        pitch: options.pitch === undefined ? 0.1 : options.pitch,
        roll: options.roll === undefined ? -0.08 : options.roll,
        z: options.z || 0,
      }, (w, h) => {
        ctx.save();
        ctx.translate(-size * 0.038, size * 0.045);
        tokenPath(ctx, w, h);
        ctx.fillStyle = "#244d3c";
        ctx.fill();
        ctx.restore();
        tokenPath(ctx, w, h);
        const face = ctx.createLinearGradient(0, 0, w, h);
        face.addColorStop(0, C.paper);
        face.addColorStop(0.12, color);
        face.addColorStop(1, color === C.lime ? "#88a623" : color);
        ctx.fillStyle = face;
        ctx.shadowColor = "rgba(0,0,0,0.4)";
        ctx.shadowBlur = size * 0.2;
        ctx.shadowOffsetY = size * 0.14;
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.shadowOffsetY = 0;
        ctx.shadowColor = "rgba(0,0,0,0)";
        ctx.strokeStyle = rgba(C.paper, 0.66);
        ctx.lineWidth = Math.max(1, size * 0.009);
        ctx.stroke();
        line(ctx, [[w * 0.69, 2], [w * 0.69, h * 0.235], [w - 2, h * 0.235]], rgba(C.ink, 0.25), Math.max(1, size * 0.01));
        mark(ctx, w * 0.48, h * 0.49, size * 0.39, C.ink);
        if (size >= 125) label(ctx, "REQUEST", w * 0.16, h * 0.83, rgba(C.ink, 0.7), size * 0.065, size * 0.015);
      });
    });
  }

  function cubic(points, p) {
    const q = 1 - p;
    return [
      q * q * q * points[0][0] + 3 * q * q * p * points[1][0] + 3 * q * p * p * points[2][0] + p * p * p * points[3][0],
      q * q * q * points[0][1] + 3 * q * q * p * points[1][1] + 3 * q * p * p * points[2][1] + p * p * p * points[3][1],
    ];
  }

  function route(ctx, points, progress = 0, color = C.lime, width = 2.4) {
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(...points[0]);
    ctx.bezierCurveTo(...points[1], ...points[2], ...points[3]);
    ctx.strokeStyle = rgba(C.muted, 0.18);
    ctx.lineWidth = width;
    ctx.lineCap = "round";
    ctx.stroke();
    if (progress > 0) {
      ctx.beginPath();
      ctx.moveTo(...points[0]);
      for (let i = 1; i <= 48; i += 1) ctx.lineTo(...cubic(points, clamp(progress) * i / 48));
      ctx.strokeStyle = rgba(color, 0.72);
      ctx.shadowColor = rgba(color, 0.38);
      ctx.shadowBlur = 12;
      ctx.lineWidth = width;
      ctx.stroke();
    }
    ctx.restore();
  }

  function icon(ctx, name, x, y, size, color = C.paper) {
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(size / 100, size / 100);
    ctx.lineWidth = 3.7;
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    if (name === "person" || name === "human") {
      ctx.arc(0, -19, 17, 0, Math.PI * 2);
      ctx.moveTo(-34, 39);
      ctx.bezierCurveTo(-34, 2, 34, 2, 34, 39);
      ctx.moveTo(-34, 39);
      ctx.lineTo(34, 39);
    } else if (name === "phone") {
      ctx.moveTo(-32, -37);
      ctx.bezierCurveTo(-52, -8, -6, 49, 30, 36);
      ctx.lineTo(42, 21);
      ctx.lineTo(20, 4);
      ctx.lineTo(8, 18);
      ctx.bezierCurveTo(-7, 12, -17, -1, -19, -13);
      ctx.lineTo(-5, -23);
      ctx.lineTo(-19, -43);
      ctx.closePath();
    } else if (name === "catalog") {
      ctx.moveTo(0, -26);
      ctx.quadraticCurveTo(-23, -42, -43, -30);
      ctx.lineTo(-43, 32);
      ctx.quadraticCurveTo(-21, 22, 0, 37);
      ctx.quadraticCurveTo(23, 22, 43, 32);
      ctx.lineTo(43, -30);
      ctx.quadraticCurveTo(22, -42, 0, -26);
      ctx.lineTo(0, 37);
      ctx.moveTo(-31, -13);
      ctx.lineTo(-13, -8);
      ctx.moveTo(13, -8);
      ctx.lineTo(31, -13);
      ctx.moveTo(-31, 2);
      ctx.lineTo(-13, 7);
      ctx.moveTo(13, 7);
      ctx.lineTo(31, 2);
    } else if (name === "browser") {
      round(ctx, -44, -34, 88, 69, 7);
      ctx.moveTo(-43, -15);
      ctx.lineTo(43, -15);
      ctx.moveTo(-29, -25);
      ctx.lineTo(-22, -25);
      ctx.moveTo(-24, 0);
      ctx.lineTo(-4, 0);
      ctx.lineTo(-4, 21);
      ctx.lineTo(-24, 21);
      ctx.closePath();
      ctx.moveTo(9, 1);
      ctx.lineTo(29, 1);
      ctx.moveTo(9, 13);
      ctx.lineTo(24, 13);
    } else if (name === "limit") {
      ctx.moveTo(-39, 27);
      ctx.lineTo(39, 27);
      ctx.moveTo(-31, 27);
      ctx.lineTo(-31, 5);
      ctx.moveTo(-10, 27);
      ctx.lineTo(-10, -10);
      ctx.moveTo(11, 27);
      ctx.lineTo(11, -26);
      ctx.moveTo(32, 27);
      ctx.lineTo(32, -39);
      ctx.moveTo(-42, -20);
      ctx.lineTo(42, -20);
    } else if (name === "quote") {
      round(ctx, -37, -36, 74, 72, 8);
      ctx.moveTo(-20, -16);
      ctx.lineTo(19, -16);
      ctx.moveTo(-20, 0);
      ctx.lineTo(3, 0);
      ctx.moveTo(7, 19);
      ctx.lineTo(16, 27);
      ctx.lineTo(31, 7);
    } else if (name === "record") {
      ctx.moveTo(-29, -40);
      ctx.lineTo(11, -40);
      ctx.lineTo(31, -20);
      ctx.lineTo(31, 40);
      ctx.lineTo(-29, 40);
      ctx.closePath();
      ctx.moveTo(11, -40);
      ctx.lineTo(11, -20);
      ctx.lineTo(31, -20);
      ctx.moveTo(-13, -2);
      ctx.lineTo(14, -2);
      ctx.moveTo(-13, 13);
      ctx.lineTo(14, 13);
      ctx.moveTo(-13, 27);
      ctx.lineTo(4, 27);
    } else if (name === "audit") {
      for (let i = 0; i < 3; i += 1) {
        const yy = -27 + i * 27;
        ctx.moveTo(-33, yy);
        ctx.lineTo(-26, yy + 7);
        ctx.lineTo(-14, yy - 7);
        ctx.moveTo(1, yy);
        ctx.lineTo(35, yy);
      }
    } else {
      ctx.stroke();
      mark(ctx, 0, 0, 72, color);
      ctx.restore();
      return;
    }
    ctx.stroke();
    ctx.restore();
  }

  function phaseWeights(t, times, draw, transition = 0.36) {
    const exitLength = transition * 0.45;
    times.forEach((start, i) => {
      // Finish the previous label's exit before entering the same text slot.
      const delay = i > 0 ? exitLength : 0;
      const incoming = at(t, start + delay, transition - delay);
      const outgoing = i + 1 < times.length ? at(t, times[i + 1], exitLength) : 0;
      if (incoming * (1 - outgoing) > 0) draw(i, incoming * (1 - outgoing), incoming, outgoing);
    });
  }

  function background(ctx, time) {
    const t = Math.min(Math.max(0, Number(time) || 0), 114);
    ctx.save();
    const base = ctx.createLinearGradient(0, 0, 1600, H);
    base.addColorStop(0, C.ink);
    base.addColorStop(0.58, "#04161c");
    base.addColorStop(1, "#020d11");
    ctx.fillStyle = base;
    ctx.fillRect(0, 0, W, H);
    glow(ctx, 1270 + Math.sin(t * 0.075) * 65, 365, 970, 610, C.teal, 0.28);
    glow(ctx, 1470, 754, 610, 220, C.lime, 0.035);
    glow(ctx, 550, 930, 870, 180, C.teal, 0.1);
    const horizon = ctx.createLinearGradient(0, 0, W, 0);
    horizon.addColorStop(0, rgba(C.teal, 0));
    horizon.addColorStop(0.64, rgba(C.muted, 0.055));
    horizon.addColorStop(1, rgba(C.teal, 0));
    line(ctx, [[0, 869], [1920, 869]], horizon, 1);
    const vignette = ctx.createRadialGradient(960, 420, 310, 960, 480, 1140);
    vignette.addColorStop(0, rgba(C.ink, 0));
    vignette.addColorStop(1, rgba(C.ink, 0.5));
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, W, H);
    ctx.restore();
  }

  function hook(ctx, s, t) {
    const d = duration(s);
    const push = at(t, 0, d);
    camera(ctx, { x: lerp(960, 985, push), y: 540, zoom: lerp(1, 1.035, push) }, () => {
      glow(ctx, 1385, 450, 450, 520, C.teal, 0.27);
      gate(ctx, { x: 1430, y: 485, w: 420, h: 546, yaw: -0.28, pitch: 0.1, roll: -0.025, light: 0.72, sweep: at(t, 0.45, 2.3) });
      const path = [[1060, 845], [1075, 665], [1270, 692], [1330, 548]];
      const travel = lerp(0.22, 0.88, at(t, 0.15, d - 0.35));
      route(ctx, path, travel, C.lime, 2.5);
      const pos = cubic(path, travel);
      token(ctx, pos[0], pos[1], lerp(187, 159, push), { yaw: lerp(-0.38, -0.12, push), roll: lerp(-0.15, -0.05, push) });
    });
    reveal(ctx, at(t, 0, 0.42), () => label(ctx, "VALIO AIMO  /  A NEW BUYING INTERFACE", 130, 174));
    reveal(ctx, at(t, cue(s, "Who", 0.01), 0.5), () => text(ctx, "Who places", 124, 359, 156));
    reveal(ctx, at(t, cue(s, "your next", 0.23) - 0.08, 0.48), () => text(ctx, "your next", 124, 510, 156));
    reveal(ctx, at(t, cue(s, "wholesale order", 0.51) - 0.09, 0.52), () => text(ctx, "wholesale order?", 124, 660, 143, C.lime, { maxWidth: 920 }));
    alpha(ctx, at(t, 0.55, 0.8), () => {
      line(ctx, [[131, 767], [181, 767]], C.lime, 3);
      label(ctx, "THE REQUEST IS ALREADY ON ITS WAY.", 203, 774, C.muted, 18, 1.6);
    });
  }

  function history(ctx, s, t) {
    const d = duration(s);
    const times = [
      Math.max(0, cue(s, "person", 0.08) - 0.16),
      cue(s, "phone call", 0.31) - 0.12,
      cue(s, "catalog", 0.54) - 0.12,
      cue(s, "webshop", 0.77) - 0.12,
    ];
    const names = ["A person.", "A phone call.", "A catalog.", "A webshop."];
    const icons = ["person", "phone", "catalog", "browser"];
    const web = at(t, times[3], 0.68);
    const tilt = at(t, 0, d - 0.35);
    reveal(ctx, at(t, 0, 0.4), () => label(ctx, "FOR DECADES", 132, 197));
    phaseWeights(t, times, (i, a, incoming, outgoing) => {
      alpha(ctx, a, () => {
        ctx.save();
        ctx.translate(0, (1 - incoming) * 28 - outgoing * 18);
        text(ctx, names[i], 126, 435, 154, C.paper, { maxWidth: 880 });
        ctx.restore();
      });
    });
    text(ctx, "One order. Different interfaces.", 133, 533, 33, C.muted, { body: true });
    times.forEach((start, i) => {
      const active = at(t, start, 0.3);
      line(ctx, [[134 + i * 101, 645], [208 + i * 101, 645]], rgba(C.muted, 0.2), 3);
      line(ctx, [[134 + i * 101, 645], [134 + i * 101 + 74 * active, 645]], C.lime, 3);
      text(ctx, String(i + 1).padStart(2, "0"), 134 + i * 101, 687, 24, active > 0.5 ? C.paper : C.quiet, { body: true });
    });
    const path = [[1060, 792], [1130, 791], [1515, 791], [1650, 792]];
    route(ctx, path, at(t, 0, d), C.lime, 2);
    panel(ctx, {
      x: lerp(1365, 1350, tilt), y: 480,
      w: lerp(430, 594, web), h: lerp(452, 414, web),
      yaw: lerp(-0.36, -0.055, tilt), pitch: lerp(0.19, 0.045, tilt),
      roll: lerp(0.025, 0, tilt), light: true, depth: 22, accent: C.lime,
    }, (w, h) => {
      label(ctx, "A WHOLESALE ORDER", 35, 44, C.teal, 17, 2);
      line(ctx, [[35, 66], [w - 35, 66]], rgba(C.teal, 0.17), 1);
      phaseWeights(t, times, (i, a, incoming) => {
        alpha(ctx, a, () => {
          icon(ctx, icons[i], w / 2, h * 0.51, lerp(156, 176, incoming), C.teal);
          text(ctx, names[i].slice(2, -1).toUpperCase(), w / 2, h - 57, 19, C.teal, { body: true, bold: true, align: "center" });
        });
      });
      mark(ctx, w - 43, h - 36, 19, rgba(C.teal, 0.4));
    });
    token(ctx, lerp(1090, 1570, at(t, 0.1, d - 0.25)), 792, 49, { roll: 0, yaw: 0 });
  }

  function agent(ctx, s, t) {
    const ask = at(t, cue(s, "who", 0.51) - 0.12, 0.62);
    const arrival = spring(clamp((t - cue(s, "agent", 0.15) + 0.3) / 1.7));
    const path = [[1030, 724], [1110, 725], [1240, 501], [1400, 501]];
    gate(ctx, { x: 1510, y: 488, w: 350, h: 459, yaw: -0.23, pitch: 0.05, light: lerp(0.34, 0.88, ask), barrier: ask, sweep: at(t, 0.5, 1.8) });
    route(ctx, path, clamp(lerp(0.07, 0.73, arrival)), C.lime);
    const pos = cubic(path, clamp(lerp(0.07, 0.73, arrival)));
    token(ctx, pos[0], pos[1], 151, { roll: lerp(-0.15, -0.035, clamp(arrival)), yaw: -0.14 });
    reveal(ctx, at(t, 0, 0.45), () => label(ctx, "THE NEXT INTERFACE", 131, 185));
    reveal(ctx, at(t, cue(s, "Next", 0.015), 0.54), () => text(ctx, "Next, an agent.", 124, 395, 156, C.paper, { maxWidth: 1050 }));
    reveal(ctx, ask, () => {
      text(ctx, "Who sets the rules?", 127, 569, 113, C.lime, { maxWidth: 1030 });
      text(ctx, "A request is not permission.", 134, 662, 32, C.muted, { body: true });
    });
    alpha(ctx, ask, () => {
      line(ctx, [[1368, 790], [1660, 790]], rgba(C.amber, 0.6), 2);
      label(ctx, "OWNER-DEFINED AUTHORITY", 1338, 831, C.amber, 17, 1.45);
    });
  }

  function hero(ctx, s, t) {
    const d = duration(s);
    const opening = at(t, cue(s, "open", 0.17) - 0.05, 0.68);
    const terms = at(t, cue(s, "On Valio", 0.52) - 0.08, 0.72);
    const push = at(t, 0, d - 0.2);
    camera(ctx, { x: lerp(960, 974, push), y: 540, zoom: lerp(1, 1.025, push) }, () => {
      glow(ctx, 1460, 458, 560, 495, C.teal, 0.36);
      const path = [[1130, 799], [1220, 755], [1338, 553], [1480, 468]];
      const travel = lerp(0.5, 0.99, at(t, 0.1, d - 0.45));
      route(ctx, path, travel, C.lime, 2.3);
      if (travel > 0.89) {
        const pos = cubic(path, travel);
        token(ctx, pos[0], pos[1], lerp(148, 116, terms), { alpha: 1 - terms * 0.15, yaw: -0.24, roll: -0.035 });
      }
      gate(ctx, { x: 1482, y: 483, w: 380, h: 514, yaw: -0.29, pitch: 0.1, roll: -0.025, light: lerp(0.5, 1, terms), sweep: at(t, 0.32, 2.7) });
      if (travel <= 0.89) {
        const pos = cubic(path, travel);
        token(ctx, pos[0], pos[1], lerp(148, 116, terms), { yaw: -0.24, roll: -0.035 });
      }
    });
    reveal(ctx, at(t, 0, 0.45), () => label(ctx, "OUR ANSWER", 133, 181));
    reveal(ctx, opening, () => text(ctx, "Open to agents.", 123, 392, 162, C.paper, { maxWidth: 1130 }));
    reveal(ctx, terms, () => text(ctx, "On Valio Aimo’s terms.", 126, 577, 119, C.lime, { maxWidth: 1130 }));
    alpha(ctx, terms, () => {
      line(ctx, [[134, 704], [205, 704]], C.lime, 3);
      text(ctx, "The interface opens. The owner stays in control.", 232, 716, 27, C.muted, { body: true, maxWidth: 900 });
    });
  }

  function title(ctx, s, t) {
    const two = at(t, cue(s, "two things", 0.46) - 0.22, 0.9);
    const one = at(t, cue(s, "one", 0.84) - 0.42, 0.65);
    const inA = at(t, 0, 0.75);
    const inB = at(t, 0.3, 0.9);
    reveal(ctx, at(t, 0, 0.35), () => label(ctx, "BUILT FOR VALIO AIMO", 134, 168));
    reveal(ctx, at(t, cue(s, "Delusionals", 0.13) - 0.2, 0.5), () => text(ctx, "THE DELUSIONALS", 126, 315, 149, C.paper, { maxWidth: 1620 }));
    const path = [[392, 648], [780, 815], [1072, 815], [1470, 623]];
    route(ctx, path, two, C.lime, 2.5);
    panel(ctx, { x: 1320, y: lerp(629, 596, inA), w: 572, h: 300, yaw: lerp(-0.3, -0.12, inA), pitch: 0.1, roll: -0.022, alpha: inA, accent: C.lime, depth: 24 }, (w, h) => {
      label(ctx, "01", 37, 45, C.lime, 20);
      icon(ctx, "agent", w - 62, 70, 58, C.lime);
      text(ctx, "Trusted Gateway", 35, 164, 74, C.paper, { maxWidth: w - 70 });
      text(ctx, "The authority boundary", 39, 226, 26, C.muted, { body: true });
      line(ctx, [[39, h - 31], [w - 39, h - 31]], rgba(C.lime, 0.35), 2);
    });
    panel(ctx, { x: 564, y: lerp(650, 579, inB), w: 596, h: 307, yaw: lerp(0.31, 0.13, inB), pitch: 0.11, roll: 0.017, alpha: inB, light: true, depth: 24 }, (w, h) => {
      label(ctx, "02", 37, 46, C.teal, 20);
      icon(ctx, "browser", w - 66, 68, 55, C.teal);
      text(ctx, "Agent workspace", 35, 166, 74, C.ink, { maxWidth: w - 70 });
      text(ctx, "The buying interface", 39, 230, 26, C.teal, { body: true });
      line(ctx, [[39, h - 31], [w - 39, h - 31]], rgba(C.teal, 0.23), 2);
    });
    const pos = cubic(path, lerp(0.25, 0.73, two));
    token(ctx, pos[0], pos[1], 89, { alpha: inB, roll: lerp(0.05, -0.05, two) });
    reveal(ctx, one, () => text(ctx, "Two parts. One controlled path.", 960, 852, 43, C.paper, { align: "center" }), 12, 1.5);
  }

  function architecture(ctx, s, t) {
    const second = Number(s.visual && s.visual.part) === 2;
    const d = duration(s);
    const focus = second ? at(t, 0.05, 1.35) : 0;
    const entry = second ? 1 : at(t, 0, 0.85);
    const source = { x: lerp(348, 591, focus), y: lerp(494, 485, focus), w: lerp(379, 860, focus), h: lerp(260, 456, focus), yaw: lerp(-0.19, -0.035, focus), pitch: lerp(0.08, 0.025, focus) };
    const gateway = { x: lerp(984, 1435, focus), y: lerp(486, 449, focus), w: lerp(576, 535, focus), h: lerp(378, 361, focus), yaw: lerp(-0.045, 0.075, focus), pitch: 0.035 };
    const api = { x: lerp(1586, 1516, focus), y: lerp(492, 757, focus), w: lerp(337, 369, focus), h: lerp(264, 142, focus), yaw: lerp(0.15, 0.06, focus), pitch: 0.065 };
    const human = { x: lerp(991, 1080, focus), y: lerp(791, 786, focus), w: lerp(346, 329, focus), h: lerp(118, 118, focus), yaw: -0.025, pitch: 0.025 };
    const sourcePath = [[source.x + source.w * 0.39, source.y + 11], [source.x + source.w * 0.58, source.y + 11], [gateway.x - gateway.w * 0.63, gateway.y + 11], [gateway.x - gateway.w * 0.38, gateway.y + 11]];
    const apiPath = [[gateway.x + gateway.w * 0.43, gateway.y + 13], [gateway.x + gateway.w * 0.75, gateway.y + 13], [api.x, api.y - api.h * 0.7], [api.x, api.y - api.h * 0.35]];
    const humanPath = [[gateway.x - 12, gateway.y + gateway.h * 0.4], [gateway.x - 12, 708], [human.x, 711], [human.x, human.y - 45]];
    const times = [
      cue(s, "find products", 0.29) - 0.12,
      cue(s, "price and stock", 0.39) - 0.12,
      cue(s, "enforce limits", 0.52) - 0.12,
      cue(s, "approve", 0.63) - 0.12,
      cue(s, "mock order", 0.77) - 0.18,
      cue(s, "Every step", 0.9) - 0.13,
    ];
    const gatewayTime = second ? d + 1 : t;
    const credentials = second ? 1 : at(t, cue(s, "credentialed agents", 0.22) - 0.5, 0.68);
    const find = second ? at(t, cue(s, "sources products", 0.43) - 0.16, 0.65) : at(t, times[0], 0.62);
    const check = second ? 1 : at(t, times[1], 0.7);
    const approval = second ? at(t, cue(s, "human", 0.79) - 0.18, 0.65) : at(t, times[3], 0.7);
    const record = second ? 1 : at(t, times[4], 0.65);
    const logged = second ? 1 : at(t, times[5], 0.6);
    const headingChange = second ? at(t, 0.12, 0.55) : 0;
    const headingIn = second ? 1 : at(t, 0, 0.55);
    const labelOut = 1 - ease(focus / 0.45);
    const labelIn = ease((focus - 0.45) / 0.55);

    alpha(ctx, headingIn, () => {
      alpha(ctx, 1 - ease(headingChange / 0.45), () => {
        label(ctx, "01 / TRUSTED GATEWAY", 131, 157, C.lime, 16);
        text(ctx, "One controlled path.", 125, 244, 101, C.paper);
      });
      alpha(ctx, ease((headingChange - 0.45) / 0.55), () => {
        label(ctx, "02 / AGENT WORKSPACE", 131, 157, C.lime, 16);
        text(ctx, "From a need to a decision.", 125, 244, 97, C.paper, { maxWidth: 1620 });
      });
    });

    camera(ctx, { x: lerp(985, 960, entry), y: lerp(544, 540, entry), zoom: lerp(1.035, 1, entry) }, () => {
      glow(ctx, gateway.x, gateway.y, 400, 310, C.teal, 0.17);
      route(ctx, sourcePath, credentials, C.lime);
      route(ctx, apiPath, check, C.lime);
      route(ctx, humanPath, approval, C.amber, 2);

      panel(ctx, { ...api, alpha: lerp(0.35 + check * 0.65, 0.78, focus), depth: 13, accent: C.teal }, (w, h) => {
        alpha(ctx, labelOut, () => {
          label(ctx, "CHALLENGE APIs", 27, 38, C.muted, 15, 1.7);
          text(ctx, "Valio Aimo", 25, 101, 54, C.paper, { maxWidth: w - 50 });
          line(ctx, [[27, 123], [w - 27, 123]], rgba(C.muted, 0.2), 1);
          text(ctx, "Product catalog", 28, 167, 23, C.muted, { body: true });
          text(ctx, "Fixed price / stock", 28, 207, 23, C.paper, { body: true, maxWidth: w - 56 });
        });
        alpha(ctx, labelIn, () => {
          text(ctx, "Valio Aimo challenge APIs", 24, 53, 34, C.paper, { maxWidth: w - 48 });
          text(ctx, "Fixed price / stock", 26, 96, 22, C.muted, { body: true });
        });
      });

      panel(ctx, { ...human, alpha: second ? lerp(1, 0.5 + approval * 0.5, focus) : 0.25 + approval * 0.75, accent: C.amber, depth: 11 }, (w) => {
        icon(ctx, "human", 42, 56, 45, C.amber);
        text(ctx, "Kitchen manager", 80, 51, 35, C.paper, { maxWidth: w - 101 });
        text(ctx, "When approval is needed", 81, 82, 17, C.muted, { body: true, maxWidth: w - 101 });
      });

      panel(ctx, { ...source, light: true, depth: lerp(15, 24, focus), alpha: entry }, (w, h) => {
        alpha(ctx, labelOut, () => {
          label(ctx, "REQUEST ORIGIN", 29, 40, C.teal, 15, 1.6);
          icon(ctx, "agent", w - 52, 49, 39, C.teal);
          text(ctx, "Credentialed", 28, 115, 50, C.ink);
          text(ctx, "agent", 28, 169, 55, C.ink);
          text(ctx, "Workspace or external agent", 30, 218, 20, C.teal, { body: true, maxWidth: w - 60 });
        });
        alpha(ctx, labelIn, () => {
          label(ctx, "02", 32, 43, C.teal, 17, 1.5);
          text(ctx, "Agent workspace", 78, 58, 53, C.ink, { maxWidth: w - 157 });
          mark(ctx, w - 45, 40, 27, C.teal);
          line(ctx, [[32, 83], [w - 32, 83]], rgba(C.teal, 0.17), 1);
          const need = at(t, cue(s, "chef", 0.2) - 0.18, 0.55);
          reveal(ctx, need, () => {
            label(ctx, "THE CHEF’S REQUEST", 36, 126, C.teal, 15, 1.6);
            round(ctx, 31, 143, w - 62, 108, 14);
            ctx.fillStyle = "#e2eeea";
            ctx.fill();
            text(ctx, "1,000 L lactose-free milk", 53, 184, 31, C.ink, { body: true, maxWidth: w - 112 });
            text(ctx, "for Monday", 53, 225, 29, C.teal, { body: true });
          }, 12, 1.5);
          const exception = at(t, cue(s, "exceptions", 0.64) - 0.22, 0.55);
          const rows = [
            { name: "Source products", icon: "catalog", p: find, color: C.teal },
            { name: "Handle exceptions", icon: "quote", p: exception, color: C.teal },
            { name: "Ask a human", icon: "human", p: approval, color: "#91641f" },
          ];
          const rowWidth = (w - 80) / 3;
          rows.forEach((row, i) => {
            reveal(ctx, row.p, () => {
              const x = 39 + rowWidth * i;
              if (i > 0) line(ctx, [[x - 10, 287], [x - 10, h - 39]], rgba(C.teal, 0.17), 1);
              icon(ctx, row.icon, x + 31, 316, 40, row.color);
              text(ctx, row.name, x + 5, 367, 27, C.ink, { maxWidth: rowWidth - 25 });
              line(ctx, [[x + 6, 391], [x + rowWidth - 27, 391]], rgba(row.color, 0.25), 2);
            }, 16, 1.5);
          });
        });
      });

      panel(ctx, { ...gateway, alpha: entry, accent: C.lime, depth: 21 }, (w, h) => {
        label(ctx, "01", 31, 39, C.lime, 18, 1.6);
        text(ctx, "Trusted Gateway", 31, 101, lerp(67, 61, focus), C.paper, { maxWidth: w - 62 });
        text(ctx, "OpenAPI 3.1", 34, 137, 23, C.muted, { body: true });
        line(ctx, [[33, 158], [w - 33, 158]], rgba(C.muted, 0.2), 1);
        alpha(ctx, labelOut, () => {
          const pages = [
            ["Owner-controlled access", "A request enters a defined path.", "agent", C.lime],
            ["Find products", "Catalog lookup", "catalog", C.lime],
            ["Price + stock", "Check the current quote", "quote", C.lime],
            ["Enforce limits", "The agent’s granted authority", "limit", C.lime],
            ["Human approval", "When the grant requires it", "human", C.amber],
            ["Mock order", "Local record · no payment", "record", C.lime],
            ["Audit trail", "Every step logged.", "audit", C.lime],
          ];
          phaseWeights(gatewayTime, [-0.36, ...times], (i, a, incoming, outgoing) => {
            alpha(ctx, a, () => {
              ctx.save();
              ctx.translate(0, (1 - incoming) * 13 - outgoing * 13);
              icon(ctx, pages[i][2], i === 0 ? 84 : 82, i === 0 ? 232 : 238, i === 0 ? 59 : 60, pages[i][3]);
              text(ctx, pages[i][0], i === 0 ? 139 : 138, 236, i === 0 ? 37 : 44, C.paper, { maxWidth: w - 166 });
              text(ctx, pages[i][1], 140, 278, i === 0 ? 20 : 21, C.muted, { body: true, maxWidth: w - 168 });
              ctx.restore();
            });
          });
          times.forEach((start, i) => {
            const active = at(gatewayTime, start, 0.4);
            const x = 35 + i * ((w - 70) / 6);
            line(ctx, [[x, h - 41], [x + (w - 100) / 6, h - 41]], rgba(C.muted, 0.18), 3);
            if (active > 0) line(ctx, [[x, h - 41], [x + (w - 100) / 6 * active, h - 41]], i === 3 ? C.amber : C.lime, 3);
          });
        });
        alpha(ctx, labelIn, () => {
          icon(ctx, approval > 0.2 ? "human" : "limit", 79, 239, 62, approval > 0.2 ? C.amber : C.lime);
          text(ctx, "The same", 136, 222, 47, C.paper);
          text(ctx, "authority rules.", 136, 275, 47, C.paper, { maxWidth: w - 165 });
          text(ctx, "Limit · approval · audit", 36, h - 29, 22, C.muted, { body: true });
        });
      });

      if (!second) {
        const travel = at(t, cue(s, "credentialed agents", 0.22) - 0.3, Math.max(0.6, times[0] - cue(s, "credentialed agents", 0.22) + 0.65));
        const pos = cubic(sourcePath, lerp(0.04, 0.99, travel));
        token(ctx, pos[0], pos[1], 57, { alpha: credentials * (1 - at(t, times[0] + 0.15, 0.5)), yaw: -0.08, roll: -0.035 });
        const approvalTravel = at(t, times[3] + 0.1, Math.max(0.5, times[4] - times[3] - 0.15));
        if (approvalTravel > 0 && approvalTravel < 1) {
          const pt = cubic(humanPath, approvalTravel);
          token(ctx, pt[0], pt[1], 43, { color: C.amber, roll: 0, yaw: 0 });
        }
        alpha(ctx, logged, () => {
          line(ctx, [[167, 855], [570, 855]], rgba(C.lime, 0.3), 1.5);
          label(ctx, "EVERY STEP LOGGED", 173, 836, C.lime, 17, 1.8);
        });
      } else {
        const travel = at(t, cue(s, "sources products", 0.43) - 0.1, 1.1);
        if (travel > 0 && travel < 1) {
          const pt = cubic(sourcePath, travel);
          token(ctx, pt[0], pt[1], 55, { roll: 0, yaw: 0 });
        }
        alpha(ctx, approval, () => {
          const branch = [[858, 706], [901, 765], [909, 786], [942, 786]];
          route(ctx, branch, approval, C.amber, 2.3);
        });
      }
    });
    if (!second) {
      alpha(ctx, record * (1 - logged), () => label(ctx, "MOCK ORDER / LOCAL DEMO", 134, 856, C.muted, 17, 1.8));
    }
  }

  function scenarios(ctx, s, t) {
    const rules = at(t, cue(s, "rules", 0.68) - 0.45, 0.6);
    reveal(ctx, at(t, 0, 0.4), () => {
      text(ctx, "Three scenarios.", 126, 247, 132, C.paper);
      text(ctx, "One set of rules.", 130, 339, 72, C.lime);
    });
    const stations = [
      { x: 375, n: "01", title: "Milk.", note: "Manager approval", color: C.amber },
      { x: 960, n: "02", title: "Butter.", note: "Within the limit", color: C.lime },
      { x: 1540, n: "03", title: "Bypass.", note: "Refused", color: C.red },
    ];
    const path = [[150, 622], [630, 765], [1320, 765], [1775, 622]];
    route(ctx, path, rules, C.lime, 2);
    stations.forEach((station, i) => {
      const enter = at(t, 0.02 + i * 0.13, 0.68);
      const y = lerp(580, 555, enter);
      gate(ctx, { x: station.x + 30, y, w: 301, h: 299, yaw: lerp(0.24 - i * 0.19, 0.08 - i * 0.08, enter), pitch: 0.07, depth: 24, thickness: 17, alpha: enter * 0.63, light: 0.6, sweep: at(t, 0.1 + i * 0.13, 1.45) });
      reveal(ctx, enter, () => {
        text(ctx, station.n, station.x - 141, 610, 199, C.paper);
        text(ctx, station.title, station.x - 143, 731, 61, station.color);
        text(ctx, station.note, station.x - 140, 783, 26, C.muted, { body: true, maxWidth: 360 });
      }, 14, 1.5);
    });
    const pt = cubic(path, lerp(0.025, 0.96, at(t, 0.2, duration(s) - 0.25)));
    token(ctx, pt[0], pt[1], 65, { alpha: at(t, 0.1, 0.35), yaw: 0, roll: -0.04 });
  }

  function terminal(ctx, s, t, film) {
    const lines = film.terminal;
    if (!Array.isArray(lines) || !lines.length) {
      throw new TypeError("CinematicMotion: terminal capture must be a non-empty array of refusal lines.");
    }
    for (const value of lines) {
      if (typeof value !== "string" || !value.trim() || /[\r\n]/.test(value)) {
        throw new TypeError("CinematicMotion: terminal capture entries must be non-empty, single-line strings.");
      }
    }
    const firstError = lines.findIndex((value) => /\b409\b.*\bapproval\s+required\b/i.test(value));
    const secondError = lines.findIndex((value) => /\b403\b.*\bhuman\s+(?:is\s+)?required\b/i.test(value));
    if (firstError < 0 || secondError < 0) {
      throw new Error("CinematicMotion: terminal capture must contain both 409 Approval required and 403 Human required refusals.");
    }
    const skip = cue(s, "skip", 0.29);
    const self = cue(s, "approve", 0.56);
    const firstAt = Math.max(skip + 0.23, 0.8);
    const secondAt = Math.max(self + 0.38, firstAt + 1.1);
    const refusedAt = Math.max(secondAt + 0.45, cue(s, "refused", 0.86) - 0.15);
    const defaultStarts = [0.12, Math.max(0.35, skip - 0.45), skip, firstAt, Math.max(firstAt + 0.4, self - 0.42), self, secondAt, refusedAt];
    const positions = [87, 154, 197, 244, 326, 368, 415, 493];
    const first = at(t, firstAt, 0.35);
    const second = at(t, secondAt, 0.38);

    reveal(ctx, at(t, 0.02, 0.5), () => text(ctx, "No bypass. No self-approval.", 128, 218, 108, C.paper, { maxWidth: 1660 }));
    panel(ctx, { x: 718, y: 572, w: 1180, h: 571, yaw: -0.015, pitch: 0.012, depth: 18, accent: second > 0.15 ? C.red : C.amber }, (w, h) => {
      label(ctx, "CAPTURED REFUSAL / LOCAL DEMO", 31, 37, C.muted, 17, 1.6);
      line(ctx, [[31, 54], [w - 31, 54]], rgba(C.muted, 0.2), 1);
      lines.forEach((value, i) => {
        const start = defaultStarts[i] === undefined ? refusedAt + (i - 7) * 0.16 : defaultStarts[i];
        const entered = at(t, start, 0.26);
        const isFirst = i === firstError;
        const isSecond = i === secondError;
        const color = isFirst ? C.amber : isSecond ? C.red : value.startsWith("#") ? C.quiet : /^Both refused/.test(value) ? C.lime : C.paper;
        const yy = positions[i] === undefined ? 493 + (i - 7) * 32 : positions[i];
        if ((isFirst || isSecond) && entered > 0) {
          alpha(ctx, entered, () => {
            round(ctx, 19, yy - 34, w - 38, 52, 9);
            ctx.fillStyle = rgba(color, 0.075);
            ctx.fill();
            line(ctx, [[21, yy - 26], [21, yy + 10]], color, 3);
          });
        }
        reveal(ctx, entered, () => {
          wrapped(ctx, value, 36, yy, w - 72, isFirst || isSecond ? 26 : i === 0 || /^Both refused/.test(value) ? 21 : 24, color, 1.28, isFirst || isSecond);
        }, 7, 0);
      });
    });
    const codeX = 1396;
    if (firstError >= 0) {
      alpha(ctx, first * (1 - second), () => {
        label(ctx, "REQUEST 01", codeX, 340, C.amber, 18, 1.8);
        text(ctx, "409", codeX - 8, 540, 211, C.amber);
        text(ctx, "Approval", codeX, 625, 66, C.paper);
        text(ctx, "required", codeX, 695, 66, C.paper);
        line(ctx, [[codeX, 747], [1766, 747]], rgba(C.amber, 0.5), 2);
      });
    }
    if (secondError >= 0) {
      reveal(ctx, second, () => {
        label(ctx, "REQUEST 02", codeX, 340, C.red, 18, 1.8);
        text(ctx, "403", codeX - 8, 540, 211, C.red);
        text(ctx, "Human", codeX, 625, 66, C.paper);
        text(ctx, "required", codeX, 695, 66, C.paper);
        line(ctx, [[codeX, 747], [1766, 747]], rgba(C.red, 0.55), 2);
      }, 14, 2);
    }
    if (firstError >= 0 && secondError >= 0) {
      reveal(ctx, at(t, refusedAt, 0.38), () => label(ctx, "BOTH REFUSED", codeX, 806, C.lime, 23, 2.1), 10, 0);
    }
  }

  function rules(ctx, s, t) {
    const alone = at(t, cue(s, "Small orders", 0.015), 0.68);
    const human = at(t, cue(s, "Humans sign", 0.24) - 0.1, 0.72);
    const never = at(t, cue(s, "Never", 0.51) - 0.12, 0.66);
    const self = at(t, cue(s, "self approval", 0.59) - 0.12, 0.45);
    const stale = at(t, cue(s, "stale quotes", 0.71) - 0.12, 0.45);
    const allergens = at(t, cue(s, "guessing allergens", 0.83) - 0.15, 0.5);
    reveal(ctx, at(t, 0, 0.45), () => {
      label(ctx, "THE AUTHORITY MODEL", 132, 157, C.muted, 18);
      text(ctx, "Autonomy has boundaries.", 124, 246, 111, C.paper, { maxWidth: 1650 });
    });
    const path = [[140, 789], [602, 839], [1360, 839], [1780, 789]];
    route(ctx, path, lerp(0.25, 0.94, human * 0.45 + never * 0.55), C.lime, 1.8);
    const columns = [
      { x: 156, w: 510, enter: alone, color: C.lime, title: "Alone", number: "01" },
      { x: 754, w: 477, enter: human, color: C.amber, title: "Humans sign", number: "02" },
      { x: 1341, w: 451, enter: never, color: C.red, title: "Never", number: "03" },
    ];
    columns.forEach((column, i) => {
      const p = column.enter;
      alpha(ctx, p, () => {
        const fin = [[column.x - 28, 342], [column.x - 11, 329], [column.x - 11, 749], [column.x - 28, 766]];
        polygon(ctx, fin);
        const g = ctx.createLinearGradient(column.x, 330, column.x, 768);
        g.addColorStop(0, rgba(column.color, 0.6));
        g.addColorStop(0.43, rgba(C.teal, 0.45));
        g.addColorStop(1, rgba(C.teal, 0));
        ctx.fillStyle = g;
        ctx.fill();
        line(ctx, [[column.x - 27, 344], [column.x - 27, 763]], rgba(column.color, 0.7), 1.6);
      });
      reveal(ctx, p, () => {
        label(ctx, column.number, column.x + 5, 350, column.color, 18, 2);
        text(ctx, column.title, column.x, 452, i === 1 ? 88 : 100, C.paper, { maxWidth: column.w - 26 });
        if (i === 0) {
          text(ctx, "≤ €500", column.x - 3, 614, 143, C.lime, { maxWidth: column.w - 34 });
          text(ctx, "Butter ≈ €42", column.x + 5, 686, 33, C.paper, { body: true });
          text(ctx, "Within the demo grant", column.x + 5, 733, 23, C.muted, { body: true });
        } else if (i === 1) {
          text(ctx, "€1,150", column.x - 3, 614, 138, C.amber, { maxWidth: column.w - 30 });
          text(ctx, "Milk order", column.x + 5, 686, 33, C.paper, { body: true });
          text(ctx, "A human approves the exact basket", column.x + 5, 733, 22, C.muted, { body: true, maxWidth: column.w - 25 });
        }
      }, 26, 2);
    });
    [
      ["Self-approval", 537, self],
      ["Stale quotes", 618, stale],
      ["Guessing allergen safety", 699, allergens],
    ].forEach(([value, y, p]) => {
      reveal(ctx, p, () => {
        line(ctx, [[1346, y - 12], [1362, y - 12]], C.red, 3);
        wrapped(ctx, value, 1380, y, 394, 30, C.paper, 1.3);
      }, 12, 1.5);
    });
    reveal(ctx, at(t, 0.4, 0.6), () => label(ctx, "DEMO POLICY — NOT A UNIVERSAL LIMIT", 158, 865, C.muted, 19, 1.5), 8, 0);
  }

  function moving(ctx, s, t) {
    const d = duration(s);
    const opens = at(t, cue(s, "buying interface", 0.53) - 0.16, 0.8);
    const settle = at(t, 0, d - 0.2);
    const path = [[661, 704], [927, 841], [1250, 495], [1481, 486]];
    route(ctx, path, lerp(0.2, 0.94, opens), C.lime, 2.5);
    gate(ctx, { x: lerp(1497, 1481, settle), y: 486, w: 381, h: 514, yaw: lerp(-0.2, -0.29, settle), pitch: 0.1, roll: -0.025, light: lerp(0.35, 0.9, opens), sweep: at(t, 0.4, 2.7) });
    panel(ctx, { x: lerp(489, 463, opens), y: lerp(582, 632, opens), w: lerp(590, 527, opens), h: lerp(304, 274, opens), yaw: lerp(-0.05, 0.12, opens), pitch: 0.08, light: true, depth: 19 }, (w, h) => {
      label(ctx, "WEBSHOP", 28, 39, C.teal, 19, 1.7);
      line(ctx, [[28, 59], [w - 28, 59]], rgba(C.teal, 0.2), 1);
      const gap = 15;
      const tileWidth = (w - 58 - gap * 2) / 3;
      for (let i = 0; i < 3; i += 1) {
        const x = 29 + i * (tileWidth + gap);
        round(ctx, x, 80, tileWidth, h - 114, 11);
        ctx.fillStyle = i === 1 ? "#dbe9dd" : "#e1eae7";
        ctx.fill();
        icon(ctx, i === 1 ? "catalog" : "record", x + tileWidth / 2, 128, 41, rgba(C.teal, 0.55));
        line(ctx, [[x + 17, h - 76], [x + tileWidth - 17, h - 76]], rgba(C.teal, 0.33), 5);
        line(ctx, [[x + 17, h - 57], [x + tileWidth * 0.57, h - 57]], rgba(C.teal, 0.18), 4);
      }
    });
    const pos = cubic(path, lerp(0.33, 0.93, at(t, cue(s, "interface", 0.62) - 0.5, Math.max(1.3, d * 0.5))));
    token(ctx, pos[0], pos[1], lerp(101, 143, opens), { yaw: lerp(0.1, -0.23, opens), roll: lerp(0.08, -0.035, opens) });
    reveal(ctx, at(t, 0.02, 0.52), () => text(ctx, "The webshop stays.", 126, 235, 129, C.paper, { maxWidth: 1370 }));
    reveal(ctx, opens, () => text(ctx, "The interface opens.", 129, 353, 106, C.lime, { maxWidth: 1140 }));
    alpha(ctx, opens, () => {
      text(ctx, "Still here.", 235, 832, 27, C.muted, { body: true });
      text(ctx, "Credentialed agents. The same authority boundary.", 842, 832, 26, C.muted, { body: true, maxWidth: 921 });
    });
  }

  function ending(ctx, s, t, film) {
    const second = Number(s.visual && s.visual.part) === 2;
    const firstSegment = (film.segments || []).find((item) => item.visual && item.visual.scene === "end" && Number(item.visual.part) === 1);
    const before = firstSegment ? duration(firstSegment) : 2.7;
    const difference = firstSegment && Number.isFinite(s.start) && Number.isFinite(firstSegment.start) ? s.start - firstSegment.start : before;
    const elapsed = second ? Math.max(0, difference) + t : t;
    const open = second ? 1 : at(t, cue(s, "Open", 0.02), 0.62);
    const terms = second ? at(t, Math.max(0.65, cue(s, "On", 0.015)), 0.52) : 0;
    const unfold = second ? at(t, 0.08, Math.min(1.7, duration(s) * 0.35)) : 0;
    const frame = {
      x: lerp(1481, 960, unfold),
      y: lerp(486, 437, unfold),
      w: lerp(381, 1664, unfold),
      h: lerp(514, 574, unfold),
      yaw: lerp(-0.29, 0, unfold),
      pitch: lerp(0.1, 0, unfold),
      roll: lerp(-0.025, 0, unfold),
      depth: lerp(44, 9, unfold),
      thickness: lerp(34, 10, unfold),
      light: lerp(0.85, 0.64, unfold),
      sweep: second ? at(t, 0.08, 1.8) : at(elapsed, 0.1, 2.2),
    };
    glow(ctx, 1350, 472, 655, 420, C.teal, lerp(0.23, 0.15, unfold));
    gate(ctx, frame);
    const dock = second ? at(t, 0.12, Math.min(1.58, duration(s) * 0.34)) : 0;
    const tx = lerp(1422, 1706, dock);
    const ty = lerp(501, 188, dock);
    token(ctx, tx, ty, lerp(139, 78, dock), { yaw: lerp(-0.23, 0, dock), pitch: lerp(0.1, 0, dock), roll: lerp(-0.035, 0, dock) });
    label(ctx, "VALIO AIMO", 185, 188, C.muted, 20, 3.2);
    reveal(ctx, open, () => text(ctx, "Open to agents.", 178, 365, 172, C.paper, { maxWidth: 1517 }), 20, 2);
    reveal(ctx, terms, () => text(ctx, "On Valio Aimo’s terms.", 181, 561, 161, C.lime, { maxWidth: 1510 }), 18, 2);
    if (second) {
      const detailsAt = Math.max(0.65, Math.min(cue(s, "terms", 0.25) + 0.28, duration(s) - 2.85));
      const details = at(t, detailsAt, 0.48);
      reveal(ctx, details, () => {
        text(ctx, "THE DELUSIONALS", 133, 808, 48, C.paper, { maxWidth: 401 });
        text(ctx, "Krish Waghresha  ·  Jakub Piotrowski", 608, 806, 28, C.muted, { body: true, maxWidth: 1172 });
        text(ctx, "Synthetic systems · local mock orders · no payments", 136, 866, 25, C.muted, { body: true, maxWidth: 1630 });
      }, 11, 1);
    }
  }

  const scenes = Object.freeze({
    hook,
    history,
    agent,
    hero,
    title,
    architecture,
    scenarios,
    terminal,
    rules,
    moving,
    end: ending,
  });

  function scene(ctx, segment, localTime, film) {
    if (!segment || !segment.visual || typeof segment.visual.scene !== "string" || !segment.visual.scene.trim()) {
      throw new TypeError("CinematicMotion.scene requires segment.visual.scene.");
    }
    const name = segment.visual.scene;
    if (!Object.prototype.hasOwnProperty.call(scenes, name)) {
      throw new RangeError(`CinematicMotion: unknown scene "${name}".`);
    }
    const draw = scenes[name];
    const t = clamp(Number(localTime) || 0, 0, duration(segment));
    ctx.save();
    try {
      draw(ctx, segment, t, film || {});
    } finally {
      ctx.restore();
    }
  }

  window.CinematicMotion = Object.freeze({ background, scene });
}());
