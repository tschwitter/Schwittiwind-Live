// ================= GLOBALE ZUSTANDSVERWALTUNG =================
let mapLeft = null, mapRight = null;
let isSplitActive = false;
let isSyncingMaps = false;
let isLegendOpen = false;
let syncRafId = null;

const ALL_MODELS = ["kenda-ch1", "icon-ch1", "icon-ch2", "arome", "icon-d2", "icon-eu", "ecmwf", "aifs", "gfs"];
let isMobileModelExpanded = false;

const modelsState = {
    left: {
        currentModel: "icon-ch1", currentRunId: null, currentMemberIdx: 0,
        config: null, times: null, contourLayer1: null, contourLayer2: null,
        arrowCanvas: null, arrowCtx: null, canvasRenderer1: null, canvasRenderer2: null
    },
    right: {
        currentModel: "ecmwf", currentRunId: null, currentMemberIdx: 0,
        config: null, times: null, contourLayer1: null, contourLayer2: null,
        arrowCanvas: null, arrowCtx: null, canvasRenderer1: null, canvasRenderer2: null
    }
};

const availableRuns = { "kenda-ch1": [], "icon-ch1": [], "icon-ch2": [], "arome": [], "icon-d2": [], "icon-eu": [], "ecmwf": [], "aifs": [], "gfs": [] };
const selectedRuns = {
    left: { "kenda-ch1": null, "icon-ch1": null, "icon-ch2": null, "arome": null, "icon-d2": null, "icon-eu": null, "ecmwf": null, "aifs": null, "gfs": null },
    right: { "kenda-ch1": null, "icon-ch1": null, "icon-ch2": null, "arome": null, "icon-d2": null, "icon-eu": null, "ecmwf": null, "aifs": null, "gfs": null }
};

let verticalNavMode = 'member';
let baseMapOpacity = 0.80;
let baseMapStyle = 'relief';

let layer1Var = "wind";
let layer2Var = null;
let layer1Mode = 'fill';
let layer2Mode = 'fill';
let layer1Opacity = 0.60;
let layer2Opacity = 0.60;

let isWetterOpen = false;
let isHoehenOpen = false;
let isEnsembleOpen = (localStorage.getItem("icon_ensemble_open") === "true");

let currentStepIdx = 0;
let baseReliefLayerLeft, baseReliefLayerRight;
let riversLayerLeft, riversLayerRight;
let cantonalBoundaryLayerLeft, cantonalBoundaryLayerRight;
let cityLayerGroupLeft, cityLayerGroupRight;

const MAX_CACHE_ENTRIES = 70;
const cacheGrid = {};
const cacheContours = {};

function storeInBoundedCache(cache, key, value) {
    const keys = Object.keys(cache);
    if (keys.length >= MAX_CACHE_ENTRIES) {
        delete cache[keys[0]];
    }
    cache[key] = value;
}

let uniqueDays = [];
let dayTimesteps = {};
const weekdays = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

let mapUpdateTimer = null;
let mapSafetyTimer = null;
let resizeDebounceTimer = null;

const CITIES = [
    { name: "Zürich", lat: 47.3769, lon: 8.5417, minZoom: 7 }, { name: "Bern", lat: 46.9480, lon: 7.4474, minZoom: 7 },
    { name: "Basel", lat: 47.5596, lon: 7.5886, minZoom: 7 }, { name: "Genève", lat: 46.2044, lon: 6.1432, minZoom: 7 },
    { name: "Lausanne", lat: 46.5197, lon: 6.6323, minZoom: 7 }, { name: "Luzern", lat: 47.0502, lon: 8.3093, minZoom: 7 },
    { name: "St. Gallen", lat: 47.4245, lon: 9.3767, minZoom: 7 }, { name: "Lugano", lat: 46.0037, lon: 8.9511, minZoom: 7 },
    { name: "Chur", lat: 46.8508, lon: 9.5320, minZoom: 7 }, { name: "Sion", lat: 46.2331, lon: 7.3606, minZoom: 7 },
    { name: "Winterthur", lat: 47.4999, lon: 8.7241, minZoom: 9 }, { name: "Biel/Bienne", lat: 47.1368, lon: 7.2468, minZoom: 9 },
    { name: "Thun", lat: 46.7580, lon: 7.6280, minZoom: 9 }, { name: "Bellinzona", lat: 46.1928, lon: 9.0170, minZoom: 9 },
    { name: "Fribourg", lat: 46.8065, lon: 7.1620, minZoom: 9 }, { name: "Neuchâtel", lat: 46.9896, lon: 6.9293, minZoom: 9 },
    { name: "Schaffhausen", lat: 47.6959, lon: 8.6380, minZoom: 9 }, { name: "Aarau", lat: 47.3925, lon: 8.0442, minZoom: 9 },
    { name: "Olten", lat: 47.3522, lon: 7.9077, minZoom: 9 }, { name: "Brig", lat: 46.3167, lon: 7.9878, minZoom: 9 },
    { name: "Davos", lat: 46.8027, lon: 9.8360, minZoom: 9 }, { name: "St. Moritz", lat: 46.4908, lon: 9.8355, minZoom: 9 },
    { name: "Altdorf", lat: 46.8804, lon: 8.6444, minZoom: 9 }, { name: "Schwyz", lat: 47.0207, lon: 8.6530, minZoom: 9 },
    { name: "Sarnen", lat: 46.8961, lon: 8.2458, minZoom: 9 }, { name: "Stans", lat: 46.9575, lon: 8.3660, minZoom: 9 },
    { name: "Appenzell", lat: 47.3312, lon: 9.4098, minZoom: 9 }, { name: "Delémont", lat: 47.3653, lon: 7.3444, minZoom: 9 },
    { name: "Frauenfeld", lat: 47.5583, lon: 8.8986, minZoom: 9 }, { name: "Liestal", lat: 47.4844, lon: 7.7348, minZoom: 9 },
    { name: "Interlaken", lat: 46.6863, lon: 7.8632, minZoom: 10 }, { name: "Spiez", lat: 46.6888, lon: 7.6806, minZoom: 10 },
    { name: "Zermatt", lat: 45.9765, lon: 7.7491, minZoom: 10 }, { name: "Andermatt", lat: 46.6337, lon: 8.5947, minZoom: 10 },
    { name: "Locarno", lat: 46.1711, lon: 8.7995, minZoom: 10 }, { name: "Martigny", lat: 46.1037, lon: 7.0734, minZoom: 10 },
    { name: "Montreux", lat: 46.4312, lon: 6.9107, minZoom: 10 }, { name: "Vevey", lat: 46.4628, lon: 6.8432, minZoom: 10 },
    { name: "Yverdon", lat: 46.7785, lon: 6.6412, minZoom: 10 }, { name: "La Chaux-de-Fonds", lat: 47.1035, lon: 6.8328, minZoom: 10 },
    { name: "Bulle", lat: 46.6174, lon: 7.0569, minZoom: 10 }, { name: "Rapperswil", lat: 47.2267, lon: 8.8184, minZoom: 10 },
    { name: "Zug", lat: 47.1662, lon: 8.5155, minZoom: 10 }, { name: "Baden", lat: 47.4737, lon: 8.3087, minZoom: 10 },
    { name: "Lenzburg", lat: 47.3881, lon: 8.1809, minZoom: 10 }, { name: "Burgdorf", lat: 47.0573, lon: 7.6258, minZoom: 10 },
    { name: "Langenthal", lat: 47.2132, lon: 7.7915, minZoom: 10 }, { name: "Solothurn", lat: 47.2088, lon: 7.5370, minZoom: 10 },
    { name: "Glarus", lat: 47.0406, lon: 9.0678, minZoom: 10 }
];

// ================= HILFSFUNKTIONEN =================
function parseLocalStr(str) {
    if (!str) return new Date();
    const [datePart, timePart] = str.split(" ");
    const [d, m, y] = datePart.split(".").map(Number);
    const [hh, mm] = timePart.split(":").map(Number);
    return new Date(y, m - 1, d, hh, mm || 0);
}

function getActiveStateSide(domSide) {
    return isSplitActive ? domSide : 'left';
}

function isCurrentRunHistorical(side) {
    const st = modelsState[getActiveStateSide(side)];
    if (!st) return false;
    const runs = availableRuns[st.currentModel] || [];
    return Boolean(runs.length > 0 && st.currentRunId && st.currentRunId !== runs[0].id);
}

function modelHasEnsembleForCurrentVar(stateSide) {
    const st = modelsState[stateSide];
    if (!st || !st.config) return false;
    const vCfg = st.config.variables_config && st.config.variables_config[layer1Var];
    return Boolean(vCfg && vCfg.has_ensemble && st.config.member_names && st.config.member_names.length > 1);
}

