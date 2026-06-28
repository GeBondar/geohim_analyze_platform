/* АгроГео — интерактивная веб-карта 7 тематических слоёв (КП Этап 2, работа 4). */
(function () {
  "use strict";
  const A = window.AGROGEO;
  if (!A) { document.getElementById("map").innerHTML = "<p style='padding:20px'>Нет данных: запустите src/run_all.py</p>"; return; }

  const layersByKey = {};
  A.layers.forEach(l => layersByKey[l.key] = l);
  const order = A.layers.map(l => l.key);

  // --- карта ---
  const map = L.map("map", { zoomControl: true }).setView(A.meta.center, 16);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map);

  // контур парка, дороги (OSM) и участок
  L.geoJSON(A.park, { style: { color: "#2e7d32", weight: 1.5, fill: false, dashArray: "5,5" } }).addTo(map);
  if (A.roads) L.geoJSON(A.roads, { style: { color: "#8a5a2b", weight: 2, opacity: 0.7 } }).addTo(map);
  const fieldLayer = L.geoJSON(A.field, { style: { color: "#ff3d00", weight: 2, fill: false } }).addTo(map);
  map.fitBounds(fieldLayer.getBounds().pad(0.6));

  // --- оверлеи слоёв ---
  const overlays = {};
  order.forEach(k => {
    overlays[k] = L.imageOverlay(layersByKey[k].png, layersByKey[k].bounds, { opacity: 0.75, interactive: false });
  });
  let active = null;
  function setActive(k) {
    if (active && overlays[active]) map.removeLayer(overlays[active]);
    active = k;
    overlays[k].addTo(map);
    if (pointsLayer && map.hasLayer(pointsLayer)) pointsLayer.bringToFront();
    document.querySelectorAll(".metric-btn").forEach(b => b.classList.toggle("active", b.dataset.k === k));
    renderLegend(layersByKey[k]);
  }

  // --- кнопки метрик ---
  const grid = document.getElementById("metricBtns");
  order.forEach(k => {
    const l = layersByKey[k];
    const b = document.createElement("button");
    b.className = "metric-btn" + (l.device ? " device" : "");
    b.dataset.k = k;
    b.innerHTML = `<div>${l.name}</div>`;
    b.onclick = () => setActive(k);
    grid.appendChild(b);
  });

  function renderLegend(l) {
    document.getElementById("legend").innerHTML =
      `<div class="name">${l.name}, ${l.unit}</div>
       <img src="${l.colorbar}" alt="шкала">
       <div class="scale"><span>${l.min}</span><span>${((l.min+l.max)/2).toFixed(1)}</span><span>${l.max}</span></div>
       <div class="src ${l.device ? 'dev' : 'real'}">${l.device ? '◆ ' : '● '}${l.source}</div>
       <div class="acc">Кросс-валидация (кригинг): отн. ошибка ±${l.rel_pct}%</div>`;
  }

  // --- точки измерений ---
  const units = {}; A.layers.forEach(l => units[l.key] = l.unit);
  const labels = {}; A.layers.forEach(l => labels[l.key] = l.name);
  const pointsLayer = L.geoJSON(A.points, {
    pointToLayer: (f, latlng) => L.circleMarker(latlng, {
      radius: 4, color: "#0d1b2a", weight: 1, fillColor: "#ffffff", fillOpacity: 0.9
    }),
    onEachFeature: (f, layer) => {
      const p = f.properties;
      let rows = order.map(k => `<tr><td>${labels[k]}</td><td><b>${p[k]}</b> ${units[k]}</td></tr>`).join("");
      layer.bindPopup(`<b>Точка №${p.id}</b><br><span style="color:#777;font-size:11px">${p.ts}</span><table>${rows}</table>`);
    }
  }).addTo(map);

  document.getElementById("togglePoints").onchange = e => { e.target.checked ? pointsLayer.addTo(map) : map.removeLayer(pointsLayer); };
  document.getElementById("toggleField").onchange = e => { e.target.checked ? fieldLayer.addTo(map) : map.removeLayer(fieldLayer); };

  // --- сводка ---
  const m = A.meta;
  document.getElementById("stats").innerHTML =
    `<span class="pill">Участок ${m.field_area_ha} га</span>
     <span class="pill">${m.n_clean}/${m.n_raw} точек</span>
     <span class="pill">валидных ${m.valid_frac_pct}%</span><br>
     Объект: <b>${m.park}</b><br>
     Договор: <b>${m.contract}</b><br>
     Старт прохода: <b>${m.base_time.replace("T"," ")}</b>, цикл ${m.cycle_s} с<br>
     PCA (2 компоненты): <b>${(A.correlations.pca_first2*100).toFixed(1)}%</b> дисперсии<br>
     Moran's I (азот): <b>${A.correlations.morans_I_n}</b>`;

  // --- корреляции (топ пар) ---
  document.getElementById("corr").innerHTML =
    A.correlations.top_pairs.map(p => `<li>${p.a.toUpperCase()}–${p.b.toUpperCase()}: r = <b>${p.r}</b></li>`).join("");

  document.getElementById("note").innerHTML =
    "Источник: <b>SoilGrids (ISRIC)</b> — реальные данные, 250&nbsp;м, глубина 0–5&nbsp;см. " +
    "Показаны только точки с реальными значениями (застройка/вода отфильтрованы). " +
    "Интерполяция — ординарный кригинг. Хранение — PostGIS/TimescaleDB (прод.) / SQLite (демо).<br><br>" +
    "<b>EC, температура, доступные P и K</b> отсутствуют в открытых данных — измеряются прибором комплекса в поле.";

  // старт
  setActive("n");
})();
