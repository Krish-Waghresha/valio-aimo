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

  function wipeText(ctx, value, x, y, size, color, amount, maxWidth, exit = 0) {
    if (amount <= 0 || exit >= 1) return;
    ctx.save();
    ctx.beginPath();
    ctx.rect(x - 8, y - size, maxWidth + 16, size * 1.25);
    ctx.clip();
    ctx.globalAlpha *= Math.min(1, amount * 2) * (1 - exit);
    ctx.translate(0, (1 - amount) * size * 0.78 - exit * 30);
    text(ctx, value, x, y, size, color, { maxWidth });
    ctx.restore();
  }

  function kitchenNumber(ctx, t, morph) {
    const value = "20,000+";
    const x = 125;
    const y = lerp(602, 234, morph);
    let size = lerp(516, 86, morph);
    ctx.save();
    ctx.font = `700 ${size}px ${DISPLAY}`;
    let widths = Array.from(value, (letter) => ctx.measureText(letter).width);
    const total = widths.reduce((sum, width) => sum + width, 0);
    if (total > 1640) {
      size *= 1640 / total;
      ctx.font = `700 ${size}px ${DISPLAY}`;
      widths = Array.from(value, (letter) => ctx.measureText(letter).width);
    }
    let cursor = x;
    Array.from(value).forEach((letter, i) => {
      const entered = at(t, 0.025 + i * 0.025, 0.53);
      if (entered > 0) {
        ctx.save();
        ctx.beginPath();
        ctx.rect(cursor - 5, y - size, widths[i] + 10, size * 1.2);
        ctx.clip();
        ctx.translate(cursor + widths[i] / 2, y + (1 - entered) * size * 0.95);
        const scale = 1 + (1 - entered) * 0.13;
        ctx.scale(scale, scale);
        ctx.fillStyle = letter === "+" ? C.lime : C.paper;
        ctx.textAlign = "center";
        ctx.textBaseline = "alphabetic";
        ctx.fillText(letter, 0, 0);
        ctx.restore();
      }
      cursor += widths[i];
    });
    ctx.restore();
  }

  function pitchFrame(ctx, amount, bottom = 747) {
    const p = clamp(amount);
    const right = 1775;
    const top = lerp(bottom - 28, 276, p);
    ctx.save();
    const edge = ctx.createLinearGradient(136, bottom, right, 276);
    edge.addColorStop(0, rgba(C.lime, 0.95));
    edge.addColorStop(0.7, rgba(C.lime, 0.62));
    edge.addColorStop(1, rgba(C.paper, 0.75));
    line(ctx, [[136, bottom], [right - 28, bottom], [right, bottom - 28], [right, top]], edge, 4);
    polygon(ctx, [[right + 7, bottom - 32], [right + 17, bottom - 42], [right + 17, top + 7], [right + 7, top - 3]]);
    ctx.fillStyle = rgba(C.teal, 0.55 * p);
    ctx.fill();
    alpha(ctx, at(p, 0.78, 0.22), () => {
      line(ctx, [[right, 276], [right - 28, 248], [right - 116, 248]], rgba(C.lime, 0.62), 4);
    });
    ctx.restore();
  }

  function connection(ctx, points, activity = 0, color = C.lime, twoWay = false) {
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(...points[0]);
    ctx.bezierCurveTo(...points[1], ...points[2], ...points[3]);
    ctx.lineWidth = 2.6;
    ctx.strokeStyle = rgba(C.muted, 0.47);
    ctx.stroke();
    if (activity > 0) {
      ctx.strokeStyle = rgba(color, activity * 0.86);
      ctx.stroke();
    }
    const head = (a, b) => {
      const angle = Math.atan2(b[1] - a[1], b[0] - a[0]);
      const length = 10;
      line(ctx, [
        [b[0] - Math.cos(angle - 0.48) * length, b[1] - Math.sin(angle - 0.48) * length],
        b,
        [b[0] - Math.cos(angle + 0.48) * length, b[1] - Math.sin(angle + 0.48) * length],
      ], activity > 0.3 ? color : C.muted, 2.6);
    };
    head(points[2], points[3]);
    if (twoWay) head(points[1], points[0]);
    ctx.restore();
  }

  function routePacket(ctx, points, t, start, length, color = C.lime) {
    const p = at(t, start, length);
    if (p <= 0 || p >= 1) return;
    const position = cubic(points, p);
    token(ctx, position[0], position[1], 30, {
      color, roll: 0, yaw: 0, pitch: 0,
      alpha: at(p, 0, 0.1) * (1 - at(p, 0.9, 0.1)),
    });
  }

  function background(ctx, time) {
    const t = Math.min(Math.max(0, Number(time) || 0), 114);
    const lift = 1 - at(t, 9.5, 1.5) + at(t, 109, 0.8);
    ctx.save();
    const base = ctx.createLinearGradient(0, 0, 1600, H);
    base.addColorStop(0, C.ink);
    base.addColorStop(0.58, "#062b36");
    base.addColorStop(1, "#03171e");
    ctx.fillStyle = base;
    ctx.fillRect(0, 0, W, H);
    glow(ctx, 1270, 365, 970, 610, C.teal, 0.28 + lift * 0.25);
    glow(ctx, 1470, 754, 610, 220, C.lime, 0.035 + lift * 0.025);
    glow(ctx, 550, 930, 870, 180, C.teal, 0.1);
    const horizon = ctx.createLinearGradient(0, 0, W, 0);
    horizon.addColorStop(0, rgba(C.teal, 0));
    horizon.addColorStop(0.64, rgba(C.muted, 0.055));
    horizon.addColorStop(1, rgba(C.teal, 0));
    line(ctx, [[0, 869], [1920, 869]], horizon, 1);
    const vignette = ctx.createRadialGradient(960, 420, 310, 960, 480, 1140);
    vignette.addColorStop(0, rgba(C.ink, 0));
    vignette.addColorStop(1, rgba(C.ink, 0.35));
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, W, H);
    ctx.restore();
  }

  function hook(ctx, s, t) {
    const d = duration(s);
    const lead = Number(s.leadInSeconds) || 2;
    const buyerAt = clamp(cue(s, "The next buyer", 0.56), lead + 0.75, d - 1.7);
    const morph = at(t, buyerAt - 0.12, 0.66);
    const agentAt = Math.min(Math.max(cue(s, "agent", 0.76) - 0.06, buyerAt + 0.67), d - 1);
    const numberIn = at(t, 0.06, 0.52);
    alpha(ctx, numberIn, () => label(ctx, "VALIO AIMO / FOODSERVICE", 134, 150, C.muted, 20, 2.2));
    alpha(ctx, at(t, 0.09, 0.45), () => {
      mark(ctx, 1718, 159, 67, C.lime);
      pitchFrame(ctx, morph, 846);
    });
    // The figure settles in the music-only lead-in. Word cues already include it.
    kitchenNumber(ctx, t, morph);
    reveal(ctx, at(t, 0.49, 0.34), () => {
      text(ctx, "professional kitchens", 134, lerp(718, 282, morph), lerp(72, 27, morph), C.muted, { body: true, maxWidth: 1570 });
    }, 15, 0);
    wipeText(ctx, "The next buyer", 128, 481, 119, C.paper, at(t, buyerAt + 0.34, 0.35), 1570);
    wipeText(ctx, "AN AGENT.", 123, 702, 230, C.lime, at(t, agentAt, 0.4), 1570);
    reveal(ctx, at(t, Math.min(agentAt + 0.53, d - 0.9), 0.27), () => {
      text(ctx, "Your business. Your terms.", 137, 810, 31, C.paper, { body: true });
    }, 10, 0);
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
    const opening = at(t, cue(s, "Open", 0.025), 0.47);
    const terms = at(t, cue(s, "On Valio", 0.44) - 0.04, 0.47);
    pitchFrame(ctx, 1);
    mark(ctx, 1718, 159, 67, C.lime);
    label(ctx, "VALIO AIMO", 138, 178, C.paper, 25, 3.6);
    wipeText(ctx, "Open to agents.", 129, 427, 183, C.paper, opening, 1582);
    wipeText(ctx, "On Valio Aimo’s terms.", 132, 623, 166, C.lime, terms, 1580);
    reveal(ctx, terms, () => {
      text(ctx, "A new buying interface. The owner stays in control.", 140, 824, 30, C.muted, { body: true, maxWidth: 1570 });
    }, 9, 0);
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

  function architecture(ctx, s, t, film) {
    const second = Number(s.visual && s.visual.part) === 2;
    const first = second
      ? (film.segments || []).find((item) => item.visual && item.visual.scene === "architecture" && Number(item.visual.part) === 1) || { targetSeconds: 12 }
      : s;
    const firstTime = second ? duration(first) + t : t;
    const entry = second ? 1 : at(t, 0, 0.55);
    const needAt = cue(first, "chef's need", 0.31);
    const taskAt = cue(first, "purchasing task", 0.54);
    const externalAt = cue(first, "External purchasing agents", 0.71);
    const need = at(firstTime, needAt - 0.12, 0.65);
    const task = at(firstTime, taskAt - 0.12, 0.65);
    const external = at(firstTime, externalAt - 0.12, 0.65);
    const focus = second ? at(t, 0.04, 0.7) : 0;
    const workspaceFocus = (0.55 + 0.45 * at(firstTime, cue(first, "workspace", 0.2), 0.6)) * (1 - focus * 0.6);
    const gatewayFocus = 0.32 + focus * 0.68;
    const products = second ? at(t, cue(s, "products", 0.16) - 0.1, 0.55) : 0;
    const prices = second ? at(t, cue(s, "fixed prices", 0.25) - 0.1, 0.55) : 0;
    const stock = second ? at(t, cue(s, "stock", 0.32) - 0.1, 0.55) : 0;
    const open = second ? at(t, cue(s, "open API", 0.41) - 0.12, 0.55) : 0;
    const limits = second ? at(t, cue(s, "spending limits", 0.54) - 0.12, 0.6) : 0;
    const approvalAt = second ? cue(s, "human approval", 0.66) - 0.12 : Infinity;
    const recordAt = second ? cue(s, "mock order", 0.8) - 0.12 : Infinity;
    const approval = second ? at(t, approvalAt, 0.6) : 0;
    const record = second ? at(t, recordAt, 0.65) : 0;
    const audit = second ? at(t, cue(s, "Every decision", 0.88) - 0.12, 0.65) : 0;
    const workspacePath = [[630, 499], [669, 499], [700, 499], [740, 499]];
    const externalPath = [[630, 811], [710, 811], [660, 573], [740, 573]];
    const dataPath = [[1330, 484], [1367, 484], [1401, 484], [1440, 484]];
    const humanPath = [[1025, 666], [1025, 694], [1025, 717], [1025, 745]];
    const localPath = [[1256, 666], [1290, 733], [1539, 700], [1570, 745]];

    // All six nodes keep their coordinates and readable labels for both parts.
    alpha(ctx, entry, () => {
      label(ctx, "OUR TWO COMPONENTS", 134, 151, C.lime, 18, 2);
      text(ctx, "Two parts. One buying flow.", 126, 245, 97, C.paper, { maxWidth: 1640 });
      connection(ctx, workspacePath, task * (1 - focus * 0.55));
      connection(ctx, externalPath, external * (1 - focus * 0.55));
      connection(ctx, dataPath, products, C.lime, true);
      connection(ctx, humanPath, approval, C.amber, true);
      connection(ctx, localPath, record);
      text(ctx, "DATA", 1356, 460, 17, C.muted, { body: true, bold: true });
      text(ctx, "When needed", 1048, 714, 19, C.muted, { body: true });

      panel(ctx, { x: 380, y: 483, w: 500, h: 366, light: true, depth: 14, accent: C.lime }, (w) => {
        alpha(ctx, workspaceFocus, () => line(ctx, [[27, 3], [w - 27, 3]], C.teal, 4));
        label(ctx, "01 / OUR WORKSPACE", 31, 40, C.teal, 17, 1.5);
        text(ctx, "Agent workspace", 28, 110, 68, C.ink, { maxWidth: w - 58 });
        line(ctx, [[31, 135], [w - 31, 135]], rgba(C.teal, 0.2), 1);
        text(ctx, "A chef’s need", 33, 191, 32, C.ink, { body: true });
        line(ctx, [[34, 206], [34 + 236 * need, 206]], rgba(C.teal, 0.56), 2);
        connection(ctx, [[52, 221], [52, 229], [52, 238], [52, 247]], task, C.teal);
        mark(ctx, 52, 280, 31, C.teal);
        text(ctx, "Purchasing task", 83, 289, 51, C.ink, { maxWidth: w - 112 });
        text(ctx, "Products · quantity · delivery", 34, 334, 23, C.teal, { body: true, maxWidth: w - 67 });
      });

      panel(ctx, { x: 1035, y: 483, w: 590, h: 366, depth: 17, accent: C.lime }, (w) => {
        alpha(ctx, gatewayFocus, () => line(ctx, [[27, 3], [w - 27, 3]], C.lime, 4));
        label(ctx, "02 / OUR GATEWAY", 31, 40, C.lime, 17, 1.5);
        text(ctx, "Trusted Gateway", 29, 110, 70, C.paper, { maxWidth: w - 60 });
        text(ctx, "OpenAPI 3.1", 34, 153, 27, C.muted, { body: true });
        line(ctx, [[34, 165], [34 + 194 * open, 165]], rgba(C.lime, 0.8), 2);
        line(ctx, [[33, 184], [w - 33, 184]], rgba(C.muted, 0.23), 1);
        icon(ctx, "limit", 59, 224, 40, limits > 0.2 ? C.lime : C.muted);
        text(ctx, "Spending limits", 100, 241, 45, C.paper, { maxWidth: w - 131 });
        icon(ctx, "human", 59, 282, 39, approval > 0.2 ? C.amber : C.muted);
        text(ctx, "Human approval", 100, 299, 45, C.paper, { maxWidth: w - 131 });
        text(ctx, "Owner-defined authority", 35, 342, 23, C.muted, { body: true });
      });

      panel(ctx, { x: 1620, y: 483, w: 360, h: 366, depth: 12, accent: C.teal }, (w) => {
        label(ctx, "CHALLENGE APIs", 26, 40, C.muted, 18, 1.2);
        text(ctx, "Valio Aimo", 25, 108, 59, C.paper, { maxWidth: w - 50 });
        line(ctx, [[27, 133], [w - 27, 133]], rgba(C.muted, 0.23), 1);
        [
          ["Products", products],
          ["Fixed prices", prices],
          ["Stock", stock],
        ].forEach(([value, highlight], i) => {
          const y = 195 + i * 65;
          alpha(ctx, highlight * 0.09, () => {
            round(ctx, 15, y - 35, w - 30, 50, 8);
            ctx.fillStyle = C.lime;
            ctx.fill();
          });
          text(ctx, value, 29, y, 32, C.paper, { body: true, maxWidth: w - 60 });
          if (highlight > 0) line(ctx, [[17, y - 27], [17, y + 5]], rgba(C.lime, highlight), 3);
        });
      });

      panel(ctx, { x: 380, y: 811, w: 500, h: 132, depth: 10, accent: C.teal }, (w) => {
        alpha(ctx, external * (1 - focus * 0.6), () => line(ctx, [[26, 3], [w - 26, 3]], C.lime, 3));
        text(ctx, "External purchasing agents", 28, 54, 45, C.paper, { maxWidth: w - 55 });
        text(ctx, "Credentialed · direct access", 30, 99, 24, C.muted, { body: true, maxWidth: w - 60 });
      });

      panel(ctx, { x: 1025, y: 811, w: 420, h: 132, depth: 10, accent: C.amber }, (w) => {
        alpha(ctx, approval, () => line(ctx, [[26, 3], [w - 26, 3]], C.amber, 3));
        icon(ctx, "human", 47, 64, 46, C.amber);
        text(ctx, "Human approval", 85, 57, 41, C.paper, { maxWidth: w - 108 });
        text(ctx, "Kitchen manager", 87, 98, 24, C.muted, { body: true });
      });

      panel(ctx, { x: 1600, y: 811, w: 400, h: 132, depth: 10, accent: C.lime }, (w) => {
        alpha(ctx, Math.max(record, audit), () => line(ctx, [[26, 3], [w - 26, 3]], C.lime, 3));
        label(ctx, "LOCAL RECORDS", 25, 31, C.lime, 17, 1.5);
        text(ctx, "Mock order + audit", 24, 78, 43, C.paper, { maxWidth: w - 47 });
        text(ctx, "No backend order or payment", 26, 112, 20, C.muted, { body: true, maxWidth: w - 50 });
      });

      routePacket(ctx, workspacePath, firstTime, taskAt + 0.15, 1.15);
      routePacket(ctx, externalPath, firstTime, externalAt + 0.18, 1.8);
      if (second) {
        routePacket(ctx, dataPath, t, cue(s, "products", 0.16) + 0.12, 1.3);
        routePacket(ctx, humanPath, t, approvalAt + 0.25, 1.1, C.amber);
        routePacket(ctx, localPath, t, recordAt + 0.3, 1.35);
      }
    });
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
    const firstGroup = lines.slice(1, firstError);
    const secondGroup = lines.slice(firstError + 1, secondError);
    const firstRequest = firstGroup.filter((value) => /^POST\s/.test(value)).pop();
    const secondRequest = secondGroup.filter((value) => /^POST\s/.test(value)).pop();
    const summary = lines.slice(secondError + 1).find((value) => /^Both refused/.test(value));
    if (!firstRequest || !secondRequest || !summary || firstError >= secondError) {
      throw new Error("CinematicMotion: terminal capture must include each refusal's original POST request and the captured refusal summary.");
    }
    const bypassAt = cue(s, "bypassing approval", 0.11) - 0.1;
    const selfAt = cue(s, "Try letting", 0.36) - 0.1;
    const firstAt = cue(s, "Refused", 0.26);
    const secondAt = Math.max(firstAt + 0.9, cue(s, "Refused", 0.62, 1));
    const rulesAt = Math.max(secondAt + 0.4, cue(s, "gateway rules", 0.8) - 0.1);
    const entry = at(t, 0.03, 0.45);

    wipeText(ctx, "Guardrails, built in.", 243, 228, 108, C.paper, entry, 1537);
    alpha(ctx, entry, () => {
      label(ctx, "CAPTURED GATEWAY RESPONSES / LOCAL DEMO", 247, 281, C.muted, 19, 1.65);
      text(ctx, lines[0], 247, 331, 24, C.muted, { body: true, maxWidth: 1530 });
    });
    [
      {
        x: 616, title: "Bypass approval", number: "REQUEST 01",
        comment: firstGroup.find((value) => value.startsWith("#")),
        request: firstRequest, response: lines[firstError],
        requestAt: bypassAt, responseAt: firstAt,
      },
      {
        x: 1404, title: "Self-approval", number: "REQUEST 02",
        comment: secondGroup.find((value) => value.startsWith("#")),
        request: secondRequest, response: lines[secondError],
        requestAt: selfAt, responseAt: secondAt,
      },
    ].forEach((attempt) => {
      const shown = at(t, attempt.requestAt, 0.35);
      const response = at(t, attempt.responseAt, 0.34);
      panel(ctx, { x: attempt.x, y: 559, w: 744, h: 366, depth: 12, accent: C.teal, alpha: entry }, (w) => {
        label(ctx, attempt.number, 30, 38, C.muted, 18, 1.7);
        text(ctx, attempt.title, 27, 106, 55, C.paper, { maxWidth: w - 58 });
        line(ctx, [[30, 129], [w - 30, 129]], rgba(C.muted, 0.24), 1);
        reveal(ctx, shown, () => {
          if (attempt.comment) text(ctx, attempt.comment, 32, 170, 22, C.muted, { body: true, maxWidth: w - 64 });
          text(ctx, attempt.request, 31, 225, 30, C.paper, { body: true, bold: true, maxWidth: w - 62 });
        }, 10, 0);
        alpha(ctx, response, () => {
          round(ctx, 18, 259, w - 36, 78, 10);
          ctx.fillStyle = rgba(C.amber, 0.085);
          ctx.fill();
          line(ctx, [[20, 271], [20, 324]], C.amber, 4);
        });
        reveal(ctx, response, () => {
          text(ctx, attempt.response, 35, 307, 33, C.amber, { body: true, bold: true, maxWidth: w - 68 });
        }, 9, 0);
      });
    });
    reveal(ctx, at(t, secondAt + 0.35, 0.4), () => {
      text(ctx, summary, 247, 803, 25, C.muted, { body: true, maxWidth: 1525 });
    }, 9, 0);
    wipeText(ctx, "Gateway rules. Not just prompts.", 243, 887, 70, C.lime, at(t, rulesAt, 0.4), 1530);
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

  function ending(ctx, s, t) {
    const second = Number(s.visual && s.visual.part) === 2;
    const d = duration(s);
    const delegate = second ? 1 : at(t, Math.min(cue(s, "Delegate", 0.015), d - 1.8), 0.46);
    const control = second ? 1 : at(t, Math.min(cue(s, "Keep control", 0.47), d - 1.8), 0.46);
    const exit = second ? at(t, 0, 0.22) : 0;
    pitchFrame(ctx, second ? 1 : at(t, 0, 0.55));
    mark(ctx, 1718, 159, 67, C.lime);
    label(ctx, "VALIO AIMO", 138, 178, C.paper, 25, 3.6);
    wipeText(ctx, "Delegate the ordering.", 130, 427, 172, C.paper, delegate, 1575, exit);
    wipeText(ctx, "Keep control.", 132, 623, 184, C.lime, control, 1575, exit);
    if (second) {
      const openAt = Math.min(Math.max(0.25, cue(s, "Open", 0.025)), d - 1.9);
      const termsAt = Math.min(Math.max(0.3, cue(s, "On Valio", 0.34)), d - 1.9);
      wipeText(ctx, "Open to agents.", 129, 427, 183, C.paper, at(t, openAt, 0.46), 1582);
      wipeText(ctx, "On Valio Aimo’s terms.", 132, 623, 166, C.lime, at(t, termsAt, 0.48), 1580);
      const detailsAt = Math.min(Math.max(1.25, cue(s, "terms", 0.55) - 0.15), d - 1.9);
      const details = at(t, detailsAt, 0.4);
      reveal(ctx, details, () => {
        text(ctx, "The Delusionals · Krish Waghresha · Jakub Piotrowski · Junction 2026", 140, 813, 23, C.muted, { body: true, maxWidth: 1570 });
        text(ctx, "Synthetic systems · local mock orders · no payments", 140, 874, 25, C.muted, { body: true, maxWidth: 1570 });
      }, 9, 0);
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