function sanitizeMemberIndex(side) {
    const stateSide = getActiveStateSide(side);
    const st = modelsState[stateSide];
    if (!st || !st.config) return;

    if (!modelHasEnsembleForCurrentVar(stateSide)) {
        st.currentMemberIdx = 0;
        return;
    }

    const cfg = st.config;
    const statOffset = (cfg.member_names && cfg.member_names.length > 6) ? (cfg.member_names.length - 6) : 1;
    if (isCurrentRunHistorical(stateSide) && st.currentMemberIdx >= 1 && st.currentMemberIdx < statOffset) {
        st.currentMemberIdx = 0;
    }

    const maxIdx = (cfg.member_names && cfg.member_names.length > 0) ? (cfg.member_names.length - 1) : 0;
    if (st.currentMemberIdx > maxIdx || st.currentMemberIdx < 0) {
        st.currentMemberIdx = 0;
    }
}

function getStepIdxForSide(domSide) {
    const st = modelsState[getActiveStateSide(domSide)];
    if (!st || !st.times || st.times.length === 0) return 0;
    const baseTimes = modelsState.left.times;
    if (!baseTimes || baseTimes.length === 0) return 0;

    const safeMasterIdx = Math.max(0, Math.min(baseTimes.length - 1, currentStepIdx));
    const targetDateMs = parseLocalStr(baseTimes[safeMasterIdx].local_str).getTime();

    let bestIdx = 0, minDiff = Infinity;
    for (let i = 0; i < st.times.length; i++) {
        const diff = Math.abs(parseLocalStr(st.times[i].local_str).getTime() - targetDateMs);
        if (diff < minDiff) { minDiff = diff; bestIdx = i; }
    }
    return bestIdx;
}

function clampAndSyncMasterStep(newTimes) {
    if (!newTimes || newTimes.length === 0) {
        currentStepIdx = 0;
        return;
    }
    const oldTimes = modelsState.left.times;
    const targetDateMs = (oldTimes && oldTimes[currentStepIdx]) ? parseLocalStr(oldTimes[currentStepIdx].local_str).getTime() : null;

    if (targetDateMs !== null) {
        let bestIdx = 0, minDiff = Infinity;
        for (let i = 0; i < newTimes.length; i++) {
            const diff = Math.abs(parseLocalStr(newTimes[i].local_str).getTime() - targetDateMs);
            if (diff < minDiff) { minDiff = diff; bestIdx = i; }
        }
        currentStepIdx = bestIdx;
    } else {
        currentStepIdx = Math.max(0, Math.min(newTimes.length - 1, currentStepIdx));
    }
}

function setOverlaysVisible(visible) {
    const op = visible ? "1" : "0";
    [{ map: mapLeft, st: modelsState.left }, { map: mapRight, st: modelsState.right }].forEach(item => {
        if (!item.map) return;
        const cp = item.map.getPane('cityPane');
        if (cp) cp.style.opacity = op;
        if (item.st && item.st.arrowCanvas) item.st.arrowCanvas.style.opacity = op;
    });
}

function scheduleMapUpdates() {
    if (mapSafetyTimer) clearTimeout(mapSafetyTimer);
    if (mapUpdateTimer) clearTimeout(mapUpdateTimer);
    mapUpdateTimer = setTimeout(() => {
        drawVisibleArrows('left');
        if (isSplitActive) drawVisibleArrows('right');
        updateCityLabels();
        setOverlaysVisible(true);
    }, 40);
}

function syncMap(sourceMap, targetMap) {
    if (!sourceMap || !targetMap || !isSplitActive || isSyncingMaps) return;
    if (syncRafId) cancelAnimationFrame(syncRafId);
    syncRafId = requestAnimationFrame(() => {
        isSyncingMaps = true;
        targetMap.setView(sourceMap.getCenter(), sourceMap.getZoom(), { animate: false });
        isSyncingMaps = false;
    });
}

function toggleSplitScreen(e) {
    if (e && e.preventDefault) e.preventDefault();
    isSplitActive = !isSplitActive;

    const wrapper = document.getElementById("mapsWrapper");
    const btn = document.getElementById("splitBtn");
    document.body.classList.toggle("split-active", isSplitActive);
    if (btn) { btn.classList.toggle("active", isSplitActive); btn.blur(); }

    if (isSplitActive) {
        wrapper.classList.remove("single-view");
        wrapper.classList.add("split-view");
    } else {
        wrapper.classList.remove("split-view");
        wrapper.classList.add("single-view");
    }

    setTimeout(async () => {
        if (mapLeft) mapLeft.invalidateSize();
        if (mapRight) {
            mapRight.invalidateSize();
            if (mapLeft) mapRight.setView(mapLeft.getCenter(), mapLeft.getZoom(), { animate: false });
        }
        initMemberPanelsAll();
        updateModelButtonLabels();
        await updateForecast();
    }, 150);
}

function toggleLegend() {
    isLegendOpen = !isLegendOpen;
    const box = document.getElementById("legendBox");
    const btn = document.getElementById("btnToggleLegend");
    if (box) box.style.display = isLegendOpen ? "flex" : "none";
    if (btn) btn.classList.toggle("active", isLegendOpen);
}

function toggleMobileModelPanel(forceState, e) {
    if (e && e.preventDefault) e.preventDefault();
    isMobileModelExpanded = (typeof forceState === "boolean") ? forceState : !isMobileModelExpanded;
    document.body.classList.toggle("mobile-models-expanded", isMobileModelExpanded);
    ['modelSelectRight', 'modelSelectLeft'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.toggle("mobile-collapsed", !isMobileModelExpanded);
    });
}

function toggleMemberPanel(side) {
    const p = document.getElementById(side === 'left' ? "memberPanelLeft" : "memberPanelRight");
    const b = document.getElementById(side === 'left' ? "btnToggleMemberLeft" : "btnToggleMemberRight");
    if (!p) return;
    const isOpen = (p.style.display === "flex");
    p.style.display = isOpen ? "none" : "flex";
    if (b) b.classList.toggle("active", !isOpen);
}

function toggleEnsembleAccordionLocal(side) {
    const cont = document.getElementById(side === 'left' ? "ensembleContainerLeft" : "ensembleContainerRight");
    const btn = document.getElementById(side === 'left' ? "btnToggleEnsembleLeft" : "btnToggleEnsembleRight");
    if (!cont) return;
    const isOpen = (cont.style.display !== "none");
    cont.style.display = isOpen ? "none" : "block";
    if (btn) btn.classList.toggle("open", !isOpen);

    isEnsembleOpen = !isOpen;
    localStorage.setItem("icon_ensemble_open", isEnsembleOpen ? "true" : "false");
    updateEnsembleToggleState();
}

function updateCityLabels() {
    [{ map: mapLeft, group: cityLayerGroupLeft }, { map: mapRight, group: cityLayerGroupRight }].forEach(item => {
        if (!item.map || !item.group) return;
        item.group.clearLayers();
        const curZoom = item.map.getZoom();
        const bounds = item.map.getBounds();

        CITIES.forEach(city => {
            if (curZoom >= city.minZoom) {
                const latlng = L.latLng(city.lat, city.lon);
                if (bounds.contains(latlng)) {
                    const html = `<div class="city-label-container"><div class="city-dot"></div><span class="city-name">${city.name}</span></div>`;
                    L.marker(latlng, { icon: L.divIcon({ html: html, className: 'city-div-icon', iconSize: [0, 0] }), pane: 'cityPane', interactive: false }).addTo(item.group);
                }
            }
        });
    });
}

function getDateKeyForStep(stepIdx) {
    const t = modelsState.left.times;
    return (t && t[stepIdx]) ? t[stepIdx].local_str.split(" ")[0] : "";
}

function closeAllPopups() {
    ['left', 'right'].forEach(side => {
        ALL_MODELS.forEach(m => {
            const el = document.getElementById(`runDropdown-${side}-${m}`);
            if (el) el.style.display = "none";
        });
        const p = document.getElementById(side === 'left' ? "memberPanelLeft" : "memberPanelRight");
        const b = document.getElementById(side === 'left' ? "btnToggleMemberLeft" : "btnToggleMemberRight");
        if (p) p.style.display = "none";
        if (b) b.classList.remove("active");
    });

    const l2 = document.getElementById("layer2Dropdown");
    if (l2) l2.style.display = "none";
    const sp = document.getElementById("settingsPopup");
    if (sp) sp.style.display = "none";
}

function setBaseMapOpacity(val) {
    baseMapOpacity = val / 100.0;
    const lbl = document.getElementById("opacityLabelBase");
    const sld = document.getElementById("opacitySliderBase");
    if (lbl) lbl.innerText = `${val}%`;
    if (sld) sld.value = val;
    [mapLeft, mapRight].forEach(m => {
        if (!m) return;
        ['reliefPane', 'waterPane'].forEach(p => { if (m.getPane(p)) m.getPane(p).style.opacity = baseMapOpacity; });
    });
}

