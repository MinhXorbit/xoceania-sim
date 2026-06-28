(function () {
  "use strict";
  var SVGNS = "http://www.w3.org/2000/svg";
  var T = window.XO_TWIN;
  var stage = document.getElementById("pond-stage");
  var gstage = document.getElementById("live-graph");
  if (!T || !stage || !gstage) return;

  function el(n, a){ var e = document.createElementNS(SVGNS, n); for (var k in a) e.setAttribute(k, a[k]); return e; }
  function lerp(a, b, t){ return a + (b - a) * t; }
  function clamp(v, lo, hi){ return v < lo ? lo : v > hi ? hi : v; }
  function hx(h){ h = h.replace("#",""); return [parseInt(h.substr(0,2),16),parseInt(h.substr(2,2),16),parseInt(h.substr(4,2),16)]; }
  function mix(c1, c2, t){ var a = hx(c1), b = hx(c2); return "rgb(" + Math.round(lerp(a[0],b[0],t)) + "," + Math.round(lerp(a[1],b[1],t)) + "," + Math.round(lerp(a[2],b[2],t)) + ")"; }

  var HOURS = T.hours, HMAX = HOURS[HOURS.length - 1], THR = T.threshold;
  function interp(arr, t){ t = clamp(t, 0, HMAX); var i = Math.floor(t), f = t - i; return lerp(arr[i], arr[Math.min(i+1, arr.length-1)], f); }
  function doNothingAt(t){ return interp(T.do_nothing, t); }
  function autoAt(t){ return interp(T.autonomous, t); }

  // shared state
  var t = 0, playing = true, engaged = false, engageT = 0, last = 0;
  function curDO(tt){
    if (!engaged) return doNothingAt(tt);
    if (tt < engageT) return doNothingAt(tt);
    var off = doNothingAt(engageT) - autoAt(engageT);
    return autoAt(tt) + off * Math.exp(-(tt - engageT) / 2.5);
  }
  function statusOf(d){ return d >= 5 ? ["Healthy","#5EEAD4"] : d >= 3 ? ["Stressed","#FFC14D"] : ["Critical","#F0734A"]; }

  /* ---------------- POND (overhead) ---------------- */
  var VW = 420, VH = 300, PX0 = 16, PY0 = 54, PX1 = 404, PY1 = 286, COLS = 4, ROWS = 3;
  var CW = (PX1-PX0)/COLS, CH = (PY1-PY0)/ROWS;
  function cx(c){ return PX0 + CW*(c+0.5); } function cy(r){ return PY0 + CH*(r+0.5); }
  function clabel(c, r){ return "ABCD".charAt(c) + (r+1); }

  var psvg = el("svg", { viewBox:"0 0 "+VW+" "+VH, width:"100%", role:"img",
    "aria-label":"Overhead pond from the xOceania digital twin: sensor pods, aerators, shrimp that suffer as oxygen falls, and a drone scanning the grid. Hand control to the drone and the aerators switch on, oxygen recovers and the shrimp revive." });
  psvg.appendChild(el("rect", { x:PX0-4, y:PY0-4, width:(PX1-PX0)+8, height:(PY1-PY0)+8, rx:18, fill:"#0c3038" }));
  var water = el("rect", { x:PX0, y:PY0, width:PX1-PX0, height:PY1-PY0, rx:14, fill:"#15545f" });
  psvg.appendChild(water);
  var g = el("g", {});
  for (var c1 = 1; c1 < COLS; c1++) g.appendChild(el("line", { x1:PX0+CW*c1, y1:PY0, x2:PX0+CW*c1, y2:PY1, stroke:"#0c3a43", "stroke-width":1 }));
  for (var r1 = 1; r1 < ROWS; r1++) g.appendChild(el("line", { x1:PX0, y1:PY0+CH*r1, x2:PX1, y2:PY0+CH*r1, stroke:"#0c3a43", "stroke-width":1 }));
  psvg.appendChild(g);

  // captured zones (custody)
  var capLayer = el("g", {}), cells = [];
  for (var ri = 0; ri < ROWS; ri++) for (var ci = 0; ci < COLS; ci++){
    var gg = el("g", {}), rx = PX0+CW*ci, ry = PY0+CH*ri;
    var rect = el("rect", { x:rx+2, y:ry+2, width:CW-4, height:CH-4, rx:6, fill:"#5EEAD4", opacity:0 });
    var ring = el("circle", { cx:rx+CW-12, cy:ry+12, r:5.5, fill:"none", stroke:"#5EEAD4", "stroke-width":2, opacity:0, transform:"rotate(-90 "+(rx+CW-12)+" "+(ry+12)+")" });
    gg.appendChild(rect); gg.appendChild(ring); capLayer.appendChild(gg);
    cells.push({ c:ci, r:ri, captured:false, at:-99, rect:rect, ring:ring, circ:2*Math.PI*5.5 });
  }
  psvg.appendChild(capLayer);

  // aerators
  var aerLayer = el("g", {}); psvg.appendChild(aerLayer);
  var aerators = [{c:3,r:0},{c:0,r:1},{c:2,r:2}].map(function(a){
    var x = cx(a.c), y = cy(a.r), grp = el("g", {});
    var halo = el("circle", { cx:x, cy:y, r:13, fill:"none", stroke:"#5EEAD4", "stroke-width":2, opacity:0 }); grp.appendChild(halo);
    var rings = [0,1,2].map(function(){ var rc = el("circle", { cx:x, cy:y, r:6, fill:"none", stroke:"#9beede", "stroke-width":1.5, opacity:0 }); grp.appendChild(rc); return rc; });
    grp.appendChild(el("rect", { x:x-7, y:y-7, width:14, height:14, rx:3, fill:"#0E2336", stroke:"#8fb0bf", "stroke-width":1.5 }));
    grp.appendChild(el("line", { x1:x-5, y1:y, x2:x+5, y2:y, stroke:"#8fb0bf", "stroke-width":1.5 }));
    grp.appendChild(el("line", { x1:x, y1:y-5, x2:x, y2:y+5, stroke:"#8fb0bf", "stroke-width":1.5 }));
    aerLayer.appendChild(grp); return { x:x, y:y, rings:rings, halo:halo, ph:Math.random(), on:false };
  });

  // pods
  var podLayer = el("g", {}); psvg.appendChild(podLayer);
  var pods = [[0,0,0.3],[2,0,0.0],[3,1,-0.4],[1,1,0.1],[0,2,-0.6],[3,2,0.2]].map(function(p){
    var x = cx(p[0]), y = cy(p[1]);
    var ring = el("circle", { cx:x, cy:y, r:9, fill:"#08222b", stroke:"#5EEAD4", "stroke-width":2 });
    var dot = el("circle", { cx:x, cy:y, r:4, fill:"#5EEAD4" });
    var lab = el("text", { x:x, y:y+20, fill:"#cfe3ee", "font-size":10.5, "text-anchor":"middle", "font-family":"sans-serif" });
    podLayer.appendChild(ring); podLayer.appendChild(dot); podLayer.appendChild(lab);
    return { x:x, y:y, off:p[2], ring:ring, dot:dot, lab:lab };
  });

  // fish
  var fishLayer = el("g", {}); psvg.appendChild(fishLayer);
  var fish = [];
  for (var f = 0; f < 24; f++){
    var fg = el("g", {});
    var body = el("path", { d:"M5,0 L-5,-2.6 L-2,0 L-5,2.6 Z", fill:"#bfe9dd", stroke:"#5fae9c", "stroke-width":0.4 });
    fg.appendChild(body); fishLayer.appendChild(fg);
    fish.push({ el:fg, body:body, x:PX0+12+Math.random()*(PX1-PX0-24), y:PY0+12+Math.random()*(PY1-PY0-24), vx:(Math.random()-0.5), vy:(Math.random()-0.5) });
  }

  // drone + footprint
  var fpLayer = el("g", {}); psvg.appendChild(fpLayer);
  var footprint = el("rect", { x:0, y:0, width:CW-6, height:CH-6, rx:6, fill:"#5EEAD4", opacity:0.10, stroke:"#5EEAD4", "stroke-width":1.4 });
  fpLayer.appendChild(footprint);
  var drone = el("g", {});
  [[-7,-7],[7,-7],[-7,7],[7,7]].forEach(function(p){ drone.appendChild(el("circle", { cx:p[0], cy:p[1], r:4, fill:"none", stroke:"#5EEAD4", "stroke-width":1.3 })); });
  drone.appendChild(el("line", { x1:-7, y1:-7, x2:7, y2:7, stroke:"#3f7f86", "stroke-width":1.2 }));
  drone.appendChild(el("line", { x1:7, y1:-7, x2:-7, y2:7, stroke:"#3f7f86", "stroke-width":1.2 }));
  drone.appendChild(el("rect", { x:-4, y:-4, width:8, height:8, rx:2, fill:"#0E2336", stroke:"#5EEAD4", "stroke-width":1.3 }));
  var droneCore = el("circle", { cx:0, cy:0, r:1.7, fill:"#F0734A" }); drone.appendChild(droneCore);
  fpLayer.appendChild(drone);

  var wps = [];
  for (var rr = 0; rr < ROWS; rr++){ var ord = rr % 2 === 0 ? [0,1,2,3] : [3,2,1,0]; ord.forEach(function(cc){ wps.push({ c:cc, r:rr, x:cx(cc), y:cy(rr) }); }); }
  var dpos = { x:wps[0].x, y:wps[0].y }, widx = 0, dstate = "move", dwellEnd = 0, seeded = false;

  function ptxt(x,y,s,fill,size,anchor,weight){ var n = el("text",{x:x,y:y,fill:fill,"font-size":size,"text-anchor":anchor||"start","font-family":"sans-serif","font-weight":weight||"400"}); n.textContent=s; psvg.appendChild(n); return n; }
  ptxt(16, 24, "Pond A-3", "#E8F2F5", 15, "start", "600");
  ptxt(16, 41, "overhead · digital twin", "#7C97A6", 11);
  var pHud = ptxt(VW-16, 24, "Drone ▸ scanning", "#5EEAD4", 12.5, "end", "600");
  var pHud2 = ptxt(VW-16, 41, "monitoring", "#A6BBC8", 11, "end");
  stage.appendChild(psvg);

  /* ---------------- LIVE GRAPH ---------------- */
  var GW = 380, GH = 168, GX0 = 32, GX1 = 372, GY0 = 12, GY1 = 146;
  function xg(tt){ return GX0 + tt/HMAX*(GX1-GX0); }
  function yg(d){ return GY1 - clamp(d,0,9)/9*(GY1-GY0); }
  var gsvg = el("svg", { viewBox:"0 0 "+GW+" "+GH, width:"100%", role:"img", "aria-label":"Live dissolved-oxygen graph driven by the digital twin." });
  gsvg.appendChild(el("line", { x1:GX0, y1:GY1, x2:GX1, y2:GY1, stroke:"#14304a", "stroke-width":1 }));
  gsvg.appendChild(el("line", { x1:GX0, y1:yg(5), x2:GX1, y2:yg(5), stroke:"#FFC14D", "stroke-width":1.3, "stroke-dasharray":"5 4" }));
  var gThrLab = el("text", { x:GX0+2, y:yg(5)-4, fill:"#FFC14D", "font-size":10.5, "font-family":"sans-serif" }); gThrLab.textContent = "stress 5 mg/L"; gsvg.appendChild(gThrLab);
  [0,5,9].forEach(function(d){ var n = el("text",{x:GX0-5,y:yg(d)+3,fill:"#7C97A6","font-size":10,"text-anchor":"end","font-family":"sans-serif"}); n.textContent=d; gsvg.appendChild(n); });
  // ghost no-action full path
  var ghostPts = []; for (var s = 0; s <= HMAX; s += 0.5) ghostPts.push(xg(s).toFixed(1)+","+yg(doNothingAt(s)).toFixed(1));
  gsvg.appendChild(el("polyline", { points:ghostPts.join(" "), fill:"none", stroke:"#F0734A", "stroke-width":1.4, "stroke-dasharray":"4 4", opacity:0.45 }));
  var liveDanger = el("polygon", { points:"", fill:"#F0734A", opacity:0.16 }); gsvg.appendChild(liveDanger);
  var liveLine = el("polyline", { points:"", fill:"none", stroke:"#5EEAD4", "stroke-width":3, "stroke-linecap":"round", "stroke-linejoin":"round" }); gsvg.appendChild(liveLine);
  var nowDot = el("circle", { cx:GX0, cy:yg(7), r:4, fill:"#5EEAD4" }); gsvg.appendChild(nowDot);
  var nowLab = el("text", { x:GX0, y:yg(7)-9, fill:"#E8F2F5", "font-size":12, "font-weight":"600", "text-anchor":"middle", "font-family":"sans-serif" }); gsvg.appendChild(nowLab);
  [[0,"18:00"],[6,"00:00"],[12,"06:00"],[18,"12:00"],[24,"18:00"]].forEach(function(p){ var n = el("text",{x:xg(p[0]),y:GH-2,fill:"#7C97A6","font-size":10,"text-anchor":"middle","font-family":"sans-serif"}); n.textContent=p[1]; gsvg.appendChild(n); });
  gstage.appendChild(gsvg);

  /* ---------------- controls + external hooks ---------------- */
  var engageBtn = document.getElementById("live-engage");
  var liveStatus = document.getElementById("live-status");
  var statusPill = document.getElementById("status-pill");
  var clockEl = document.getElementById("clock");
  var kpiDo = document.getElementById("kpi-do");
  var recText = document.getElementById("rec-text");
  var aerCount = document.getElementById("aer-count");
  var aerMode = document.getElementById("aer-mode");
  var wheels = document.querySelectorAll("#wheels .wheel");

  function setEngaged(on){
    engaged = on; engageT = t;
    if (engageBtn){ engageBtn.classList.toggle("on", on);
      engageBtn.innerHTML = on ? '<i class="ti ti-bolt"></i> Autonomous control: on' : '<i class="ti ti-bolt"></i> Apply autonomous control'; }
    if (liveStatus) liveStatus.textContent = on ? "The drone is acting. Aerators on, oxygen recovering." : "Tap to hand the night over to the autonomous twin.";
    aerators.forEach(function(a, i){ if (on) setTimeout(function(){ a.on = true; }, i * 220); else a.on = false; });
  }
  if (engageBtn) engageBtn.addEventListener("click", function(){ setEngaged(!engaged); });

  var btnPlay = document.getElementById("pond-play");
  if (btnPlay) btnPlay.addEventListener("click", function(){ playing = !playing;
    btnPlay.innerHTML = playing ? '<i class="ti ti-player-pause"></i> Pause' : '<i class="ti ti-player-play"></i> Play';
    if (playing){ last = 0; requestAnimationFrame(loop); } });
  window.__pondAutopilot = function(v){ setEngaged(v !== false); };

  function nearestOnAer(x, y){ var best = null, bd = 1e9; aerators.forEach(function(a){ if (!a.on) return; var d=(a.x-x)*(a.x-x)+(a.y-y)*(a.y-y); if (d<bd){ bd=d; best=a; } }); return best; }

  /* ---------------- render ---------------- */
  function render(dt, ts){
    var d = curDO(t), st = statusOf(d), wk = clamp((d-2)/6, 0, 1);

    // pond water + pods
    water.setAttribute("fill", mix("#15323a", "#1d7080", wk));
    pods.forEach(function(p){ var pd = clamp(d + p.off + Math.sin(t*0.6 + p.x)*0.1, 0, 9), col = statusOf(pd)[1];
      p.ring.setAttribute("stroke", col); p.dot.setAttribute("fill", col); p.lab.textContent = pd.toFixed(1); });

    // aerator ripples (only when on)
    aerators.forEach(function(a){ a.ph = (a.ph + dt*0.6) % 1;
      a.halo.setAttribute("opacity", a.on ? 0.5 : 0);
      a.rings.forEach(function(rc, i){ if (!a.on){ rc.setAttribute("opacity", 0); return; } var pp=(a.ph+i/3)%1; rc.setAttribute("r",(6+pp*24).toFixed(1)); rc.setAttribute("opacity",(0.5*(1-pp)).toFixed(2)); }); });

    // drone scan + custody
    if (!seeded){ seeded = true; [[1,0,3.5],[2,0,6.5],[3,1,8.4],[0,2,5.0]].forEach(function(sd){ var cl=cells[sd[1]*COLS+sd[0]]; cl.captured=true; cl.at=(ts/1000)-sd[2]; }); }
    if (playing){ if (dstate === "move"){ var w = wps[widx], dx=w.x-dpos.x, dy=w.y-dpos.y, dd=Math.hypot(dx,dy), sp=64*dt;
        if (dd < sp+0.5){ dpos.x=w.x; dpos.y=w.y; dstate="dwell"; dwellEnd=ts/1000+0.5; var cell=cells[w.r*COLS+w.c]; cell.captured=true; cell.at=ts/1000; }
        else { dpos.x+=dx/dd*sp; dpos.y+=dy/dd*sp; } }
      else if (ts/1000 >= dwellEnd){ widx=(widx+1)%wps.length; dstate="move"; } }
    drone.setAttribute("transform","translate("+dpos.x.toFixed(1)+","+dpos.y.toFixed(1)+")");
    droneCore.setAttribute("fill", engaged ? "#5EEAD4" : "#F0734A");
    footprint.setAttribute("x",(dpos.x-(CW-6)/2).toFixed(1)); footprint.setAttribute("y",(dpos.y-(CH-6)/2).toFixed(1));
    footprint.setAttribute("opacity", dstate==="dwell"?0.2:0.1);
    var nowT = ts/1000, held = 0;
    cells.forEach(function(cell){ if (!cell.captured) return; var age=nowT-cell.at, fr=clamp(age/9,0,1);
      if (fr<1){ held++; cell.rect.setAttribute("opacity",(0.13*(1-fr)+0.05).toFixed(3)); cell.ring.setAttribute("opacity",1);
        cell.ring.setAttribute("stroke", age<5.4?"#5EEAD4":"#FFC14D"); cell.ring.setAttribute("stroke-dasharray",cell.circ.toFixed(1)); cell.ring.setAttribute("stroke-dashoffset",(cell.circ*fr).toFixed(1)); }
      else { cell.rect.setAttribute("opacity",0.045); cell.ring.setAttribute("opacity",0.22); cell.ring.setAttribute("stroke-dashoffset",0); } });
    pHud.textContent = engaged ? "Drone ▸ aerating" : "Drone ▸ " + clabel(wps[widx].c, wps[widx].r);
    pHud.setAttribute("fill", engaged ? "#5EEAD4" : "#A6BBC8");
    pHud2.textContent = engaged ? "autonomous · custody " + held + " zones" : "monitoring · custody " + held + " zones";

    // fish react to DO
    fish.forEach(function(fi){
      var col = d >= 5 ? "#bfe9dd" : d >= 3 ? "#f3c79a" : "#ee9a82";
      var speed = (d >= 5 ? 1.0 : d >= 3 ? 0.6 : 0.32);
      var aer = nearestOnAer(fi.x, fi.y), pull = (d < 5 ? 0.05 : 0.02);
      if (aer){ var ax=aer.x-fi.x, ay=aer.y-fi.y, ad=Math.hypot(ax,ay)+0.01; fi.vx+=(ax/ad)*pull; fi.vy+=(ay/ad)*pull; }
      fi.vx += (Math.random()-0.5)*0.10*speed; fi.vy += (Math.random()-0.5)*0.10*speed;
      var sp = Math.hypot(fi.vx, fi.vy), mx = 1.5*speed; if (sp > mx){ fi.vx=fi.vx/sp*mx; fi.vy=fi.vy/sp*mx; }
      fi.x += fi.vx*(1+dt*30); fi.y += fi.vy*(1+dt*30);
      if (fi.x<PX0+8){ fi.x=PX0+8; fi.vx=Math.abs(fi.vx);} else if (fi.x>PX1-8){ fi.x=PX1-8; fi.vx=-Math.abs(fi.vx);}
      if (fi.y<PY0+8){ fi.y=PY0+8; fi.vy=Math.abs(fi.vy);} else if (fi.y>PY1-8){ fi.y=PY1-8; fi.vy=-Math.abs(fi.vy);}
      var ang = Math.atan2(fi.vy, fi.vx)*180/Math.PI;
      fi.el.setAttribute("transform","translate("+fi.x.toFixed(1)+","+fi.y.toFixed(1)+") rotate("+ang.toFixed(0)+")");
      fi.body.setAttribute("fill", col);
    });

    // graph: live line up to t
    var pts = [], dz = [], below = false, dzStart = null;
    for (var s = 0; s <= t + 1e-6; s += 0.5){ var dv = curDO(s); pts.push(xg(s).toFixed(1)+","+yg(dv).toFixed(1)); }
    liveLine.setAttribute("points", pts.join(" "));
    liveLine.setAttribute("stroke", d < 5 ? "#F0734A" : "#5EEAD4");
    // danger fill under live line where below 5
    var dpoly = []; var hasBelow = false;
    for (var s2 = 0; s2 <= t + 1e-6; s2 += 0.5){ var dv2 = curDO(s2); if (dv2 < 5){ if (!hasBelow){ dpoly.push(xg(s2).toFixed(1)+","+yg(5).toFixed(1)); hasBelow = true; } dpoly.push(xg(s2).toFixed(1)+","+yg(dv2).toFixed(1)); } else if (hasBelow){ dpoly.push(xg(s2).toFixed(1)+","+yg(5).toFixed(1)); hasBelow=false; } }
    if (hasBelow) dpoly.push(xg(t).toFixed(1)+","+yg(5).toFixed(1));
    liveDanger.setAttribute("points", dpoly.length > 2 ? dpoly.join(" ") : "");
    nowDot.setAttribute("cx", xg(t).toFixed(1)); nowDot.setAttribute("cy", yg(d).toFixed(1)); nowDot.setAttribute("fill", d < 5 ? "#F0734A" : "#5EEAD4");
    nowLab.setAttribute("x", clamp(xg(t), GX0+14, GX1-14).toFixed(1)); nowLab.setAttribute("y", clamp(yg(d)-9, 12, GY1-4).toFixed(1)); nowLab.textContent = d.toFixed(1);

    // status pill + clock + KPI + aeration + rec
    if (statusPill){ var sp2 = engaged ? ["Autonomous · holding","#5EEAD4","#0c2c2a"] : (d < 5 ? ["Heading for crash","#F0734A","#3a1f15"] : ["Watching","#A6BBC8","#0E2336"]);
      statusPill.textContent = sp2[0]; statusPill.style.color = sp2[1]; statusPill.style.background = sp2[2]; }
    if (clockEl){ var ch = (T.clockStart + t) % 24, hh = Math.floor(ch), mm = Math.floor((ch-hh)*60); clockEl.textContent = (hh<10?"0":"")+hh+":"+(mm<10?"0":"")+mm; }
    if (kpiDo){ kpiDo.classList.toggle("warn", d < 5); var v = kpiDo.querySelector(".val"); if (v) v.innerHTML = d.toFixed(1) + ' <span class="u">mg/L</span>';
      var sd = kpiDo.querySelector(".statusdot"); if (sd) sd.style.background = st[1]; if (v) v.style.color = d < 5 ? st[1] : "#E8F2F5";
      var ft = kpiDo.querySelector(".foot"); if (ft){ ft.textContent = engaged ? "▲ holding" : (d < 5 ? "▼ falling" : "stable"); ft.style.color = engaged ? "#5EEAD4" : (d < 5 ? "#F0734A" : "#7C97A6"); } }
    if (wheels.length){ var n = engaged ? 4 : 1; wheels.forEach(function(w, i){ w.classList.toggle("on", i < n); }); }
    if (aerCount) aerCount.textContent = engaged ? "4 / 4 running · 8.0 kW" : "1 / 4 running · 2.0 kW";
    if (aerMode) aerMode.textContent = engaged ? "Autonomous" : "Manual";
    if (recText) recText.innerHTML = engaged
      ? 'Autonomous control engaged. Aeration at 100%, the twin is holding DO <span class="good">above the stress line</span> through dawn.'
      : 'Pre-dawn DO crash predicted around 06:00 (' + T.trough.do.toFixed(1) + ' mg/L). Hand control to the twin to prevent it.';
  }

  function loop(ts){
    if (!last) last = ts; var dt = Math.min(0.05, (ts-last)/1000); last = ts;
    if (playing){ t += dt * 1.1; if (t >= HMAX){ t = 0; if (engaged) engageT = 0; } }
    render(dt, ts);
    if (playing) requestAnimationFrame(loop); else last = 0;
  }
  if ("IntersectionObserver" in window){ var io = new IntersectionObserver(function(en){ en.forEach(function(e){ if (e.isIntersecting){ last=0; requestAnimationFrame(loop); io.disconnect(); } }); }, { threshold:0.1 }); io.observe(stage); }
  else requestAnimationFrame(loop);
  render(0, 0);

  // scroll-reveal (ported here since this is the only script now)
  (function reveals(){
    var els = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)){ els.forEach(function(e){ e.classList.add("in"); }); return; }
    var ro = new IntersectionObserver(function(en){ en.forEach(function(e){ if (e.isIntersecting){ e.target.classList.add("in"); ro.unobserve(e.target); } }); }, { threshold:0.12 });
    els.forEach(function(e){ ro.observe(e); });
  })();
})();
