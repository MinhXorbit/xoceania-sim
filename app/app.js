(function () {
  "use strict";
  var SVGNS = "http://www.w3.org/2000/svg";
  var C = { teal: "#2BC4D4", bright: "#5EEAD4", orange: "#F0734A", amber: "#FFC14D", muted: "#A6BBC8", dim: "#7C97A6", grid: "#102536", axis: "#14304a" };

  var MEASURED = [[-10,7.0],[-8,6.6],[-6,6.0],[-4,5.6],[-2,5.3],[0,5.1]];
  var NOACTION = [[0,5.1],[2,4.3],[4,3.2],[6,2.3],[8,3.6],[10,6.4]];
  var ACTED    = [[0,5.1],[2,5.8],[4,6.0],[6,5.9],[8,6.1],[10,6.6]];
  var W = 360, H = 210, X0 = 34, X1 = 346, Y0 = 18, Y1 = 176, NOW_X;

  function xpx(h){ return X0 + (h + 10) / 20 * (X1 - X0); }
  function ypx(d){ return Y1 - d / 9 * (Y1 - Y0); }
  NOW_X = xpx(0);
  function pts(arr){ return arr.map(function(p){ return xpx(p[0]).toFixed(1) + "," + ypx(p[1]).toFixed(1); }).join(" "); }
  function el(name, attrs){ var e = document.createElementNS(SVGNS, name); for (var k in attrs) e.setAttribute(k, attrs[k]); return e; }

  function textEl(x, y, str, fill, anchor, size){
    var t = el("text", { x: x, y: y, fill: fill, "font-size": size || 11, "text-anchor": anchor || "start", "font-family": "sans-serif" });
    t.textContent = str; return t;
  }

  function buildForecast(containerId, mode, animate){
    var box = document.getElementById(containerId);
    if (!box) return;
    box.innerHTML = "";
    var svg = el("svg", { viewBox: "0 0 " + W + " " + H, class: "forecast", role: "img" });

    svg.appendChild(el("line", { x1: X0, y1: Y1, x2: X1, y2: Y1, stroke: C.axis, "stroke-width": 1 }));
    svg.appendChild(el("line", { x1: X0, y1: ypx(7), x2: X1, y2: ypx(7), stroke: C.grid, "stroke-width": 1 }));
    svg.appendChild(el("line", { x1: X0, y1: ypx(3), x2: X1, y2: ypx(3), stroke: C.grid, "stroke-width": 1 }));
    svg.appendChild(el("line", { x1: X0, y1: ypx(5), x2: X1, y2: ypx(5), stroke: C.amber, "stroke-width": 1.3, "stroke-dasharray": "5 4" }));
    svg.appendChild(textEl(X0 + 2, ypx(5) - 4, "stress 5 mg/L", C.amber, "start", 10.5));
    svg.appendChild(el("line", { x1: NOW_X, y1: Y0 + 4, x2: NOW_X, y2: Y1, stroke: C.dim, "stroke-width": 1, "stroke-dasharray": "3 3" }));
    svg.appendChild(textEl(NOW_X, Y0 - 2, "now", C.muted, "middle", 10.5));
    [["16:00",-8],["20:00",-4],["00:00",0],["04:00",4],["08:00",8]].forEach(function(t){
      svg.appendChild(textEl(xpx(t[1]), H - 2, t[0], C.dim, "middle", 10));
    });

    var measured = el("polyline", { points: pts(MEASURED), fill: "none", stroke: C.teal, "stroke-width": 3, "stroke-linecap": "round", "stroke-linejoin": "round" });
    svg.appendChild(measured);

    var g = el("g", {});
    var showCrash = (mode === "contrast" || mode === "risk");
    if (showCrash){
      var dz = [[xpx(0.25), ypx(5)]];
      NOACTION.slice(1, 5).forEach(function(p){ dz.push([xpx(p[0]), ypx(p[1])]); });
      dz.push([xpx(9), ypx(5)]);
      g.appendChild(el("polygon", { points: dz.map(function(p){ return p[0].toFixed(1)+","+p[1].toFixed(1); }).join(" "), fill: C.orange, opacity: 0.20 }));
      g.appendChild(el("polyline", { points: pts(NOACTION), fill: "none", stroke: C.orange, "stroke-width": 2.4, "stroke-dasharray": "6 4", "stroke-linecap": "round" }));
      g.appendChild(el("circle", { cx: xpx(6), cy: ypx(2.3), r: 4.5, fill: C.orange }));
      g.appendChild(textEl(xpx(6), ypx(2.3) + 16, "2.3 mg/L · 06:00", C.orange, "middle", 10.5));
    }
    if (mode === "contrast" || mode === "safe"){
      g.appendChild(el("polyline", { points: pts(ACTED), fill: "none", stroke: C.bright, "stroke-width": 2.6, "stroke-dasharray": "6 4", "stroke-linecap": "round" }));
    }
    svg.appendChild(g);
    box.appendChild(svg);

    if (animate){
      var len = measured.getTotalLength();
      measured.style.strokeDasharray = len; measured.style.strokeDashoffset = len;
      g.style.opacity = 0;
      measured.getBoundingClientRect();
      measured.style.transition = "stroke-dashoffset .8s ease";
      measured.style.strokeDashoffset = 0;
      g.style.transition = "opacity .7s ease .45s";
      requestAnimationFrame(function(){ g.style.opacity = 1; });
      setTimeout(function(){ g.style.opacity = 1; measured.style.strokeDashoffset = 0; }, 1500);
    }
  }

  function showToast(text, icon){
    var t = document.getElementById("toast");
    document.getElementById("toast-text").textContent = text;
    t.querySelector("i").className = "ti " + (icon || "ti-circle-check");
    t.classList.add("show");
    clearTimeout(showToast._t);
    showToast._t = setTimeout(function(){ t.classList.remove("show"); }, 4200);
  }

  function applyAeration(){
    var btn = document.getElementById("apply");
    btn.disabled = true; btn.style.opacity = .55; btn.innerHTML = '<i class="ti ti-check"></i> Aeration applied';
    var box = document.getElementById("demo-chart");
    box.style.transition = "opacity .25s"; box.style.opacity = 0;
    setTimeout(function(){ buildForecast("demo-chart", "safe", true); box.style.opacity = 1; }, 260);

    var tag = document.getElementById("forecast-tag");
    tag.className = "tag ok"; tag.innerHTML = '<i class="ti ti-shield-check"></i> Crash prevented';
    document.getElementById("lg-noaction").innerHTML = '<span class="swatch dash" style="border-color:var(--bright)"></span>Forecast';

    var doKpi = document.getElementById("kpi-do");
    doKpi.classList.remove("warn");
    doKpi.querySelector(".val").innerHTML = '5.1 <span class="u">mg/L</span>';
    doKpi.querySelector(".statusdot").style.background = "var(--bright)";
    var foot = document.getElementById("kpi-do-foot");
    foot.textContent = "▲ holding ≥ 5.6"; foot.style.color = "var(--bright)";

    var wheels = document.querySelectorAll("#wheels .wheel");
    wheels.forEach(function(w, i){ setTimeout(function(){ w.classList.add("on"); }, i * 120); });
    document.getElementById("aer-count").textContent = "4 / 4 running · 8.0 kW";
    document.getElementById("aer-rec").textContent = "holding the line";
    document.getElementById("aer-mode").textContent = "Auto";
    document.getElementById("rec-text").innerHTML = 'Aeration at 100%. The forecast now holds DO <span class="good">≥ 5.6 mg/L</span> through dawn. Crash averted.';
    showToast("Crash prevented. DO held at 5.6 mg/L overnight.", "ti-circle-check");
  }

  function tickClock(){
    var node = document.getElementById("clock"); if (!node) return;
    var base = 12 * 60; // 00:12 in minutes
    setInterval(function(){ base += 1; var h = Math.floor(base / 60) % 24, m = base % 60;
      node.textContent = (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m; }, 3000);
  }

  function reveals(){
    var els = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)){ els.forEach(function(e){ e.classList.add("in"); }); return; }
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(en){
        if (en.isIntersecting){ en.target.classList.add("in");
          if (en.target.querySelector && en.target.querySelector("#demo-chart")) buildForecast("demo-chart", "risk", true);
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.25 });
    els.forEach(function(e){ io.observe(e); });
  }

  document.addEventListener("DOMContentLoaded", function(){
    buildForecast("hero-chart", "contrast", true);
    buildForecast("demo-chart", "risk", false);
    reveals();
    tickClock();
    document.getElementById("cta-demo").addEventListener("click", function(){
      document.getElementById("demo").scrollIntoView({ behavior: "smooth" });
    });
    document.getElementById("apply").addEventListener("click", applyAeration);
    document.getElementById("why").addEventListener("click", function(){
      showToast("The twin rolled the pond forward 6 h and saw DO breaching 5 mg/L before dawn.", "ti-bulb");
    });
  });
})();