function setBaseMapStyle(style) {
    baseMapStyle = style;
    document.getElementById("btnBaseRelief").classList.toggle("active", style === 'relief');
    document.getElementById("btnBaseSimple").classList.toggle("active", style === 'simple');

    [{ map: mapLeft, relief: baseReliefLayerLeft, rivers: riversLayerLeft, cantons: cantonalBoundaryLayerLeft },
     { map: mapRight, relief: baseReliefLayerRight, rivers: riversLayerRight, cantons: cantonalBoundaryLayerRight }
    ].forEach(c => {
        if (!c.map) return;
        const container = c.map.getContainer();
        if (style === 'simple') {
            if (c.relief && c.map.hasLayer(c.relief)) c.map.removeLayer(c.relief);
            if (c.rivers && c.map.hasLayer(c.rivers)) c.map.removeLayer(c.rivers);
            container.classList.add('simple-gray-background');
            if (c.cantons && !c.map.hasLayer(c.cantons)) c.cantons.addTo(c.map);
        } else {
            container.classList.remove('simple-gray-background');
            if (c.cantons && c.map.hasLayer(c.cantons)) c.map.removeLayer(c.cantons);
            if (c.relief && !c.map.hasLayer(c.relief)) c.relief.addTo(c.map);
            if (c.rivers && !c.map.hasLayer(c.rivers)) c.rivers.addTo(c.map);
        }
    });
}

function toggleNavMode() {
    verticalNavMode = (verticalNavMode === 'member') ? 'run' : 'member';
    updateNavModeButton();
}

function updateNavModeButton() {
    const btn = document.getElementById("navModeBtn");
    if (!btn) return;
    const isRun = (verticalNavMode === 'run');
    btn.innerText = isRun ? "Lauf" : "Mbr";
    btn.classList.toggle("mode-run", isRun);
}

function navRun(dir) {
    const side = isSplitActive ? 'right' : 'left';
    const st = modelsState[side];
    const runs = availableRuns[st.currentModel] || [];
    if (runs.length <= 1) return;
    let idx = runs.findIndex(r => r.id === st.currentRunId);
    if (idx === -1) idx = 0;
    const newIdx = idx + dir;
    if (newIdx >= 0 && newIdx < runs.length) selectRun(side, st.currentModel, runs[newIdx].id);
}

async function handleModelButtonClick(modelName, side) {
    const stateSide = getActiveStateSide(side);
    const st = modelsState[stateSide];
    if (st.currentModel !== modelName) {
        st.currentModel = modelName;
        const runs = availableRuns[modelName] || [];
        const runId = selectedRuns[stateSide][modelName] || (runs.length > 0 ? runs[0].id : null);
        await loadModelAndRun(stateSide, modelName, runId);
    } else {
        toggleRunDropdown(side, modelName);
    }
}

async function fetchAvailableRuns(modelName) {
    try {
        const res = await fetch(`data/${modelName}/runs.json?t=${Date.now()}`);
        if (res.ok) availableRuns[modelName] = await res.json();
    } catch (e) {
        console.warn("Konnte runs.json nicht laden für " + modelName, e);
    }
    updateModelButtonLabels();
}

function getModelShortLabel(m) {
    const LABELS = { "kenda-ch1": "KND", "icon-ch1": "CH1", "icon-ch2": "CH2", "icon-d2": "D2", "icon-eu": "EU", "ecmwf": "EC", "aifs": "AI", "gfs": "GFS" };
    return LABELS[m] || "AROME";
}

function updateModelButtonLabels() {
    ['left', 'right'].forEach(side => {
        const stateSide = getActiveStateSide(side);
        const st = modelsState[stateSide];
        const tabLabel = document.getElementById(side === 'left' ? "tabModelLabelLeft" : "tabModelLabelRight");
        if (tabLabel && st) tabLabel.innerText = getModelShortLabel(st.currentModel);

        ALL_MODELS.forEach(m => {
            const btn = document.getElementById(`btnModel-${side}-${m}`);
            if (!btn) return;
            const runs = availableRuns[m] || [];
            const activeRun = (st && st.currentModel === m) ? st.currentRunId : (selectedRuns[stateSide][m] || (runs[0] ? runs[0].id : null));
            const activeObj = runs.find(r => r.id === activeRun) || runs[0];
            btn.innerHTML = `<span class="model-title">${getModelShortLabel(m)} ▾</span><span class="model-time">${activeObj ? activeObj.label : "--"}</span>`;
            btn.classList.toggle("active", Boolean(st && st.currentModel === m));
        });
    });
}

function toggleRunDropdown(side, modelName) {
    const stateSide = getActiveStateSide(side);
    const el = document.getElementById(`runDropdown-${side}-${modelName}`);
    if (!el) return;
    if (el.style.display === "flex") { el.style.display = "none"; return; }

    const runs = availableRuns[modelName] || [];
    el.innerHTML = "";
    if (runs.length === 0) {
        el.innerHTML = `<div style="font-size:11px; padding:4px 8px; color:#aaa;">Keine alten Läufe</div>`;
    } else {
        runs.forEach(r => {
            const item = document.createElement("button");
            item.className = "run-item" + (r.id === modelsState[stateSide].currentRunId ? " active" : "");
            item.innerHTML = `<span>${r.label}</span>`;
            item.onclick = e => {
                e.stopPropagation();
                el.style.display = "none";
                selectRun(stateSide, modelName, r.id);
            };
            el.appendChild(item);
        });
    }

    const header = document.getElementById(`modelSelect${side === 'left' ? 'Left' : 'Right'}`);
    const rect = header.getBoundingClientRect();
    el.style.top = `${rect.bottom + 5}px`;
    if (side === 'left') { el.style.left = `${rect.left}px`; el.style.right = "auto"; }
    else { el.style.right = `${window.innerWidth - rect.right}px`; el.style.left = "auto"; }
    el.style.display = "flex";
}

async function selectRun(side, modelName, runId) {
    const stateSide = getActiveStateSide(side);
    modelsState[stateSide].currentModel = modelName;
    modelsState[stateSide].currentRunId = runId;
    selectedRuns[stateSide][modelName] = runId;
    await loadModelAndRun(stateSide, modelName, runId);
}

async function loadModelAndRun(side, modelName, runId) {
    const st = modelsState[side];
    st.currentModel = modelName;

    if (!availableRuns[modelName] || availableRuns[modelName].length === 0) {
        await fetchAvailableRuns(modelName);
    }
    const runs = availableRuns[modelName] || [];
    if (!runId && runs.length > 0) runId = runs[0].id;
    st.currentRunId = runId;
    selectedRuns[side][modelName] = runId;

    updateModelButtonLabels();

    const cacheBuster = Date.now();
    const runPath = runId ? `data/${modelName}/${runId}` : `data/${modelName}`;
    try {
        const [configRes, timesRes] = await Promise.all([
            fetch(`${runPath}/config.json?t=${cacheBuster}`),
            fetch(`${runPath}/times.json?t=${cacheBuster}`)
        ]);
        if (!configRes.ok || !timesRes.ok) throw new Error("Fehler beim Laden von Konfiguration oder Zeitschritten");
        st.config = await configRes.json();
        const newTimes = await timesRes.json();
        if (side === 'left') clampAndSyncMasterStep(newTimes);
        st.times = newTimes;
    } catch (e) {
        console.error("Fehler beim Laden von " + modelName, e);
        return;
    }

    sanitizeMemberIndex(side);
    initNavigationBars();
    initLayer2Dropdown();
    initDayButtons();
    initMemberPanelsAll();
    await updateForecast();
}

function updateEnsembleToggleState() {
    ['left', 'right'].forEach(side => {
        const stateSide = getActiveStateSide(side);
        const btn = document.getElementById(side === 'left' ? "btnToggleEnsembleLeft" : "btnToggleEnsembleRight");
        const cfg = modelsState[stateSide].config;
        if (!btn || !cfg || !cfg.member_names) return;
        const statOffset = cfg.member_names.length - 6;
        const isMemberActive = (modelsState[stateSide].currentMemberIdx >= 1 && modelsState[stateSide].currentMemberIdx < statOffset);
        btn.classList.toggle("active-indicator", isMemberActive && !isEnsembleOpen);
    });
}

function toggleWetterMenu() {
    isWetterOpen = !isWetterOpen;
    document.getElementById("wetterSubRow").style.display = isWetterOpen ? "flex" : "none";
    const btn = document.getElementById("btnToggleWetter");
    btn.classList.toggle("open", isWetterOpen);
    btn.innerText = isWetterOpen ? "Wetter ▴" : "Wetter ▾";
}

