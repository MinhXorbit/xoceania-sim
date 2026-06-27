(function () {
  "use strict";
  var SVGNS = "http://www.w3.org/2000/svg";
  var stage = document.getElementById("pond-stage");
  if (!stage) return;

  var VW = 420, VH = 320;
  var PX0 = 16, PY0 = 58, PX1 = 404, PY1 = 286;       // pond rectangle
  var COLS = 4, ROWS = 3;
  var CW = (PX1 - PX0) / COLS, CH = (PY1 - PY0) / ROWS;
  var CUSTODY = 9.0;                                    // seconds = the 24 h window

  function el(n, a){ var e = document.createElementNS(SVGNS, n); for (var k in a) e.setAttribute(k, a[k]); return e; }
  function clamp(v, lo, hi){ return v < lo ? lo : v > hi ? hi : v; }
  function cx(c){ return PX0 + CW * (c + 0.5); }
  function cy(r){ return PY0 + CH * (r + 0.5); }
  function cellLabel(c, r){ return "ABCD".charAt(c) + (r + 1); }
  function statusColor(d){ return d >= 5 ? "#5EEAD4" : d >= 3 ? "#FFC14D" : "#F0734A"; }

  var svg = el("svg", { viewBox: "0 0 " + VW + " " + VH, width: "100%", role: "img",
    "aria-label": "Overhead map of a shrimp pond: sensor pods across the water, three aerators sending out oxygen ripples, fish drifting toward the oxygen, and a drone flying a scan path. Each scanned zone shows how long the drone keeps custody of its data before it syncs." });

  svg.appendChild(el("rect", { x: PX0-4, y: PY0-4, width: (PX1-PX0)+8, height: (PY1-PY0)+8, rx: 18, fill: "#0c3038" }));
  var water = el("rect", { x: PX0, y: PY0, width: PX1-PX0, height: PY1-PY0, rx: 14, fill: "#15545f" });
  svg.appendChild(water);

  var grid = el("g", {});
  for (var c = 1; c < COLS; c++) grid.appendChild(el("line", { x1: PX0+CW*c, y1: PY0, x2: PX0+CW*c, y2: PY1, stroke: "#0c3a43", "stroke-width": 1 }));
  for (var r = 1; r < ROWS; r++) grid.appendChild(el("line", { x1: PX0, y1: PY0+CH*r, x2: PX1, y2: PY0+CH*r, stroke: "#0c3a43", "stroke-width": 1 }));
  svg.appendChild(grid);

  // captured-zone overlays (one per cell)
  var capLayer = el("g", {}), cells = [];
  for (var ri = 0; ri < ROWS; ri++) for (var ci = 0; ci < COLS; ci++){
    var g = el("g", {});
    var rect = el("rect", { x: PX0+CW*ci+2, y: PY0+CH*ri+2, width: CW-4, height: CH-4, rx: 6, fill: "#5EEAD4", opacity: 0 });
    var ring = el("circle", { cx: PX0+CW*ci+CW-13, cy: PY0+CH*ri+13, r: 6, fill: "none", stroke: "#5EEAD4", "stroke-width": 2.2, opacity: 0, transform: "rotate(-90 "+(PX0+CW*ci+CW-13)+" "+(PY0+CH*ri+13)+")" });
    var tick = el("path", { d: "M"+(PX0+CW*ci+CW-16)+","+(PY0+CH*ri+13)+" l 2,3 l 4,-5", fill: "none", stroke: "#5EEAD4", "stroke-width": 1.6, opacity: 0 });
    g.appendChild(rect); g.appendChild(ring); g.appendChild(tick); capLayer.appendChild(g);
    cells.push({ c: ci, r: ri, captured: false, at: -99, rect: rect, ring: ring, tick: tick, circ: 2*Math.PI*6 });
  }
  svg.appendChild(capLayer);

  // aerators with oxygen ripples
  var aerLayer = el("g", {}); svg.appendChild(aerLayer);
  var aerators = [{c:3,r:0},{c:0,r:1},{c:2,r:2}].map(function(a){
    var x = cx(a.c), y = cy(a.r), g = el("g", {});
    var rings = [0,1,2].map(function(i){ var rc = el("circle", { cx:x, cy:y, r:6, fill:"none", stroke:"#9beede", "stroke-width":1.5, opacity:0 }); g.appendChild(rc); return rc; });
    g.appendChild(el("rect", { x:x-7, y:y-7, width:14, height:14, rx:3, fill:"#0E2336", stroke:"#8fb0bf", "stroke-width":1.5 }));
    g.appendChild(el("line", { x1:x-5, y1:y, x2:x+5, y2:y, stroke:"#8fb0bf", "stroke-width":1.5 }));
    g.appendChild(el("line", { x1:x, y1:y-5, x2:x, y2:y+5, stroke:"#8fb0bf", "stroke-width":1.5 }));
    aerLayer.appendChild(g); return { x:x, y:y, rings:rings, ph:Math.random()*1 };
  });

  // sensor pods (buckets)
  var podLayer = el("g", {}); svg.appendChild(podLayer);
  var podDefs = [[0,0,6.4],[2,0,6.1],[3,1,5.7],[1,1,6.0],[0,2,5.5],[3,2,6.2]];
  var pods = podDefs.map(function(p){
    var x = cx(p[0]), y = cy(p[1]), col = statusColor(p[2]);
    podLayer.appendChild(el("circle", { cx:x, cy:y, r:9, fill:"#08222b", stroke:col, "stroke-width":2 }));
    var dot = el("circle", { cx:x, cy:y, r:4, fill:col }); podLayer.appendChild(dot);
    var lab = el("text", { x:x, y:y+20, fill:"#cfe3ee", "font-size":10.5, "text-anchor":"middle", "font-family":"sans-serif" });
    lab.textContent = p[2].toFixed(1); podLayer.appendChild(lab);
    return { x:x, y:y, base:p[2], dot:dot, lab:lab };
  });

  // fish
  var fishLayer = el("g", {}); svg.appendChild(fishLayer);
  var fish = [];
  for (var f = 0; f < 26; f++){
    var g = el("g", {});
    g.appendChild(el("path", { d:"M5,0 L-5,-2.6 L-2,0 L-5,2.6 Z", fill:"#cfe7ef", stroke:"#7fb6c4", "stroke-width":0.4 }));
    fishLayer.appendChild(g);
    fish.push({ el:g, x: PX0+10+Math.random()*(PX1-PX0-20), y: PY0+10+Math.random()*(PY1-PY0-20),
      vx:(Math.random()-0.5), vy:(Math.random()-0.5), ph:Math.random()*6.28 });
  }

  // drone + scan footprint
  var fpLayer = el("g", {}); svg.appendChild(fpLayer);
  var footprint = el("rect", { x:0, y:0, width:CW-6, height:CH-6, rx:6, fill:"#5EEAD4", opacity:0.10, stroke:"#5EEAD4", "stroke-width":1.4 });
  var scanLine = el("line", { x1:0, y1:0, x2:0, y2:0, stroke:"#5EEAD4", "stroke-width":1, opacity:0.7 });
  fpLayer.appendChild(footprint); fpLayer.appendChild(scanLine);
  var drone = el("g", {});
  [[-7,-7],[7,-7],[-7,7],[7,7]].forEach(function(p){ drone.appendChild(el("circle", { cx:p[0], cy:p[1], r:4, fill:"none", stroke:"#5EEAD4", "stroke-width":1.3 })); });
  drone.appendChild(el("line", { x1:-7, y1:-7, x2:7, y2:7, stroke:"#3f7f86", "stroke-width":1.2 }));
  drone.appendChild(el("line", { x1:7, y1:-7, x2:-7, y2:7, stroke:"#3f7f86", "stroke-width":1.2 }));
  drone.appendChild(el("rect", { x:-4, y:-4, width:8, height:8, rx:2, fill:"#0E2336", stroke:"#5EEAD4", "stroke-width":1.3 }));
  drone.appendChild(el("circle", { cx:0, cy:0, r:1.6, fill:"#F0734A" }));
  fpLayer.appendChild(drone);

  // serpentine waypoints over the cells
  var wps = [];
  for (var rr = 0; rr < ROWS; rr++){
    var order = rr % 2 === 0 ? [0,1,2,3] : [3,2,1,0];
    order.forEach(function(cc){ wps.push({ c:cc, r:rr, x:cx(cc), y:cy(rr) }); });
  }
  var dpos = { x: wps[0].x, y: wps[0].y }, widx = 0, dstate = "move", dwellEnd = 0, seeded = false;

  // HUD
  function txt(x,y,s,fill,size,anchor,weight){ var t = el("text",{x:x,y:y,fill:fill,"font-size":size,"text-anchor":anchor||"start","font-family":"sans-serif","font-weight":weight||"400"}); t.textContent=s; svg.appendChild(t); return t; }
  txt(16, 26, "Pond A-3", "#E8F2F5", 15, "start", "600");
  txt(16, 44, "overhead · 6 pods · 3 aerators", "#7C97A6", 11.5);
  var hScan = txt(VW-16, 26, "Drone ▸ A1", "#5EEAD4", 12.5, "end", "600");
  var hCust = txt(VW-16, 44, "custody 0 zones", "#A6BBC8", 11, "end");

  stage.appendChild(svg);

  // controls + hooks
  var btnPlay = document.getElementById("pond-play");
  var playing = true, last = 0;
  if (btnPlay) btnPlay.addEventListener("click", function(){ playing = !playing;
    btnPlay.innerHTML = playing ? '<i class="ti ti-player-pause"></i> Pause' : '<i class="ti ti-player-play"></i> Play';
    if (playing){ last = 0; requestAnimationFrame(loop); } });
  window.__pondAutopilot = function(){ aerators.forEach(function(a){ a.boost = true; }); };

  function nearestAer(x, y){ var best = aerators[0], bd = 1e9;
    aerators.forEach(function(a){ var d = (a.x-x)*(a.x-x)+(a.y-y)*(a.y-y); if (d < bd){ bd = d; best = a; } }); return best; }

  function loop(ts){
    if (!last) last = ts; var dt = Math.min(0.05, (ts - last) / 1000); last = ts;
    var t = ts / 1000;

    // On first frame, seed a few already-scanned zones at staggered custody ages
    // so the data-custody story is visible immediately (the drone has history).
    if (!seeded){ seeded = true;
      [[1,0,3.5],[2,0,6.5],[3,1,8.4],[0,2,5.0]].forEach(function(s){
        var cl = cells[s[1] * COLS + s[0]]; cl.captured = true; cl.at = t - s[2]; });
    }

    // aerator ripples
    aerators.forEach(function(a){ a.ph = (a.ph + dt * 0.6) % 1;
      a.rings.forEach(function(rc, i){ var p = (a.ph + i/3) % 1; rc.setAttribute("r", (6 + p * 26).toFixed(1)); rc.setAttribute("opacity", (0.5 * (1 - p)).toFixed(2)); });
    });

    // pods flicker slightly
    pods.forEach(function(p){ var d = p.base + Math.sin(t*0.5 + p.x)*0.15; p.lab.textContent = d.toFixed(1); });

    // drone movement along waypoints
    if (playing){
      if (dstate === "move"){
        var w = wps[widx], dx = w.x - dpos.x, dy = w.y - dpos.y, dist = Math.hypot(dx, dy), sp = 70 * dt;
        if (dist < sp + 0.5){ dpos.x = w.x; dpos.y = w.y; dstate = "dwell"; dwellEnd = t + 0.55;
          var cell = cells[w.r * COLS + w.c]; cell.captured = true; cell.at = t; }
        else { dpos.x += dx / dist * sp; dpos.y += dy / dist * sp; }
      } else { if (t >= dwellEnd){ widx = (widx + 1) % wps.length; dstate = "move"; } }
    }
    drone.setAttribute("transform", "translate(" + dpos.x.toFixed(1) + "," + dpos.y.toFixed(1) + ")");
    footprint.setAttribute("x", (dpos.x - (CW-6)/2).toFixed(1)); footprint.setAttribute("y", (dpos.y - (CH-6)/2).toFixed(1));
    footprint.setAttribute("opacity", dstate === "dwell" ? 0.20 : 0.10);
    var sweep = dpos.y - (CH-6)/2 + ((t*60) % (CH-6));
    scanLine.setAttribute("x1", (dpos.x-(CW-6)/2).toFixed(1)); scanLine.setAttribute("x2", (dpos.x+(CW-6)/2).toFixed(1));
    scanLine.setAttribute("y1", sweep.toFixed(1)); scanLine.setAttribute("y2", sweep.toFixed(1));
    scanLine.setAttribute("opacity", dstate === "dwell" ? 0.7 : 0);
    var cur = wps[widx]; hScan.textContent = "Drone ▸ " + cellLabel(cur.c, cur.r);

    // custody rendering
    var held = 0;
    cells.forEach(function(cell){
      if (!cell.captured) return;
      var age = t - cell.at, frac = clamp(age / CUSTODY, 0, 1);
      if (frac < 1){ held++;
        cell.rect.setAttribute("opacity", (0.14 * (1 - frac) + 0.05).toFixed(3));
        cell.ring.setAttribute("opacity", 1);
        cell.ring.setAttribute("stroke", age < CUSTODY * 0.6 ? "#5EEAD4" : "#FFC14D");
        cell.ring.setAttribute("stroke-dasharray", cell.circ.toFixed(1));
        cell.ring.setAttribute("stroke-dashoffset", (cell.circ * frac).toFixed(1));
        cell.tick.setAttribute("opacity", 0);
      } else {
        cell.rect.setAttribute("opacity", 0.045);
        cell.ring.setAttribute("opacity", 0.25);
        cell.ring.setAttribute("stroke", "#5EEAD4");
        cell.ring.setAttribute("stroke-dashoffset", 0);
        cell.tick.setAttribute("opacity", 0.8);
      }
    });
    hCust.textContent = "custody " + held + " zone" + (held === 1 ? "" : "s") + " · 24 h on-device";

    // fish drift toward oxygen (nearest aerator), with wander + bounds
    fish.forEach(function(fi){
      var a = nearestAer(fi.x, fi.y), ax = a.x - fi.x, ay = a.y - fi.y, ad = Math.hypot(ax, ay) + 0.01;
      var pull = (a.boost ? 0.05 : 0.03);
      fi.vx += (ax/ad) * pull + (Math.random()-0.5) * 0.10;
      fi.vy += (ay/ad) * pull + (Math.random()-0.5) * 0.10;
      var sp = Math.hypot(fi.vx, fi.vy), mx = 1.5; if (sp > mx){ fi.vx = fi.vx/sp*mx; fi.vy = fi.vy/sp*mx; }
      fi.x += fi.vx * (1 + dt*30); fi.y += fi.vy * (1 + dt*30);
      if (fi.x < PX0+8){ fi.x = PX0+8; fi.vx = Math.abs(fi.vx); } else if (fi.x > PX1-8){ fi.x = PX1-8; fi.vx = -Math.abs(fi.vx); }
      if (fi.y < PY0+8){ fi.y = PY0+8; fi.vy = Math.abs(fi.vy); } else if (fi.y > PY1-8){ fi.y = PY1-8; fi.vy = -Math.abs(fi.vy); }
      var ang = Math.atan2(fi.vy, fi.vx) * 180 / Math.PI;
      fi.el.setAttribute("transform", "translate("+fi.x.toFixed(1)+","+fi.y.toFixed(1)+") rotate("+ang.toFixed(0)+") scale(0.95)");
    });

    if (playing) requestAnimationFrame(loop); else last = 0;
  }

  if ("IntersectionObserver" in window){
    var io = new IntersectionObserver(function(en){ en.forEach(function(e){ if (e.isIntersecting){ last = 0; requestAnimationFrame(loop); io.disconnect(); } }); }, { threshold: 0.15 });
    io.observe(stage);
  } else requestAnimationFrame(loop);
})();
