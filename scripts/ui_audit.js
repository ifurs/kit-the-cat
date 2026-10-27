// Layout audit for the sandbox UI: paste into the page (browser devtools, or a browser tool's JS runner) at a phone
// width (375×812) and at desktop. Returns {width, overflowX, offscreen, overlaps, smallTargets}; all empty = good.
//   offscreen    — visible controls that stick out of the viewport horizontally
//   overlaps     — pairs of clickable things that cover each other (dropdowns/popups over content are ignored)
//   smallTargets — buttons smaller than 32px on a touch screen (finger-sized targets)
// Elements clipped by a scrolling/overflow:hidden ancestor are measured by their visible part only.
(() => {
  const W = document.documentElement.clientWidth;
  const sel = 'button, a, input, select, textarea, [role=button], .tab, .chip';
  const visible = el => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const clipped = el => {  // intersect the box with every clipping ancestor
    let r = el.getBoundingClientRect(), box = {l: r.left, t: r.top, r: r.right, b: r.bottom};
    for (let p = el.parentElement; p; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (/(auto|scroll|hidden|clip)/.test(s.overflow + s.overflowX + s.overflowY)) {
        const q = p.getBoundingClientRect();
        box = {l: Math.max(box.l, q.left), t: Math.max(box.t, q.top), r: Math.min(box.r, q.right), b: Math.min(box.b, q.bottom)};
      }
    }
    return box.r - box.l > 1 && box.b - box.t > 1 ? box : null;
  };
  const floating = el => !!el.closest('.popup, .menu, .dropdown, dialog, [role=dialog], [role=menu], .toast');
  const name = el => (el.id ? '#' + el.id : el.tagName.toLowerCase() + (el.className && typeof el.className === 'string'
    ? '.' + el.className.trim().split(/\s+/).join('.') : '')) + ' «' + (el.innerText || el.value || el.title || '').trim().slice(0, 24) + '»';
  const els = [...document.querySelectorAll(sel)].filter(visible).map(el => ({el, box: clipped(el)})).filter(x => x.box);
  const offscreen = els.filter(({box}) => box.l < -1 || box.r > W + 1).map(({el, box}) => `${name(el)} x=${box.l | 0}…${box.r | 0}`);
  const overlaps = [];
  for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
    const a = els[i], b = els[j];
    if (a.el.contains(b.el) || b.el.contains(a.el) || floating(a.el) !== floating(b.el)) continue;
    const w = Math.min(a.box.r, b.box.r) - Math.max(a.box.l, b.box.l), h = Math.min(a.box.b, b.box.b) - Math.max(a.box.t, b.box.t);
    if (w > 2 && h > 2) overlaps.push(`${name(a.el)} ⨯ ${name(b.el)} (${w | 0}×${h | 0}px)`);
  }
  const touch = matchMedia('(pointer: coarse)').matches;
  const smallTargets = touch ? els.filter(({el}) => el.matches('button, [role=button], .tab, .chip'))
    .filter(({el}) => { const r = el.getBoundingClientRect(); return r.height < 32 || r.width < 32; })
    .map(({el}) => { const r = el.getBoundingClientRect(); return `${name(el)} ${r.width | 0}×${r.height | 0}`; }) : [];
  return {width: W, overflowX: document.documentElement.scrollWidth > W + 1, offscreen, overlaps: overlaps.slice(0, 30), smallTargets};
})();