function toggleHoehenMenu() {
    isHoehenOpen = !isHoehenOpen;
    document.getElementById("hoehenSubRow").style.display = isHoehenOpen ? "flex" : "none";
    const btn = document.getElementById("btnToggleHoehen");
    btn.classList.toggle("open", isHoehenOpen);
    btn.innerText = isHoehenOpen ? "Höhenwind ▴" : "Höhenwind ▾";
}

function toggleLayer2Dropdown() {
    const el = document.getElementById("layer2Dropdown");
    if (el.style.display === "flex") { el.style.display = "none"; return; }
    const btn = document.getElementById("layer2Btn");
    const rect = btn.getBoundingClientRect();
    el.style.top = `${rect.bottom + 6}px`;
    el.style.left = `${rect.left + rect.width / 2}px`;
    el.style.transform = "translateX(-50%)";
    el.style.display = "flex";
}

function toggleSettings(e) {
    if (e && e.preventDefault) e.preventDefault();
    const el = document.getElementById("settingsPopup");
    el.style.display = (el.style.display === "block") ? "none" : "block";
}

function setLayerMode(layerNum, mode) {
    if (layerNum === 1) {
        layer1Mode = mode;
        document.getElementById("btnModeFillL1").classList.toggle("active", mode === 'fill');
        document.getElementById("btnModeLineL1").classList.toggle("active", mode === 'line');
    } else {
        layer2Mode = mode;
        document.getElementById("btnModeFillL2").classList.toggle("active", mode === 'fill');
        document.getElementById("btnModeLineL2").classList.toggle("active", mode === 'line');
    }
    renderContours('left');
    if (isSplitActive) renderContours('right');
}

function setLayerOpacity(layerNum, val) {
    const op = val / 100.0;
    if (layerNum === 1) {
        layer1Opacity = op;
        document.getElementById("opacityLabelL1").innerText = `${val}%`;
        document.getElementById("opacitySliderL1").value = val;
    } else {
        layer2Opacity = op;
        document.getElementById("opacityLabelL2").innerText = `${val}%`;
        document.getElementById("opacitySliderL2").value = val;
    }
    [mapLeft, mapRight].forEach(m => {
        if (!m) return;
        const p = m.getPane(layerNum === 1 ? 'contourPane1' : 'contourPane2');
        if (p) p.style.opacity = op;
    });
}

function initNavigationBars() {
    const wetterCont = document.getElementById("wetterSubRow");
    const hoehenCont = document.getElementById("hoehenSubRow");
    wetterCont.innerHTML = "";
    hoehenCont.innerHTML = "";

    const cfg = modelsState.left.config;
    if (!cfg) return;
    const vars = cfg.variables || Object.keys(cfg.variables_config);
    if (!layer1Var || !vars.includes(layer1Var)) layer1Var = vars[0];

    document.getElementById("varBtn-wind").style.display = vars.includes("wind") ? "inline-block" : "none";
    document.getElementById("varBtn-gust").style.display = vars.includes("gust") ? "inline-block" : "none";

    const hasAlt = vars.some(v => cfg.variables_config[v] && cfg.variables_config[v].type === "altitude");
    document.getElementById("btnToggleHoehen").style.display = hasAlt ? "inline-flex" : "none";

    const hasWetter = vars.some(v => v !== "wind" && v !== "gust" && cfg.variables_config[v] && cfg.variables_config[v].type !== "altitude");
    document.getElementById("btnToggleWetter").style.display = hasWetter ? "inline-flex" : "none";

    vars.forEach(vKey => {
        const vCfg = cfg.variables_config[vKey];
        if (!vCfg || vKey === "wind" || vKey === "gust") return;
        const btn = document.createElement("button");
        btn.className = "var-btn";
        btn.id = "varBtn-" + vKey;
        btn.innerText = vCfg.label || vKey;
        btn.onclick = () => switchLayer1(vKey);
        (vCfg.type === "altitude" ? hoehenCont : wetterCont).appendChild(btn);
    });
    updateActiveButtonStates();
}

function updateActiveButtonStates() {
    const cfg = modelsState.left.config;
    if (!cfg) return;
    const vars = cfg.variables || Object.keys(cfg.variables_config);
    let isWetterActive = false, isHoehenActive = false;

    vars.forEach(vKey => {
        const btn = document.getElementById("varBtn-" + vKey);
        const isActive = (vKey === layer1Var);
        if (btn) btn.classList.toggle("active", isActive);
        if (isActive) {
            const vCfg = cfg.variables_config[vKey];
            if (vCfg) {
                if (vCfg.type === "altitude") isHoehenActive = true;
                else if (vKey !== "wind" && vKey !== "gust") isWetterActive = true;
            }
        }
    });

    document.getElementById("btnToggleWetter").classList.toggle("has-active", isWetterActive);
    document.getElementById("btnToggleHoehen").classList.toggle("has-active", isHoehenActive);
    if (isWetterActive && !isWetterOpen) toggleWetterMenu();
    if (isHoehenActive && !isHoehenOpen) toggleHoehenMenu();
}

function initLayer2Dropdown() {
    const menu = document.getElementById("layer2Dropdown");
    menu.innerHTML = "";

    const clearBtn = document.createElement("button");
    clearBtn.className = "dropdown-item clear";
    clearBtn.innerText = "✖ 2. Ebene deaktivieren";
    clearBtn.onclick = () => setSecondaryVar(null);
    menu.appendChild(clearBtn);

    const cfg = modelsState.left.config;
    if (!cfg) return;
    const vars = cfg.variables || Object.keys(cfg.variables_config);
    vars.forEach(vKey => {
        const vCfg = cfg.variables_config[vKey];
        const btn = document.createElement("button");
        btn.className = "dropdown-item";
        btn.innerText = vCfg ? vCfg.label : vKey;
        btn.onclick = () => setSecondaryVar(vKey);
        menu.appendChild(btn);
    });
}

function setSecondaryVar(newVar) {
    layer2Var = newVar;
    const el = document.getElementById("layer2Dropdown");
    if (el) el.style.display = "none";

    const btn = document.getElementById("layer2Btn");
    const cfgSec = document.getElementById("cfgSectionL2");
    const titleSec = document.getElementById("cfgTitleL2");
    const cfg = modelsState.left.config;

    if (layer2Var) {
        const vCfg = (cfg && cfg.variables_config[layer2Var]) || {};
        const lbl = vCfg.label || layer2Var;
        if (btn) btn.innerText = `2. Ebene: ${lbl} ✕`;
        btn.classList.add("active");
        cfgSec.style.opacity = "1";
        titleSec.innerText = `2. Ebene: ${lbl}`;
        setLayerOpacity(2, (vCfg.palette === "cloud") ? 95 : 60);
    } else {
        if (btn) btn.innerText = "+ 2. Ebene";
        btn.classList.remove("active");
        cfgSec.style.opacity = "0.5";
        titleSec.innerText = "2. Ebene: Keine";
    }
    updateForecast();
}

function switchLayer1(newVar) {
    if (layer1Var === newVar) return;
    layer1Var = newVar;
    updateActiveButtonStates();

    ['left', 'right'].forEach(s => {
        if (!modelHasEnsembleForCurrentVar(s)) modelsState[s].currentMemberIdx = 0;
    });

    const cfg = modelsState.left.config;
    const vCfg = cfg ? cfg.variables_config[layer1Var] : null;
    document.getElementById("cfgTitleL1").innerText = "1. Ebene: " + (vCfg ? vCfg.label : layer1Var);
    setLayerOpacity(1, (vCfg && vCfg.palette === "cloud") ? 95 : 60);

    initMemberPanelsAll();
    updateForecast();
}

function navLeft() {
    const curDateKey = getDateKeyForStep(currentStepIdx);
    const steps = dayTimesteps[curDateKey] || [];
    const pos = steps.indexOf(currentStepIdx);

    if (pos > 0) {
        currentStepIdx = steps[pos - 1];
    } else {
        const dIdx = uniqueDays.findIndex(d => d.dateKey === curDateKey);
        if (dIdx > 0) {
            const prevSteps = dayTimesteps[uniqueDays[dIdx - 1].dateKey];
            if (prevSteps && prevSteps.length > 0) currentStepIdx = prevSteps[prevSteps.length - 1];
        }
    }
    updateForecast();
}

