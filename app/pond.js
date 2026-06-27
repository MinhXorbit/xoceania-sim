(function () {
  "use strict";
  var SVGNS = "http://www.w3.org/2000/svg";
  var stage = document.getElementById("pond-stage");
  if (!stage) return;

  var VW = 400, VH = 280, WATER_Y = 96, BED_Y = 262;
  function el(n, a){ var e = document.createElementNS(SVGNS, n); for (var k in a) e.setAttribute(k, a[k]); return e; }
  function lerp(a, b, t){ return a + (b - a) * t; }
  function clamp(v, lo, hi){ return v < lo ? lo : v > hi ? hi : v; }
  function hex(h){ h = h.replace("#",""); return [parseInt(h.substr(0,2),16),parseInt(h.substr(2,2),16),parseInt(h.substr(4,2),16)]; }
  function mix(c1, c2, t){ var a = hex(c1), b = hex(c2);
    return "rgb(" + Math.round(lerp(a[0],b[0],t)) + "," + Math.round(lerp(a[1],b[1],t)) + "," + Math.round(lerp(a[2],b[2],t)) + ")"; }

  // 24 h DO trajectories. t=0 is 18:00 (dusk); the crash lands pre-dawn near t=12 (06:00).
  var NOACT = [[0,6.5],[2,5.6],[4,4.6],[6,3.6],[8,2.9],[10,2.4],[12,2.3],[13,3.4],[14,5.6],[16,7.4],[18,8.2],[20,7.6],[22,7.0],[24,6.5]];
  var ACTED = [[0,6.5],[2,6.0],[4,5.8],[6,5.7],[8,5.6],[10,5.6],[12,5.7],[13,6.2],[14,6.8],[16,7.6],[18,8.2],[20,7.6],[22,7.0],[24,6.5]];
  function doAt(traj, t){
    t = ((t % 24) + 24) % 24;
    for (var i = 1; i < traj.length; i++){
      if (t <= traj[i][0]){ var a = traj[i-1], b = traj[i], k = (t - a[0]) / (b[0] - a[0]); return lerp(a[1], b[1], k); }
    }
    return traj[traj.length-1][1];
  }

  var svg = el("svg", { viewBox: "0 0 " + VW + " " + VH, width: "100%", role: "img",
    "aria-label": "Animated pond cross-section. As dissolved oxygen falls overnight the water darkens and the shrimp rise to the surface to gasp. With aeration on, bubbles rise, oxygen recovers and the shrimp settle." });

  var sky = el("rect", { x:0, y:0, width:VW, height:WATER_Y, fill:"#0a1d30" });
  svg.appendChild(sky);
  var stars = []; for (var s = 0; s < 18; s++){ var st = el("circle", { cx: 12 + Math.random()*(VW-24), cy: 6 + Math.random()*(WATER_Y-26), r: Math.random()*0.9+0.4, fill:"#cfe3ee", opacity:0 }); stars.push(st); svg.appendChild(st); }
  var orb = el("circle", { cx:200, cy:40, r:14, fill:"#FFC14D" });
  svg.appendChild(orb);

  var water = el("rect", { x:0, y:WATER_Y, width:VW, height:VH-WATER_Y, fill:"#1d6b78" });
  svg.appendChild(water);
  var shimmer = el("rect", { x:0, y:WATER_Y, width:VW, height:3, fill:"#5EEAD4", opacity:0.5 });
  svg.appendChild(shimmer);
  // gentle plants on the bed
  ["#0f5a4a","#0c4f54","#0f5a4a"].forEach(function(c, i){
    var px = 60 + i*150;
    svg.appendChild(el("path", { d:"M"+px+","+BED_Y+" q -6,-26 2,-44 q 6,16 -2,44 z", fill:c, opacity:0.7 }));
    svg.appendChild(el("path", { d:"M"+(px+10)+","+BED_Y+" q 6,-22 -1,-38 q -7,14 1,38 z", fill:c, opacity:0.55 }));
  });
  var bed = el("rect", { x:0, y:BED_Y, width:VW, height:VH-BED_Y, fill:"#08222b" });
  svg.appendChild(bed);

  var bubbleLayer = el("g", {}); svg.appendChild(bubbleLayer);
  var shrimpLayer = el("g", {}); svg.appendChild(shrimpLayer);

  // Aerators (paddlewheels) at the surface
  function makeAerator(cx){
    var g = el("g", {});
    g.appendChild(el("line", { x1:cx-16, y1:WATER_Y-1, x2:cx+16, y2:WATER_Y-1, stroke:"#0E2336", "stroke-width":3 }));
    var hub = el("g", {});
    hub.appendChild(el("circle", { cx:cx, cy:WATER_Y-9, r:11, fill:"none", stroke:"#8fb0bf", "stroke-width":2 }));
    for (var k = 0; k < 6; k++){ var ang = k*Math.PI/3; hub.appendChild(el("line", { x1:cx, y1:WATER_Y-9, x2:cx+Math.cos(ang)*11, y2:(WATER_Y-9)+Math.sin(ang)*11, stroke:"#8fb0bf", "stroke-width":2 })); }
    hub.setAttribute("transform", "rotate(0 "+cx+" "+(WATER_Y-9)+")");
    g.appendChild(hub); g._hub = hub; g._cx = cx; g.appendChild(el("circle", { cx:cx, cy:WATER_Y-9, r:2, fill:"#cfe3ee" }));
    svg.appendChild(g); return g;
  }
  var aerL = makeAerator(78), aerR = makeAerator(322);

  // HUD
  var hudDO = el("text", { x:14, y:30, fill:"#E8F2F5", "font-size":26, "font-weight":"700", "font-family":"sans-serif" }); hudDO.textContent = "6.5";
  var hudUnit = el("text", { x:62, y:30, fill:"#A6BBC8", "font-size":12, "font-family":"sans-serif" }); hudUnit.textContent = "mg/L  DO";
  var hudStatus = el("text", { x:14, y:46, fill:"#5EEAD4", "font-size":12, "font-weight":"600", "font-family":"sans-serif" }); hudStatus.textContent = "Healthy";
  var hudClock = el("text", { x:VW-14, y:30, fill:"#A6BBC8", "font-size":13, "text-anchor":"end", "font-family":"sans-serif" }); hudClock.textContent = "18:00";
  [hudDO,hudUnit,hudStatus,hudClock].forEach(function(n){ svg.appendChild(n); });
  // DO gauge
  svg.appendChild(el("rect", { x:VW-12, y:60, width:6, height:VH-72, rx:3, fill:"#0a1d30" }));
  var gauge = el("rect", { x:VW-12, y:60, width:6, height:80, rx:3, fill:"#5EEAD4" }); svg.appendChild(gauge);
  var gauge5 = (function(){ var y = 60 + (VH-72) * (1 - 5/9); return el("line", { x1:VW-15, y1:y, x2:VW-3, y2:y, stroke:"#FFC14D", "stroke-width":1.5, "stroke-dasharray":"2 2" }); })();
  svg.appendChild(gauge5);

  stage.appendChild(svg);

  // Shrimp
  function shrimpEl(){
    var g = el("g", {});
    g.appendChild(el("path", { d:"M-11,0 Q -3,-7 7,-5 Q 13,-4 13,1 Q 13,5 7,5 Q 1,6 -4,2 Q -8,4 -11,0 Z", fill:"#EC9A82", stroke:"#b9624a", "stroke-width":0.6 }));
    g.appendChild(el("path", { d:"M-11,0 l -6,-4 l 1,4 l -1,4 z", fill:"#EC9A82", stroke:"#b9624a", "stroke-width":0.5 }));
    g.appendChild(el("path", { d:"M11,1 q 9,-2 14,-6", fill:"none", stroke:"#cf8f7d", "stroke-width":0.7 }));
    g.appendChild(el("path", { d:"M11,2 q 9,1 14,4", fill:"none", stroke:"#cf8f7d", "stroke-width":0.7 }));
    for (var l = 0; l < 4; l++){ g.appendChild(el("line", { x1:-4+l*3, y1:5, x2:-5+l*3, y2:9, stroke:"#b9624a", "stroke-width":0.6 })); }
    g.appendChild(el("circle", { cx:8, cy:-1.5, r:1.3, fill:"#3a1f17" }));
    return g;
  }
  var shrimp = [];
  for (var i = 0; i < 8; i++){
    var g = shrimpEl(); shrimpLayer.appendChild(g);
    shrimp.push({ el:g, x:40+Math.random()*320, y:150+Math.random()*90, ty:0, dir:Math.random()<0.5?1:-1,
      sp:0.18+Math.random()*0.22, ph:Math.random()*6.28, scale:0.8+Math.random()*0.45 });
  }

  // Bubbles
  var bubbles = []; var BMAX = 34;
  for (var b = 0; b < BMAX; b++){ var c = el("circle", { cx:0, cy:0, r:1.5, fill:"#bfeede", opacity:0 }); bubbleLayer.appendChild(c); bubbles.push({ el:c, active:false }); }
  function spawnBubble(x){
    for (var j = 0; j < bubbles.length; j++){ if (!bubbles[j].active){ var bb = bubbles[j];
      bb.active = true; bb.x = x + (Math.random()*8-4); bb.y = BED_Y - Math.random()*10; bb.r = 1 + Math.random()*1.8; bb.v = 0.4 + Math.random()*0.7; bb.wob = Math.random()*6.28; return; } }
  }

  // State + controls
  var t = 0, playing = true, autopilot = false, speed = 1.2, last = 0;
  var btnPlay = document.getElementById("pond-play");
  var btnAuto = document.getElementById("pond-auto");
  var scrub = document.getElementById("pond-scrub");

  function setAuto(on){ autopilot = on;
    if (btnAuto){ btnAuto.classList.toggle("on", on); btnAuto.innerHTML = on ? '<i class="ti ti-bolt"></i> xOceania: on' : '<i class="ti ti-bolt-off"></i> xOceania: off'; }
  }
  window.__pondAutopilot = setAuto;
  if (btnAuto) btnAuto.addEventListener("click", function(){ setAuto(!autopilot); });
  if (btnPlay) btnPlay.addEventListener("click", function(){ playing = !playing;
    btnPlay.innerHTML = playing ? '<i class="ti ti-player-pause"></i> Pause' : '<i class="ti ti-player-play"></i> Play';
    if (playing) requestAnimationFrame(loop); });
  if (scrub) scrub.addEventListener("input", function(){ t = parseFloat(scrub.value); playing = false;
    if (btnPlay) btnPlay.innerHTML = '<i class="ti ti-player-play"></i> Play';
    for (var i = 0; i < 45; i++) render(0.05); });

  function statusFor(d){ return d >= 5 ? ["Healthy","#5EEAD4"] : d >= 3 ? ["Stressed","#FFC14D"] : ["Critical","#F0734A"]; }

  var wheelAng = 0;
  function render(dt){
    var traj = autopilot ? ACTED : NOACT;
    var d = doAt(traj, t);
    var clockHour = (18 + t) % 24;
    var daylight = clockHour >= 6 && clockHour < 18;
    // sky + orb
    var dayK = daylight ? 1 : 0;
    sky.setAttribute("fill", daylight ? mix("#0a1d30", "#173a52", clamp((clockHour-6)/6,0,1)) : "#061425");
    stars.forEach(function(stn){ stn.setAttribute("opacity", daylight ? 0 : 0.7); });
    var prog, ox, oy;
    if (daylight){ prog = (clockHour - 6) / 12; orb.setAttribute("fill", "#FFD37A"); }
    else { prog = ((clockHour + 6) % 24) / 12; orb.setAttribute("fill", "#cfe0ee"); }
    ox = 40 + prog * (VW - 80); oy = 78 - Math.sin(prog * Math.PI) * 60;
    orb.setAttribute("cx", ox.toFixed(1)); orb.setAttribute("cy", oy.toFixed(1));
    orb.setAttribute("r", daylight ? 14 : 9);

    // water color by DO
    var wk = clamp((d - 2) / 6, 0, 1);
    water.setAttribute("fill", mix("#15323a", "#1d7080", wk));
    shimmer.setAttribute("opacity", 0.25 + wk * 0.5);

    // gauge
    var gh = (VH - 72) * clamp(d/9, 0, 1);
    gauge.setAttribute("y", (60 + (VH-72) - gh).toFixed(1)); gauge.setAttribute("height", gh.toFixed(1));
    gauge.setAttribute("fill", d >= 5 ? "#5EEAD4" : d >= 3 ? "#FFC14D" : "#F0734A");

    // HUD
    hudDO.textContent = d.toFixed(1);
    var stt = statusFor(d); hudStatus.textContent = stt[0]; hudStatus.setAttribute("fill", stt[1]);
    hudDO.setAttribute("fill", d < 3 ? "#F0734A" : "#E8F2F5");
    var hh = Math.floor(clockHour), mm = Math.floor((clockHour - hh) * 60);
    hudClock.textContent = (hh<10?"0":"")+hh+":"+(mm<10?"0":"")+mm;

    // aerators spin + jets when autopilot on
    if (autopilot){ wheelAng = (wheelAng + dt * 220) % 360;
      aerL._hub.setAttribute("transform", "rotate("+wheelAng+" "+aerL._cx+" "+(WATER_Y-9)+")");
      aerR._hub.setAttribute("transform", "rotate("+(-wheelAng)+" "+aerR._cx+" "+(WATER_Y-9)+")");
      if (Math.random() < 0.5){ spawnBubble(aerL._cx); spawnBubble(aerR._cx); }
    }
    // ambient bubbles scale with DO (photosynthesis / aeration)
    if (Math.random() < wk * 0.35 + (autopilot?0.25:0)) spawnBubble(40 + Math.random()*(VW-80));

    // bubbles rise
    bubbles.forEach(function(bb){ if (!bb.active) return;
      bb.y -= bb.v * (1 + dt*30); bb.wob += dt*4; var bx = bb.x + Math.sin(bb.wob)*1.5;
      if (bb.y <= WATER_Y + 1){ bb.active = false; bb.el.setAttribute("opacity", 0); return; }
      bb.el.setAttribute("cx", bx.toFixed(1)); bb.el.setAttribute("cy", bb.y.toFixed(1)); bb.el.setAttribute("r", bb.r);
      bb.el.setAttribute("opacity", 0.5);
    });

    // shrimp behaviour by DO
    var surface = WATER_Y + 12, mid = (WATER_Y + BED_Y) / 2;
    shrimp.forEach(function(sh, idx){
      var target, col, op = 1, tilt = 0;
      if (d >= 5){ target = mid - 30 + (idx % 5) * 22 + Math.sin(t*0.5 + sh.ph)*8; col = "#EC9A82"; }
      else if (d >= 3){ target = lerp(surface + 26, mid - 20, (d-3)/2) + Math.sin(t + sh.ph)*6; col = "#E0A08C"; }
      else { target = surface + (idx % 3) * 5 + Math.sin(t*1.4 + sh.ph)*2; col = "#D79C90"; op = 0.9; tilt = -22; }
      sh.ty = target;
      // horizontal swim (slower + frantic when stressed)
      var hsp = sh.sp * (d < 3 ? 1.7 : d < 5 ? 1.2 : 1) * (1 + dt*40);
      sh.x += sh.dir * hsp;
      if (sh.x < 26){ sh.x = 26; sh.dir = 1; } else if (sh.x > VW-26){ sh.x = VW-26; sh.dir = -1; }
      sh.y += (sh.ty - sh.y) * clamp(dt*2.2, 0, 1);
      var bob = Math.sin(t*2 + sh.ph) * (d < 3 ? 0.6 : 1.6);
      var sx = sh.dir < 0 ? -sh.scale : sh.scale;
      var rot = (d < 3 ? tilt : 0) + Math.sin(t + sh.ph) * 4;
      sh.el.setAttribute("transform", "translate("+sh.x.toFixed(1)+","+(sh.y+bob).toFixed(1)+") scale("+sx.toFixed(2)+","+sh.scale.toFixed(2)+") rotate("+rot.toFixed(1)+")");
      sh.el.querySelectorAll("path")[0].setAttribute("fill", col);
      sh.el.querySelectorAll("path")[1].setAttribute("fill", col);
      sh.el.setAttribute("opacity", op);
    });

    if (scrub && playing) scrub.value = t;
  }

  function loop(ts){
    if (!last) last = ts; var dt = Math.min(0.05, (ts - last) / 1000); last = ts;
    if (playing){ t = (t + dt * speed) % 24; }
    render(dt);
    if (playing) requestAnimationFrame(loop); else last = 0;
  }
  // start when scrolled into view (saves battery)
  if ("IntersectionObserver" in window){
    var io = new IntersectionObserver(function(en){ en.forEach(function(e){ if (e.isIntersecting){ last = 0; requestAnimationFrame(loop); io.disconnect(); } }); }, { threshold: 0.2 });
    io.observe(stage);
  } else { requestAnimationFrame(loop); }
  render(0);
})();
