/* АгроГео — интерактивная веб-карта тематических слоёв на MapLibre GL JS (КП Этап 2, работа 4). */
(function () {
  "use strict";
  const A = window.AGROGEO;
  if (!A) { document.getElementById("map").innerHTML = "<p style='padding:20px'>Нет данных: запустите src/run_all.py</p>"; return; }

  const layersByKey = {};
  A.layers.forEach(l => layersByKey[l.key] = l);
  const order = A.layers.map(l => l.key);
  const units = {}; A.layers.forEach(l => units[l.key] = l.unit);
  const labels = {}; A.layers.forEach(l => labels[l.key] = l.name);

  // bounds: layer.bounds = [[south, west], [north, east]]
  const bnd = A.layers[0].bounds;
  const S = bnd[0][0], W = bnd[0][1], N = bnd[1][0], E = bnd[1][1];

  const map = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      sources: {
        osm: {
          type: "raster",
          tiles: ["https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
                  "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
                  "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png"],
          tileSize: 256, attribution: "© OpenStreetMap"
        }
      },
      layers: [{ id: "osm", type: "raster", source: "osm" }]
    },
    bounds: [[W, S], [E, N]],
    fitBoundsOptions: { padding: 60 }
  });
  map.addControl(new maplibregl.NavigationControl(), "top-left");
  window._map = map;
  map.on("error", e => console.error("MAPERR:", (e && e.error && e.error.message) || JSON.stringify(e)));

  let active = null;
  function setActive(k) {
    if (!map.getLayer("img-" + k)) return;
    if (active && map.getLayer("img-" + active)) map.setLayoutProperty("img-" + active, "visibility", "none");
    active = k;
    map.setLayoutProperty("img-" + k, "visibility", "visible");
    document.querySelectorAll(".metric-btn").forEach(b => b.classList.toggle("active", b.dataset.k === k));
    renderLegend(layersByKey[k]);
  }

  map.on("load", () => {
    // растровые тематические слои (PNG image-источники)
    order.forEach(k => {
      const l = layersByKey[k];
      map.addSource("img-" + k, { type: "image", url: l.png, coordinates: [[W, N], [E, N], [E, S], [W, S]] });
      map.addLayer({ id: "img-" + k, type: "raster", source: "img-" + k,
        paint: { "raster-opacity": 0.78 }, layout: { visibility: "none" } });
    });
    // контур парка (пунктир)
    if (A.park) {
      map.addSource("park", { type: "geojson", data: A.park });
      map.addLayer({ id: "park", type: "line", source: "park",
        paint: { "line-color": "#2e7d32", "line-width": 1.5, "line-dasharray": [3, 3] } });
    }
    // дороги OSM
    if (A.roads) {
      map.addSource("roads", { type: "geojson", data: A.roads });
      map.addLayer({ id: "roads", type: "line", source: "roads",
        paint: { "line-color": "#8a5a2b", "line-width": 2, "line-opacity": 0.7 } });
    }
    // контур участка
    map.addSource("field", { type: "geojson", data: A.field });
    map.addLayer({ id: "field", type: "line", source: "field", paint: { "line-color": "#ff3d00", "line-width": 2 } });
    // точки измерений
    map.addSource("points", { type: "geojson", data: A.points });
    map.addLayer({ id: "points", type: "circle", source: "points",
      paint: { "circle-radius": 4, "circle-color": "#ffffff", "circle-stroke-color": "#10202f", "circle-stroke-width": 1 } });

    map.on("click", "points", e => {
      const p = e.features[0].properties;
      const rows = order.map(k => `<tr><td>${labels[k]}</td><td><b>${p[k]}</b> ${units[k]}</td></tr>`).join("");
      new maplibregl.Popup({ closeButton: true })
        .setLngLat(e.lngLat)
        .setHTML(`<b>Точка №${p.id}</b><br><span style="color:#777;font-size:11px">${p.ts}</span><table>${rows}</table>`)
        .addTo(map);
    });
    map.on("mouseenter", "points", () => map.getCanvas().style.cursor = "pointer");
    map.on("mouseleave", "points", () => map.getCanvas().style.cursor = "");

    document.getElementById("togglePoints").onchange = e =>
      map.setLayoutProperty("points", "visibility", e.target.checked ? "visible" : "none");
    document.getElementById("toggleField").onchange = e =>
      map.setLayoutProperty("field", "visibility", e.target.checked ? "visible" : "none");

    setActive("n");
    refresh();
    setTimeout(refresh, 250);
    requestAnimationFrame(refresh);
  });
  function refresh() { map.resize(); map.triggerRepaint(); }   // фикс пустого холста при flex-разметке
  window.addEventListener("resize", refresh);
  try { new ResizeObserver(refresh).observe(document.getElementById("map")); } catch (e) {}

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

  document.getElementById("corr").innerHTML =
    A.correlations.top_pairs.map(p => `<li>${p.a.toUpperCase()}–${p.b.toUpperCase()}: r = <b>${p.r}</b></li>`).join("");

  document.getElementById("note").innerHTML =
    "Движок карты: <b>MapLibre GL JS</b> (WebGL), подложка OpenStreetMap. " +
    "Источник данных: <b>SoilGrids (ISRIC)</b> — реальные значения, 250&nbsp;м, глубина 0–5&nbsp;см; " +
    "показаны только точки с реальными данными (застройка/вода отфильтрованы, придорожные убраны по OSM). " +
    "Интерполяция — ординарный кригинг. Хранение — PostGIS/TimescaleDB (прод.) / SQLite (демо).<br><br>" +
    "<b>EC, температура, доступные P и K</b> отсутствуют в открытых данных — измеряются прибором комплекса в поле.";
})();