function navRight() {
    const curDateKey = getDateKeyForStep(currentStepIdx);
    const steps = dayTimesteps[curDateKey] || [];
    const pos = steps.indexOf(currentStepIdx);

    if (pos < steps.length - 1) {
        currentStepIdx = steps[pos + 1];
    } else {
        const dIdx = uniqueDays.findIndex(d => d.dateKey === curDateKey);
        if (dIdx < uniqueDays.length - 1) {
            const nextSteps = dayTimesteps[uniqueDays[dIdx + 1].dateKey];
            if (nextSteps && nextSteps.length > 0) currentStepIdx = nextSteps[0];
        }
    }
    updateForecast();
}

function navUp() {
    const side = isSplitActive ? 'right' : 'left';
    if (verticalNavMode === 'run') { navRun(-1); return; }
    const st = modelsState[side];
    if (!modelHasEnsembleForCurrentVar(side)) return;
    const statOffset = st.config.member_names.length - 6;

    if (!isEnsembleOpen) {
        st.currentMemberIdx = (st.currentMemberIdx === statOffset) ? 0 : (st.currentMemberIdx > statOffset ? st.currentMemberIdx - 1 : 0);
    } else {
        st.currentMemberIdx = Math.max(0, st.currentMemberIdx - 1);
    }
    sanitizeMemberIndex(side);
    updateForecast();
}

function navDown() {
    const side = isSplitActive ? 'right' : 'left';
    if (verticalNavMode === 'run') { navRun(1); return; }
    const st = modelsState[side];
    if (!modelHasEnsembleForCurrentVar(side)) return;
    const maxIdx = st.config.member_names.length - 1;
    const statOffset = st.config.member_names.length - 6;

    if (!isEnsembleOpen) {
        if (st.currentMemberIdx === 0) st.currentMemberIdx = statOffset;
        else if (st.currentMemberIdx >= statOffset) st.currentMemberIdx = Math.min(maxIdx, st.currentMemberIdx + 1);
    } else {
        st.currentMemberIdx = Math.min(maxIdx, st.currentMemberIdx + 1);
    }
    sanitizeMemberIndex(side);
    updateForecast();
}

function initDayButtons() {
    const container = document.getElementById("dayButtonsContainer");
    container.innerHTML = "";
    uniqueDays = [];
    dayTimesteps = {};

    const times = modelsState.left.times;
    if (!times) return;

    times.forEach((t, idx) => {
        const datePart = t.local_str.split(" ")[0];
        const [d, m, y] = datePart.split(".").map(Number);
        const dayName = weekdays[new Date(y, m - 1, d).getDay()];

        if (!dayTimesteps[datePart]) {
            dayTimesteps[datePart] = [];
            uniqueDays.push({ dateKey: datePart, dayName: dayName });
        }
        dayTimesteps[datePart].push(idx);
    });

    uniqueDays.forEach((dayObj, index) => {
        const btn = document.createElement("button");
        btn.className = "day-btn";
        btn.id = "day-btn-" + index;
        btn.innerText = dayObj.dayName;
        btn.onclick = () => jumpToDaySameHour(dayObj.dateKey);
        container.appendChild(btn);
    });
}

function jumpToDaySameHour(targetDateKey) {
    const times = modelsState.left.times;
    if (!times || !times[currentStepIdx]) return;
    const currentHour = parseInt(times[currentStepIdx].local_str.split(" ")[1].split(":")[0]);
    const targetIndices = dayTimesteps[targetDateKey];
    if (!targetIndices || targetIndices.length === 0) return;

    let bestIdx = targetIndices[0], minDiff = 999;
    targetIndices.forEach(idx => {
        const diff = Math.abs(parseInt(times[idx].local_str.split(" ")[1].split(":")[0]) - currentHour);
        if (diff < minDiff) { minDiff = diff; bestIdx = idx; }
    });
    currentStepIdx = bestIdx;
    updateForecast();
}

function renderMemberButtonsForTarget(domSide) {
    const stateSide = getActiveStateSide(domSide);
    const st = modelsState[stateSide];
    if (!st || !st.config) return;
    const cfg = st.config;

    const hCont = document.getElementById(domSide === 'left' ? "hauptlaufContainerLeft" : "hauptlaufContainerRight");
    const eCont = document.getElementById(domSide === 'left' ? "ensembleContainerLeft" : "ensembleContainerRight");
    const sCont = document.getElementById(domSide === 'left' ? "statistikenContainerLeft" : "statistikenContainerRight");
    const ensGroup = document.getElementById(domSide === 'left' ? "ensembleGroupLeft" : "ensembleGroupRight");
    const notice = document.getElementById(domSide === 'left' ? "onlyHlNoticeLeft" : "onlyHlNoticeRight");
    const btnToggleEns = document.getElementById(domSide === 'left' ? "btnToggleEnsembleLeft" : "btnToggleEnsembleRight");

    if (!hCont || !eCont || !sCont) return;

    const oldNoticeId = domSide === 'left' ? "oldRunNoticeLeft" : "oldRunNoticeRight";
    let oldNotice = document.getElementById(oldNoticeId);
    if (!oldNotice && ensGroup) {
        oldNotice = document.createElement("div");
        oldNotice.id = oldNoticeId;
        oldNotice.className = "only-hl-info";
        oldNotice.style.padding = "6px 4px";
        if (btnToggleEns) ensGroup.insertBefore(oldNotice, btnToggleEns);
        else ensGroup.appendChild(oldNotice);
    }

    hCont.innerHTML = "";
    eCont.innerHTML = "";
    sCont.innerHTML = "";
    sanitizeMemberIndex(stateSide);

    const hasEns = modelHasEnsembleForCurrentVar(stateSide);
    const isOldRun = isCurrentRunHistorical(stateSide);
    const statOffset = (cfg.member_names && cfg.member_names.length > 6) ? (cfg.member_names.length - 6) : 1;

    cfg.member_names.forEach((name, idx) => {
        const btn = document.createElement("button");
        btn.className = "member-btn";
        btn.id = `${domSide}-member-btn-${idx}`;

        if (idx === 0) {
            btn.innerText = "Hauptlauf";
            btn.onclick = () => { st.currentMemberIdx = idx; updateForecast(); };
            hCont.appendChild(btn);
        } else if (hasEns && idx >= 1 && idx < statOffset) {
            if (!isOldRun) {
                btn.innerText = "Member " + idx;
                btn.onclick = () => { st.currentMemberIdx = idx; updateForecast(); };
                eCont.appendChild(btn);
            }
        } else if (hasEns) {
            btn.innerText = name;
            btn.onclick = () => { st.currentMemberIdx = idx; updateForecast(); };
            sCont.appendChild(btn);
        }
    });

    if (hasEns) {
        if (ensGroup) ensGroup.style.display = "block";
        if (isOldRun) {
            if (btnToggleEns) btnToggleEns.style.display = "none";
            if (eCont) eCont.style.display = "none";
            if (oldNotice) { oldNotice.style.display = "block"; oldNotice.innerText = "Alter Lauf: Nur Hauptlauf & Statistiken verfügbar"; }
            if (notice) notice.style.display = "none";
        } else {
            if (btnToggleEns) btnToggleEns.style.display = "flex";
            if (oldNotice) oldNotice.style.display = "none";
            if (notice) notice.style.display = "none";
        }
    } else {
        if (ensGroup) ensGroup.style.display = "none";
        if (oldNotice) oldNotice.style.display = "none";
        if (notice) { notice.style.display = "block"; notice.innerText = "Nur Hauptlauf verfügbar"; }
    }
}

function initMemberPanelsAll() {
    renderMemberButtonsForTarget('left');
    renderMemberButtonsForTarget('right');
    updateEnsembleToggleState();
}

