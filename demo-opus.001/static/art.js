"use strict";
// Procedural recipe illustration: a bowl drawn from the recipe's own ingredients.
// Deterministic per recipe; no external image service.
(function () {
  const FAMILIES = [
    { key: "green", color: "#7cb342", tex: "leaf", words: ["spinach", "broccoli", "cilantro", "scallion", "cucumber", "zucchini", "edamame", "avocado", "cabbage"] },
    { key: "red", color: "#e35d4f", tex: "blob", words: ["tomato", "salsa", "gochujang", "kimchi", "bell pepper"] },
    { key: "orange", color: "#f29c38", tex: "cube", words: ["sweet potato", "carrot", "mango", "cheddar"] },
    { key: "yellow", color: "#f6cf4a", tex: "kernel", words: ["corn", "pineapple", "banana", "eggs"] },
    { key: "brown", color: "#7b5a45", tex: "bean", words: ["black beans", "lentils", "peanut", "mushroom", "beef", "turkey", "soy sauce", "whole wheat"] },
    { key: "pink", color: "#f39a7b", tex: "stripe", words: ["salmon", "shrimp"] },
    { key: "protein", color: "#e9c89a", tex: "cube", words: ["chicken", "tofu", "paneer", "feta"] },
    { key: "cream", color: "#f3e6c8", tex: "grain", words: ["rice", "quinoa", "noodles", "tortilla", "naan", "pita", "oats", "chickpeas", "hummus", "yogurt", "coconut", "cashews", "bread", "potato", "apple"] },
  ];
  const SAUCES = ["soy sauce", "gochujang", "olive oil", "lime juice", "honey", "salsa", "coconut milk", "peanut butter", "sesame seeds", "garlic", "ginger"];

  function family(name) {
    const n = name.toLowerCase();
    return FAMILIES.find((f) => f.words.some((w) => n.includes(w))) || { key: "other", color: "#c5a880", tex: "grain" };
  }
  function rng(seedStr) {
    let h = 2166136261;
    for (const c of seedStr) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
    return () => { h += 0x6d2b79f5; let t = h; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }
  const shade = (hex, amt) => {
    const n = parseInt(hex.slice(1), 16);
    const c = (v) => Math.max(0, Math.min(255, Math.round(v + amt)));
    return `rgb(${c(n >> 16)},${c((n >> 8) & 255)},${c(n & 255)})`;
  };

  function texture(fam, r, cx, cy, a0, a1, R) {
    let out = "";
    const count = { grain: 70, leaf: 16, blob: 14, cube: 11, kernel: 30, bean: 22, stripe: 7 }[fam.tex] || 30;
    for (let i = 0; i < count; i++) {
      const a = a0 + (a1 - a0) * (0.06 + 0.88 * r());
      const d = R * (0.22 + 0.72 * Math.sqrt(r()));
      const x = cx + d * Math.cos(a), y = cy + d * Math.sin(a);
      const rot = (r() * 360).toFixed(0);
      const light = shade(fam.color, 28), dark = shade(fam.color, -30);
      switch (fam.tex) {
        case "grain": out += `<ellipse cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" rx="4.2" ry="2" fill="${r() > .5 ? light : "#fffaf0"}" opacity=".9" transform="rotate(${rot} ${x.toFixed(1)} ${y.toFixed(1)})"/>`; break;
        case "leaf": out += `<path d="M${x},${y} q8,-10 16,0 q-8,10 -16,0z" fill="${r() > .5 ? dark : light}" transform="rotate(${rot} ${x} ${y})"/>`; break;
        case "blob": out += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(5 + r() * 6).toFixed(1)}" fill="${r() > .4 ? light : dark}" opacity=".85"/>`; break;
        case "cube": out += `<rect x="${(x - 8).toFixed(1)}" y="${(y - 8).toFixed(1)}" width="16" height="16" rx="4" fill="${r() > .5 ? light : shade(fam.color, 10)}" stroke="${dark}" stroke-opacity=".25" transform="rotate(${rot} ${x.toFixed(1)} ${y.toFixed(1)})"/>`; break;
        case "kernel": out += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.6" fill="${r() > .5 ? light : dark}"/>`; break;
        case "bean": out += `<ellipse cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" rx="6" ry="3.6" fill="${r() > .5 ? dark : shade(fam.color, -50)}" transform="rotate(${rot} ${x.toFixed(1)} ${y.toFixed(1)})"/>`; break;
        case "stripe": out += `<g transform="rotate(${rot} ${x.toFixed(1)} ${y.toFixed(1)})"><rect x="${(x - 14).toFixed(1)}" y="${(y - 8).toFixed(1)}" width="28" height="16" rx="5" fill="${fam.color}"/><path d="M${x - 8},${y - 7} l3,14 M${x},${y - 8} l3,16 M${x + 8},${y - 7} l3,14" stroke="#fff" stroke-opacity=".7" stroke-width="1.6"/></g>`; break;
      }
    }
    return out;
  }

  window.recipeArt = function (card) {
    const W = 960, H = 440, cx = 480, cy = 222, R = 160;
    const r = rng(card.title + card.ingredients.map((i) => i.name).join());
    const solids = card.ingredients.filter((i) => !SAUCES.some((s) => i.name.includes(s)));
    const sauces = card.ingredients.filter((i) => SAUCES.some((s) => i.name.includes(s)));
    const parts = (solids.length ? solids : card.ingredients).slice(0, 6);
    const weights = parts.map((p) => Math.sqrt(p.grams));
    const total = weights.reduce((a, b) => a + b, 0);
    let a = -Math.PI / 2 + r() * 0.6, wedges = "", textures = "";
    parts.forEach((p, i) => {
      const span = (weights[i] / total) * Math.PI * 2;
      const a0 = a, a1 = a + span; a = a1;
      const fam = family(p.name);
      const large = span > Math.PI ? 1 : 0;
      const x0 = cx + R * Math.cos(a0), y0 = cy + R * Math.sin(a0), x1 = cx + R * Math.cos(a1), y1 = cy + R * Math.sin(a1);
      wedges += `<path d="M${cx},${cy} L${x0.toFixed(1)},${y0.toFixed(1)} A${R},${R} 0 ${large} 1 ${x1.toFixed(1)},${y1.toFixed(1)} Z" fill="${fam.color}"/>`;
      textures += texture(fam, r, cx, cy, a0, a1, R);
    });
    const drizzle = sauces.slice(0, 2).map((s, i) => {
      const col = family(s.name).color === "#c5a880" ? "#8d5a2b" : shade(family(s.name).color, -20);
      const off = i * 26 - 13;
      return `<path d="M${cx - 120},${cy + off - 20} C${cx - 60},${cy + off - 70} ${cx - 10},${cy + off + 40} ${cx + 50},${cy + off - 10} S${cx + 120},${cy + off + 20} ${cx + 130},${cy + off - 30}" fill="none" stroke="${col}" stroke-width="5" stroke-linecap="round" opacity=".75"/>`;
    }).join("");
    let garnish = "";
    for (let i = 0; i < 26; i++) {
      const ang = r() * Math.PI * 2, d = R * 0.55 * Math.sqrt(r());
      const x = cx + d * Math.cos(ang), y = cy + d * Math.sin(ang);
      garnish += i % 3 ? `<ellipse cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" rx="2.6" ry="1.5" fill="#fffdf5" stroke="#d8c9a6" stroke-width=".5" transform="rotate(${(r() * 180).toFixed(0)} ${x.toFixed(1)} ${y.toFixed(1)})"/>`
        : `<path d="M${x},${y} q5,-6 10,0 q-5,6 -10,0z" fill="#3f8f3a"/>`;
    }
    let table = "";
    for (let i = 0; i < 9; i++) {
      const x = 40 + r() * 880, y = 30 + r() * 380;
      if (Math.hypot(x - cx, y - cy) < R + 70) continue;
      table += `<path d="M${x},${y} q9,-11 18,0 q-9,11 -18,0z" fill="#6aa84f" opacity=".55" transform="rotate(${(r() * 360).toFixed(0)} ${x.toFixed(1)} ${y.toFixed(1)})"/>`;
    }
    return `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Illustration of ${card.title.replace(/"/g, "")}">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fbf6ee"/><stop offset="1" stop-color="#efe5d6"/></linearGradient>
        <radialGradient id="plate" cx=".45" cy=".4" r=".7"><stop offset="0" stop-color="#ffffff"/><stop offset=".8" stop-color="#f4f1ec"/><stop offset="1" stop-color="#e2ddd4"/></radialGradient>
        <radialGradient id="shine" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#fff" stop-opacity=".35"/><stop offset=".6" stop-color="#fff" stop-opacity="0"/></radialGradient>
        <clipPath id="bowl"><circle cx="${cx}" cy="${cy}" r="${R}"/></clipPath>
        <filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="14"/></filter>
      </defs>
      <rect width="${W}" height="${H}" fill="url(#bg)"/>
      <rect x="70" y="290" width="190" height="120" rx="8" fill="#dfe9f5" transform="rotate(-12 165 350)"/>
      <rect x="70" y="290" width="190" height="120" rx="8" fill="none" stroke="#c6d7ec" stroke-width="3" stroke-dasharray="2 8" transform="rotate(-12 165 350)"/>
      <rect x="715" y="80" width="14" height="300" rx="7" fill="#c49a6c" transform="rotate(14 722 230)"/>
      <rect x="745" y="80" width="14" height="300" rx="7" fill="#b88a5c" transform="rotate(10 752 230)"/>
      ${table}
      <ellipse cx="${cx + 14}" cy="${cy + 24}" rx="${R + 46}" ry="${R + 34}" fill="#6b5b45" opacity=".22" filter="url(#soft)"/>
      <circle cx="${cx}" cy="${cy}" r="${R + 34}" fill="url(#plate)"/>
      <circle cx="${cx}" cy="${cy}" r="${R + 4}" fill="#e9e3d8"/>
      <g clip-path="url(#bowl)">${wedges}${textures}${drizzle}${garnish}</g>
      <circle cx="${cx}" cy="${cy}" r="${R}" fill="url(#shine)"/>
    </svg>`;
  };
})();