function renderSingleLegendCol(varName, isIQR) {
    const cfg = modelsState.left.config || {};
    const vCfg = (cfg.variables_config && cfg.variables_config[varName]) || {};
    const paletteType = isIQR ? ("iqr_" + (vCfg.palette || "wind")) : (vCfg.palette || "wind");
    const p = (cfg.palettes && cfg.palettes[paletteType]) || (cfg.palettes && cfg.palettes["wind"]) || { levels: [], colors: [] };
    const colors = p.colors || [];
    const levels = p.levels || [];

    let title = "";
    if (isIQR) {
        title = (vCfg.palette === "sun" || vCfg.palette === "cloud") ? "% (IQR)" : (vCfg.palette === "dbz" ? "dBZ (IQR)" : "km/h (IQR)");
    } else {
        title = (vCfg.palette === "sun") ? "Sun %" : (vCfg.palette === "cloud" ? "Cloud %" : (vCfg.palette === "dbz" ? "dBZ" : "km/h"));
    }

    let barHtml = "";
    for (let i = colors.length - 1; i >= 0; i--) {
        const c = colors[i];
        const isTrans = (c === 'transparent' || c === '#ffffff00' || (c.length === 9 && c.endsWith('00')));
        const border = ((paletteType === "dbz" || paletteType === "cloud") && !isTrans)
            ? "border-bottom: 1px solid rgba(255,255,255,0.4);"
            : (c.toLowerCase() === "#ffffff" ? "border-top: 1px solid rgba(0,0,0,0.3); border-bottom: 1px solid rgba(0,0,0,0.3);" : "");
        barHtml += `<div style="background-color: ${isTrans ? 'transparent' : c}; flex: 1; ${border}"></div>`;
    }

    const LABEL_MAP = {
        "dbz": ["64","61","60","59","58","57","56","55","54","53","52","51","49","47","45","41","31","24","19","7"],
        "sun": ["100","80","60","40","20","0"],
        "cloud": ["100","95","90","80","70","60","50","40","30","20","10"],
        "iqr_dbz": ["+","65","56","48","40","32","25","18","12","6","0"],
        "iqr_sun": ["100","90","80","70","60","50","40","30","20","10","0"],
        "iqr_cloud": ["100","90","80","70","60","50","40","30","20","10","0"],
        "iqr_wind": ["+","30","24","18","14","10","8","6","4","2","0"]
    };

    let labelsArr = LABEL_MAP[paletteType];
    if (!labelsArr) {
        labelsArr = (levels && levels.length > 15)
            ? ["+","135","125","115","105","95","85","75","65","55","45","36","27","23","18","14","11","7","4","0"]
            : ["+","45","36","27","23","18","14","11","7","4","0"];
    }
    const labelsHtml = labelsArr.map(l => `<div>${l}</div>`).join("");

    return `
        <div class="legend-column">
            <div class="legend-title">${title}</div>
            <div class="legend-scale">
                <div class="legend-bar">${barHtml}</div>
                <div class="legend-labels">${labelsHtml}</div>
            </div>
        </div>
    `;
}

function updateLegend() {
    const box = document.getElementById("legendBox");
    const cfg = modelsState.left.config;
    if (!cfg) return;
    const hasMultiple = modelHasEnsembleForCurrentVar('left');
    const iqrIdx = (cfg.member_names && cfg.member_names.length > 1) ? (cfg.member_names.length - 1) : 0;
    const isIQR1 = (hasMultiple && modelsState.left.currentMemberIdx === iqrIdx);

    let html = renderSingleLegendCol(layer1Var, isIQR1);
    if (layer2Var && layer2Var !== layer1Var) {
        const vCfg2 = cfg.variables_config[layer2Var] || {};
        const isIQR2 = (hasMultiple && vCfg2.has_ensemble && modelsState.left.currentMemberIdx === iqrIdx);
        html += renderSingleLegendCol(layer2Var, isIQR2);
    }
    box.innerHTML = html;
}

async function fetchAndDecompress(url) {
    const response = await fetch(url);
    if (!response.ok) return null;
    const ds = new DecompressionStream('gzip');
    return await new Response(response.body.pipeThrough(ds)).arrayBuffer();
}

function decodeBinaryGrid(buffer, cfg) {
    if (!buffer) return null;
    const totalPoints = cfg.nx * cfg.ny;
    const lowBytes = new Uint8Array(buffer, 0, totalPoints);
    const highBytes = new Uint8Array(buffer, totalPoints, totalPoints);
    const s = new Int16Array(totalPoints);
    for (let i = 0; i < totalPoints; i++) s[i] = (highBytes[i] << 8) | lowBytes[i];
    const d = (buffer.byteLength >= (totalPoints * 3)) ? new Uint8Array(buffer, totalPoints * 2, totalPoints) : null;
    return { s, d };
}

function generateContoursClient(gridObj, paletteType, cfg) {
    if (!gridObj || !gridObj.s) return null;
    const p = cfg.palettes[paletteType] || cfg.palettes["wind"];
    const { levels, colors } = p;
    const s = gridObj.s;
    const values = new Float32Array(s.length);

    for (let i = 0; i < s.length; i++) values[i] = (s[i] < 0) ? NaN : (s[i] / 10.0);

    const thresholds = levels.slice(0, levels.length - 1);
    const rawContours = d3.contours().size([cfg.nx, cfg.ny]).smooth(true).thresholds(thresholds)(values);
    const dx = (cfg.xmax - cfg.xmin) / (cfg.nx - 1);
    const dy = (cfg.ymax - cfg.ymin) / (cfg.ny - 1);

    const features = [];
    for (let i = 0; i < rawContours.length; i++) {
        const c = rawContours[i];
        if (!c.coordinates || c.coordinates.length === 0) continue;
        const color = colors[i] || colors[colors.length - 1];
        const geoCoords = c.coordinates.map(polygon =>
            polygon.map(ring => ring.map(pt => [cfg.xmin + (pt[0] - 0.5) * dx, cfg.ymin + (pt[1] - 0.5) * dy]))
        );
        features.push({
            type: "Feature",
            properties: { fill: color, stroke: color },
            geometry: { type: "MultiPolygon", coordinates: geoCoords }
        });
    }
    return { type: "FeatureCollection", features };
}

async function ensureDataLoaded(side, varName, memberIdx, stepIdx) {
    const st = modelsState[side];
    const cacheKey = `${st.currentModel}_${st.currentRunId}_${varName}_${memberIdx}_${stepIdx}`;
    const vCfg = (st.config && st.config.variables_config && st.config.variables_config[varName]) || {};
    const hasMultiple = modelHasEnsembleForCurrentVar(side);
    const iqrIdx = (st.config && st.config.member_names && st.config.member_names.length > 1) ? (st.config.member_names.length - 1) : 0;
    const paletteType = (hasMultiple && memberIdx === iqrIdx) ? ("iqr_" + (vCfg.palette || "wind")) : (vCfg.palette || "wind");

    if (!cacheContours[cacheKey]) {
        const runBuster = encodeURIComponent(st.config.ref_time_utc);
        const basePath = st.currentRunId ? `data/${st.currentModel}/${st.currentRunId}` : `data/${st.currentModel}`;
        if (!cacheGrid[cacheKey]) {
            try {
                const rawBuffer = await fetchAndDecompress(`${basePath}/grid_${varName}_m${memberIdx}_s${stepIdx}.bin.gz?v=${runBuster}`);
                if (rawBuffer) storeInBoundedCache(cacheGrid, cacheKey, decodeBinaryGrid(rawBuffer, st.config));
            } catch (err) {
                console.warn("Konnte Daten nicht laden: " + cacheKey, err);
            }
        }
        if (cacheGrid[cacheKey]) {
            storeInBoundedCache(cacheContours, cacheKey, generateContoursClient(cacheGrid[cacheKey], paletteType, st.config));
        }
    }
    return cacheKey;
}

function initMapInstance(domId) {
    const swisstopo_relief_url = "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissalti3d-reliefschattierung/default/current/3857/{z}/{x}/{y}.png";
    const swisstopo_lakes_url = "https://wmts.geo.admin.ch/1.0.0/ch.bafu.vec25-seen/default/current/3857/{z}/{x}/{y}.png";
    const swisstopo_rivers_url = "https://wmts.geo.admin.ch/1.0.0/ch.bafu.vec25-gewaessernetz_2000/default/current/3857/{z}/{x}/{y}.png";
    const swisstopo_boundary_url = "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissboundaries3d-land-flaeche.fill/default/current/3857/{z}/{x}/{y}.png";
    const swisstopo_cantons_url = "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissboundaries3d-kanton-flaeche.fill/default/current/3857/{z}/{x}/{y}.png";

    const m = L.map(domId, {
        center: [46.8182, 8.2275],
        zoom: 9, minZoom: 7, maxZoom: 15,
        zoomControl: false, preferCanvas: true
    });

    m.createPane('reliefPane'); m.getPane('reliefPane').style.zIndex = '200'; m.getPane('reliefPane').style.opacity = baseMapOpacity;
    m.createPane('waterPane'); m.getPane('waterPane').style.zIndex = '250'; m.getPane('waterPane').style.opacity = baseMapOpacity;
    m.createPane('boundaryPane'); m.getPane('boundaryPane').style.zIndex = '280'; m.getPane('boundaryPane').style.opacity = '1.0'; m.getPane('boundaryPane').style.pointerEvents = 'none';

    m.createPane('contourPane1'); m.getPane('contourPane1').style.opacity = layer1Opacity; m.getPane('contourPane1').style.zIndex = '400';
    m.createPane('contourPane2'); m.getPane('contourPane2').style.opacity = layer2Opacity; m.getPane('contourPane2').style.zIndex = '450';

    m.createPane('arrowPane');
    m.getPane('arrowPane').style.zIndex = '500';
    m.getPane('arrowPane').style.pointerEvents = 'none';

    m.createPane('cityPane');
    m.getPane('cityPane').style.zIndex = '520';
    m.getPane('cityPane').style.pointerEvents = 'none';
    m.getPane('cityPane').style.transition = 'opacity 0.1s ease';

    const arrowCanvas = document.createElement('canvas');
    arrowCanvas.style.cssText = 'position:absolute; left:0; top:0; pointer-events:none; opacity:1; transition:opacity 0.12s ease;';
    m.getPane('arrowPane').appendChild(arrowCanvas);
    const arrowCtx = arrowCanvas.getContext('2d');

    const relief = L.tileLayer(swisstopo_relief_url, {
        pane: 'reliefPane', attribution: '&copy; swisstopo | Wetter: &copy; MeteoSchweiz, DWD, ECMWF & Météo-France',
        maxZoom: 15, maxNativeZoom: 14
    }).addTo(m);

    L.tileLayer(swisstopo_lakes_url, { pane: 'waterPane', maxZoom: 15, maxNativeZoom: 14, opacity: 0.85 }).addTo(m);
    const rivers = L.tileLayer(swisstopo_rivers_url, { pane: 'waterPane', maxZoom: 15, maxNativeZoom: 14, opacity: 0.35 }).addTo(m);
    L.tileLayer(swisstopo_boundary_url, { pane: 'boundaryPane', className: 'boundary-national', maxZoom: 15, maxNativeZoom: 14 }).addTo(m);

    const cantons = L.layerGroup();
    const canvasRendererBoundary = L.canvas({ pane: 'boundaryPane', padding: 0.1 });
    fetch("https://cdn.jsdelivr.net/gh/empet/Datasets@master/swiss-cantons.geojson")
        .then(res => res.json())
        .then(geojson => {
            L.geoJSON(geojson, { pane: 'boundaryPane', renderer: canvasRendererBoundary, interactive: false, style: { color: "#111111", weight: 0.7, opacity: 1.0, fill: false } }).addTo(cantons);
        })
        .catch(() => {
            L.tileLayer(swisstopo_cantons_url, { pane: 'boundaryPane', className: 'boundary-cantonal', maxZoom: 15, maxNativeZoom: 14 }).addTo(cantons);
        });

    const cityGroup = L.layerGroup([], { pane: 'cityPane' }).addTo(m);

    m.on('zoomstart', () => {
        setOverlaysVisible(false);
        if (mapSafetyTimer) clearTimeout(mapSafetyTimer);
        mapSafetyTimer = setTimeout(() => setOverlaysVisible(true), 1200);
    });
    m.on('move', () => { syncMap(domId === 'mapLeft' ? mapLeft : mapRight, domId === 'mapLeft' ? mapRight : mapLeft); });
    m.on('moveend', scheduleMapUpdates);
    m.on('zoomend', scheduleMapUpdates);
    m.on('click', closeAllPopups);

    return { map: m, relief, rivers, cantons, cities: cityGroup, arrowCanvas, arrowCtx };
}

// ================= APP INITIALISIERUNG =================
async function init() {
    try {
        const leftInit = initMapInstance('mapLeft');
        mapLeft = leftInit.map;
        baseReliefLayerLeft = leftInit.relief;
        riversLayerLeft = leftInit.rivers;
        cantonalBoundaryLayerLeft = leftInit.cantons;
        cityLayerGroupLeft = leftInit.cities;
        modelsState.left.arrowCanvas = leftInit.arrowCanvas;
        modelsState.left.arrowCtx = leftInit.arrowCtx;

        const rightInit = initMapInstance('mapRight');
        mapRight = rightInit.map;
        baseReliefLayerRight = rightInit.relief;
        riversLayerRight = rightInit.rivers;
        cantonalBoundaryLayerRight = rightInit.cantons;
        cityLayerGroupRight = rightInit.cities;
        modelsState.right.arrowCanvas = rightInit.arrowCanvas;
        modelsState.right.arrowCtx = rightInit.arrowCtx;

        modelsState.left.canvasRenderer1 = L.canvas({ pane: 'contourPane1', padding: 0.1 });
        modelsState.left.canvasRenderer2 = L.canvas({ pane: 'contourPane2', padding: 0.1 });
        modelsState.right.canvasRenderer1 = L.canvas({ pane: 'contourPane1', padding: 0.1 });
        modelsState.right.canvasRenderer2 = L.canvas({ pane: 'contourPane2', padding: 0.1 });

        const slider = document.getElementById("timeSlider");
        slider.addEventListener("input", function() {
            const targetHour = parseInt(this.value);
            const curDateKey = getDateKeyForStep(currentStepIdx);
            const steps = dayTimesteps[curDateKey] || [];
            if (steps.length === 0) return;

            const times = modelsState.left.times;
            let bestIdx = steps[0], minDiff = 999;
            steps.forEach(idx => {
                const diff = Math.abs(parseInt(times[idx].local_str.split(" ")[1].split(":")[0]) - targetHour);
                if (diff < minDiff) { minDiff = diff; bestIdx = idx; }
            });
            currentStepIdx = bestIdx;
            updateForecast();
        });

        document.addEventListener('keydown', event => {
            if (event.key === "ArrowLeft") navLeft();
            else if (event.key === "ArrowRight") navRight();
            else if (event.key === "ArrowUp") { event.preventDefault(); navUp(); }
            else if (event.key === "ArrowDown") { event.preventDefault(); navDown(); }
        });

        window.onresize = () => {
            if (resizeDebounceTimer) clearTimeout(resizeDebounceTimer);
            resizeDebounceTimer = setTimeout(() => {
                if (mapLeft) mapLeft.invalidateSize();
                if (mapRight) mapRight.invalidateSize();
                scheduleMapUpdates();
            }, 100);
        };

        updateNavModeButton();
        await Promise.all(ALL_MODELS.map(m => fetchAvailableRuns(m)));
        if (window.innerWidth <= 768) toggleMobileModelPanel(false);

        await Promise.all([
            loadModelAndRun('left', 'icon-ch1', null),
            loadModelAndRun('right', 'ecmwf', null)
        ]);
        updateCityLabels();
    } catch (err) {
        console.error("Fehler bei init():", err);
    }
}

async function updateForecast() {
    const sidesToUpdate = isSplitActive ? ['left', 'right'] : ['left'];
    const times = modelsState.left.times;
    if (!times || times.length === 0) return;

    currentStepIdx = Math.max(0, Math.min(times.length - 1, currentStepIdx));
    const curDateKey = getDateKeyForStep(currentStepIdx);
    const currentHour = parseInt(times[currentStepIdx].local_str.split(" ")[1].split(":")[0]);

    const slider = document.getElementById("timeSlider");
    slider.min = 0; slider.max = 23; slider.value = currentHour;

    const loadingIndicator = document.getElementById("loadingIndicator");
    if (loadingIndicator) loadingIndicator.style.display = "block";

    try {
        for (const side of sidesToUpdate) {
            const st = modelsState[side];
            if (!st.config) continue;
            sanitizeMemberIndex(side);
            const stepForSide = getStepIdxForSide(side);

            await ensureDataLoaded(side, layer1Var, st.currentMemberIdx, stepForSide);
            if (layer2Var) {
                const vCfg2 = st.config.variables_config && st.config.variables_config[layer2Var] || {};
                const m2 = vCfg2.has_ensemble ? st.currentMemberIdx : 0;
                await ensureDataLoaded(side, layer2Var, m2, stepForSide);
            }
        }
    } catch (err) {
        console.error("Fehler beim Laden von Forecast-Daten:", err);
    } finally {
        if (loadingIndicator) loadingIndicator.style.display = "none";
    }

    const tInfo = times[currentStepIdx];
    const [d, m] = tInfo.local_str.split(" ")[0].split(".");
    const hourMin = tInfo.local_str.split(" ")[1].substring(0, 5);
    document.getElementById("currentStepLabel").innerText = `${d}.${m} ${hourMin} LT`;

    const cfgCurrent = modelsState.left.config;
    const refParts = cfgCurrent ? cfgCurrent.ref_time_utc.split(" ") : ["01.01.", "00:00"];
    const [rd, rm] = refParts[0].split(".");
    const refHour = refParts[1].split(":")[0];

    const labelEl = document.getElementById("modelRunLabel");
    if (isSplitActive) {
        labelEl.innerText = `🕒${rd}.${rm} ${refHour}Z | L: ${getModelShortLabel(modelsState.left.currentModel)} | R: ${getModelShortLabel(modelsState.right.currentModel)}`;
    } else {
        labelEl.innerText = `🕒${rd}.${rm} ${refHour}Z ${getModelShortLabel(modelsState.left.currentModel)}`;
    }

    uniqueDays.forEach((dayObj, index) => {
        const btn = document.getElementById("day-btn-" + index);
        if (btn) btn.classList.toggle("active", dayObj.dateKey === curDateKey);
    });

    ['left', 'right'].forEach(side => {
        const stateSide = getActiveStateSide(side);
        const st = modelsState[stateSide];
        const lbl = document.getElementById(side === 'left' ? "lblMemberBtnLeft" : "lblMemberBtnRight");
        if (lbl && st && st.config && st.config.member_names) {
            lbl.innerText = `${st.config.member_names[st.currentMemberIdx] || "Hauptlauf"} ▾`;
        }
        if (st && st.config && st.config.member_names) {
            for (let i = 0; i < st.config.member_names.length; i++) {
                const btn = document.getElementById((side === 'left' ? "left-" : "right-") + "member-btn-" + i);
                if (btn) btn.classList.toggle("active", i === st.currentMemberIdx);
            }
        }
    });

    updateEnsembleToggleState();
    updateLegend();

    renderContours('left');
    drawVisibleArrows('left');
    if (isSplitActive) {
        renderContours('right');
        drawVisibleArrows('right');
    }
    updateCityLabels();
}

function renderContours(side) {
    const st = modelsState[side];
    const targetMap = (side === 'left') ? mapLeft : mapRight;
    if (!st.config || !targetMap) return;

    if (st.contourLayer1) targetMap.removeLayer(st.contourLayer1);
    const stepForSide = getStepIdxForSide(side);
    const key1 = `${st.currentModel}_${st.currentRunId}_${layer1Var}_${st.currentMemberIdx}_${stepForSide}`;

    if (cacheContours[key1]) {
        st.contourLayer1 = L.geoJson(cacheContours[key1], {
            pane: 'contourPane1', renderer: st.canvasRenderer1, smoothFactor: 1.0,
            style: feature => {
                const fill = feature.properties.fill;
                const isTrans = (fill === 'transparent' || fill === '#ffffff00' || (fill.length === 9 && fill.endsWith('00')));
                return (layer1Mode === 'line')
                    ? { fill: false, color: isTrans ? 'transparent' : fill, weight: 1.8, opacity: 1.0 }
                    : { fillColor: fill, color: isTrans ? 'transparent' : fill, weight: 0.5, fillOpacity: isTrans ? 0 : 1.0 };
            }
        }).addTo(targetMap);
    }

    if (st.contourLayer2) { targetMap.removeLayer(st.contourLayer2); st.contourLayer2 = null; }
    if (layer2Var) {
        const vCfg2 = st.config.variables_config[layer2Var] || {};
        const m2 = vCfg2.has_ensemble ? st.currentMemberIdx : 0;
        const key2 = `${st.currentModel}_${st.currentRunId}_${layer2Var}_${m2}_${stepForSide}`;

        if (cacheContours[key2]) {
            st.contourLayer2 = L.geoJson(cacheContours[key2], {
                pane: 'contourPane2', renderer: st.canvasRenderer2, smoothFactor: 1.0,
                style: feature => {
                    const fill = feature.properties.fill;
                    const isTrans = (fill === 'transparent' || fill === '#ffffff00' || (fill.length === 9 && fill.endsWith('00')));
                    return (layer2Mode === 'line')
                        ? { fill: false, color: isTrans ? 'transparent' : fill, weight: 2.2, opacity: 1.0 }
                        : { fillColor: fill, color: isTrans ? 'transparent' : fill, weight: 0.5, fillOpacity: isTrans ? 0 : 1.0 };
                }
            }).addTo(targetMap);
        }
    }
}

function drawVisibleArrows(side) {
    const st = modelsState[side];
    const targetMap = (side === 'left') ? mapLeft : mapRight;
    if (!targetMap || !st.config || !st.arrowCanvas || !st.arrowCtx) return;

    const size = targetMap.getSize();
    if (!size || size.x <= 0 || size.y <= 0) return;

    const canvas = st.arrowCanvas;
    const ctx = st.arrowCtx;
    const dpr = window.devicePixelRatio || 1;
    const pad = 160;
    const topLeft = targetMap.containerPointToLayerPoint([-pad, -pad]);

    L.DomUtil.setPosition(canvas, topLeft);

    const totalW = size.x + pad * 2;
    const totalH = size.y + pad * 2;
    const targetW = Math.round(totalW * dpr);
    const targetH = Math.round(totalH * dpr);

    if (canvas.width !== targetW || canvas.height !== targetH) {
        canvas.width = targetW;
        canvas.height = targetH;
        canvas.style.width = totalW + 'px';
        canvas.style.height = totalH + 'px';
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    let arrowVar = null, arrowMember = 0;
    const vCfg1 = st.config.variables_config && st.config.variables_config[layer1Var];
    const hasMultiple = modelHasEnsembleForCurrentVar(side);
    const iqrIdx = (st.config && st.config.member_names && st.config.member_names.length > 1) ? (st.config.member_names.length - 1) : 0;

    if (vCfg1 && vCfg1.has_arrows && (!hasMultiple || st.currentMemberIdx < iqrIdx - 5)) {
        arrowVar = layer1Var;
        arrowMember = st.currentMemberIdx;
    } else if (layer2Var) {
        const vCfg2 = st.config.variables_config && st.config.variables_config[layer2Var];
        if (vCfg2 && vCfg2.has_arrows) {
            arrowVar = layer2Var;
            arrowMember = vCfg2.has_ensemble ? st.currentMemberIdx : 0;
        }
    }

    if (!arrowVar) return;

    const stepForSide = getStepIdxForSide(side);
    const gridData = cacheGrid[`${st.currentModel}_${st.currentRunId}_${arrowVar}_${arrowMember}_${stepForSide}`];
    if (!gridData || !gridData.s || !gridData.d) return;

    const bounds = targetMap.getBounds();
    const zoom = targetMap.getZoom();

    let step = 16;
    if (zoom >= 9 && zoom <= 10) step = 7;
    else if (zoom === 11) step = 4;
    else if (zoom === 12) step = 3;
    else if (zoom === 13) step = 2;
    else if (zoom >= 14) step = 1;

    if (st.config.nx <= 200) step = Math.max(1, Math.round(step / 2));

    const { s: speeds, d: dirs_half } = gridData;
    const { nx, ny, xmin, xmax, ymin, ymax } = st.config;

    const bNorth = bounds.getNorth() + 0.15, bSouth = bounds.getSouth() - 0.15;
    const bWest = bounds.getWest() - 0.20, bEast = bounds.getEast() + 0.20;

    let rMin = Math.max(0, Math.floor((bSouth - ymin) / (ymax - ymin) * (ny - 1)));
    const rMax = Math.min(ny - 1, Math.ceil((bNorth - ymin) / (ymax - ymin) * (ny - 1)));
    let cMin = Math.max(0, Math.floor((bWest - xmin) / (xmax - xmin) * (nx - 1)));
    const cMax = Math.min(nx - 1, Math.ceil((bEast - xmin) / (xmax - xmin) * (nx - 1)));

    rMin = Math.floor(rMin / step) * step;
    cMin = Math.floor(cMin / step) * step;

    for (let r = rMin; r <= rMax; r += step) {
        const lat = ymin + r * (ymax - ymin) / (ny - 1);
        const rowOffset = r * nx;

        for (let c = cMin; c <= cMax; c += step) {
            const i = rowOffset + c;
            const sVal = speeds[i];
            if (sVal < 25) continue;

            const dirVal = dirs_half[i];
            if (dirVal === 255) continue;

            const lon = xmin + c * (xmax - xmin) / (nx - 1);
            const layerPt = targetMap.latLngToLayerPoint(L.latLng(lat, lon));
            const px = (layerPt.x - topLeft.x) * dpr;
            const py = (layerPt.y - topLeft.y) * dpr;

            if (px < -40 || px > canvas.width + 40 || py < -40 || py > canvas.height + 40) continue;

            const speed = sVal / 10.0;
            const dir = dirVal * 2.0;
            const arrow_w = Math.min(20, Math.max(4.5, 3.2 + Math.pow(speed, 0.58) * 1.2));
            const scale = (arrow_w / 15.0) * dpr;

            ctx.save();
            ctx.translate(px, py);
            ctx.rotate(dir * Math.PI / 180.0);
            ctx.scale(scale, scale);

            ctx.beginPath();
            ctx.moveTo(0, -10.5);
            ctx.lineTo(4.2, -3.0);
            ctx.lineTo(0.9, -3.0);
            ctx.lineTo(0.9, 11.0);
            ctx.lineTo(-0.9, 11.0);
            ctx.lineTo(-0.9, -3.0);
            ctx.lineTo(-4.2, -3.0);
            ctx.closePath();

            ctx.fillStyle = '#111111';
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 0.55;
            ctx.stroke();
            ctx.restore();
        }
    }
}

window.onload = init;
