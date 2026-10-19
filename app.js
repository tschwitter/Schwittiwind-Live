var mapLeft, mapRight;
var isSplitActive = false;
var isSyncingMaps = false;
var isLegendOpen = false;
var syncRafId = null;

var ALL_MODELS = ["icon-ch1", "icon-ch2", "arome", "icon-d2"];
var isMobileModelExpanded = false;

var modelsState = {
    left: {
        currentModel: "icon-ch1",
        currentRunId: null,
        currentMemberIdx: 0,
        config: null,
        times: null,
        contourLayer1: null,
        contourLayer2: null,
        arrowCanvas: null,
        arrowCtx: null,
        canvasRenderer1: null,
        canvasRenderer2: null
    },
    right: {
        currentModel: "icon-d2",
        currentRunId: null,
        currentMemberIdx: 0,
        config: null,
        times: null,
        contourLayer1: null,
        contourLayer2: null,
        arrowCanvas: null,
        arrowCtx: null,
        canvasRenderer1: null,
        canvasRenderer2: null
    }
};

var availableRuns = { "icon-ch1": [], "icon-ch2": [], "arome": [], "icon-d2": [] };
var selectedRuns = {
    left: { "icon-ch1": null, "icon-ch2": null, "arome": null, "icon-d2": null },
    right: { "icon-ch1": null, "icon-ch2": null, "arome": null, "icon-d2": null }
};

var verticalNavMode = 'member';

var baseMapOpacity = 0.80;
var baseMapStyle = 'relief';

var layer1Var = "wind";
var layer2Var = null;
var layer1Mode = 'fill';
var layer2Mode = 'fill';
var layer1Opacity = 0.60;
var layer2Opacity = 0.60;

var isWetterOpen = false;
var isHoehenOpen = false;
var isEnsembleOpen = (localStorage.getItem("icon_ensemble_open") === "true");

var currentStepIdx = 0;

var baseReliefLayerLeft, baseReliefLayerRight;
var riversLayerLeft, riversLayerRight;
var cantonalBoundaryLayerLeft, cantonalBoundaryLayerRight;
var cityLayerGroupLeft, cityLayerGroupRight;

var cacheGrid = {};
var cacheContours = {};

var uniqueDays = [];
var dayTimesteps = {};
var weekdays = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

var mapUpdateTimer = null;
var mapSafetyTimer = null;

var CITIES = [
    { name: "Zürich", lat: 47.3769, lon: 8.5417, minZoom: 7 },
    { name: "Bern", lat: 46.9480, lon: 7.4474, minZoom: 7 },
    { name: "Basel", lat: 47.5596, lon: 7.5886, minZoom: 7 },
    { name: "Genève", lat: 46.2044, lon: 6.1432, minZoom: 7 },
    { name: "Lausanne", lat: 46.5197, lon: 6.6323, minZoom: 7 },
    { name: "Luzern", lat: 47.0502, lon: 8.3093, minZoom: 7 },
    { name: "St. Gallen", lat: 47.4245, lon: 9.3767, minZoom: 7 },
    { name: "Lugano", lat: 46.0037, lon: 8.9511, minZoom: 7 },
    { name: "Chur", lat: 46.8508, lon: 9.5320, minZoom: 7 },
    { name: "Sion", lat: 46.2331, lon: 7.3606, minZoom: 7 },
    { name: "Winterthur", lat: 47.4999, lon: 8.7241, minZoom: 9 },
    { name: "Biel/Bienne", lat: 47.1368, lon: 7.2468, minZoom: 9 },
    { name: "Thun", lat: 46.7580, lon: 7.6280, minZoom: 9 },
    { name: "Bellinzona", lat: 46.1928, lon: 9.0170, minZoom: 9 },
    { name: "Fribourg", lat: 46.8065, lon: 7.1620, minZoom: 9 },
    { name: "Neuchâtel", lat: 46.9896, lon: 6.9293, minZoom: 9 },
    { name: "Schaffhausen", lat: 47.6959, lon: 8.6380, minZoom: 9 },
    { name: "Aarau", lat: 47.3925, lon: 8.0442, minZoom: 9 },
    { name: "Olten", lat: 47.3522, lon: 7.9077, minZoom: 9 },
    { name: "Brig", lat: 46.3167, lon: 7.9878, minZoom: 9 },
    { name: "Davos", lat: 46.8027, lon: 9.8360, minZoom: 9 },
    { name: "St. Moritz", lat: 46.4908, lon: 9.8355, minZoom: 9 },
    { name: "Altdorf", lat: 46.8804, lon: 8.6444, minZoom: 9 },
    { name: "Schwyz", lat: 47.0207, lon: 8.6530, minZoom: 9 },
    { name: "Sarnen", lat: 46.8961, lon: 8.2458, minZoom: 9 },
    { name: "Stans", lat: 46.9575, lon: 8.3660, minZoom: 9 },
    { name: "Appenzell", lat: 47.3312, lon: 9.4098, minZoom: 9 },
    { name: "Delémont", lat: 47.3653, lon: 7.3444, minZoom: 9 },
    { name: "Frauenfeld", lat: 47.5583, lon: 8.8986, minZoom: 9 },
    { name: "Liestal", lat: 47.4844, lon: 7.7348, minZoom: 9 },
    { name: "Interlaken", lat: 46.6863, lon: 7.8632, minZoom: 10 },
    { name: "Spiez", lat: 46.6888, lon: 7.6806, minZoom: 10 },
    { name: "Zermatt", lat: 45.9765, lon: 7.7491, minZoom: 10 },
    { name: "Andermatt", lat: 46.6337, lon: 8.5947, minZoom: 10 },
    { name: "Locarno", lat: 46.1711, lon: 8.7995, minZoom: 10 },
    { name: "Martigny", lat: 46.1037, lon: 7.0734, minZoom: 10 },
    { name: "Montreux", lat: 46.4312, lon: 6.9107, minZoom: 10 },
    { name: "Vevey", lat: 46.4628, lon: 6.8432, minZoom: 10 },
    { name: "Yverdon", lat: 46.7785, lon: 6.6412, minZoom: 10 },
    { name: "La Chaux-de-Fonds", lat: 47.1035, lon: 6.8328, minZoom: 10 },
    { name: "Bulle", lat: 46.6174, lon: 7.0569, minZoom: 10 },
    { name: "Rapperswil", lat: 47.2267, lon: 8.8184, minZoom: 10 },
    { name: "Zug", lat: 47.1662, lon: 8.5155, minZoom: 10 },
    { name: "Baden", lat: 47.4737, lon: 8.3087, minZoom: 10 },
    { name: "Lenzburg", lat: 47.3881, lon: 8.1809, minZoom: 10 },
    { name: "Burgdorf", lat: 47.0573, lon: 7.6258, minZoom: 10 },
    { name: "Langenthal", lat: 47.2132, lon: 7.7915, minZoom: 10 },
    { name: "Solothurn", lat: 47.2088, lon: 7.5370, minZoom: 10 },
    { name: "Glarus", lat: 47.0406, lon: 9.0678, minZoom: 10 }
];

// In Single-Ansicht steuern die rechten Controls immer modelsState.left
function getActiveStateSide(domSide) {
    return isSplitActive ? domSide : 'left';
}

// Prüft absolut verlässlich, ob für das Modell und die aktuelle Variable ein Ensemble existiert
function modelHasEnsembleForCurrentVar(stateSide) {
    var st = modelsState[stateSide];
    if (!st || !st.config) return false;
    var vCfg = st.config.variables_config && st.config.variables_config[layer1Var];
    var hasEnsVar = vCfg ? (vCfg.has_ensemble === true) : false;
    var hasMultiple = st.config.member_names && st.config.member_names.length > 1;
    return Boolean(hasEnsVar && hasMultiple);
}

function setOverlaysVisible(visible) {
    var op = visible ? "1" : "0";
    [ { map: mapLeft, st: modelsState.left }, { map: mapRight, st: modelsState.right } ].forEach(item => {
        if (!item.map) return;
        var cp = item.map.getPane('cityPane');
        if (cp) cp.style.opacity = op;
        if (item.st && item.st.arrowCanvas) item.st.arrowCanvas.style.opacity = op;
    });
}

function scheduleMapUpdates() {
    if (mapSafetyTimer) clearTimeout(mapSafetyTimer);
    if (mapUpdateTimer) clearTimeout(mapUpdateTimer);
    
    mapUpdateTimer = setTimeout(function() {
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
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }
    isSplitActive = !isSplitActive;

    var wrapper = document.getElementById("mapsWrapper");
    var btn = document.getElementById("splitBtn");
    document.body.classList.toggle("split-active", isSplitActive);
    
    if (btn) {
        btn.classList.toggle("active", isSplitActive);
        btn.blur();
    }
    if (document.activeElement && document.activeElement.blur) {
        document.activeElement.blur();
    }

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
    var box = document.getElementById("legendBox");
    var btn = document.getElementById("btnToggleLegend");
    if (box) box.style.display = isLegendOpen ? "flex" : "none";
    if (btn) btn.classList.toggle("active", isLegendOpen);
}

// Mobile Aufklappen / Zuklappen
function toggleMobileModelPanel(forceState) {
    if (typeof forceState === "boolean") {
        isMobileModelExpanded = forceState;
    } else {
        isMobileModelExpanded = !isMobileModelExpanded;
    }

    document.body.classList.toggle("mobile-models-expanded", isMobileModelExpanded);
    var elR = document.getElementById("modelSelectRight");
    var elL = document.getElementById("modelSelectLeft");

    if (elR) elR.classList.toggle("mobile-collapsed", !isMobileModelExpanded);
    if (elL) elL.classList.toggle("mobile-collapsed", !isMobileModelExpanded);
}

// Unabhängiges Aufklappen des Member-Panels
function toggleMemberPanel(side) {
    var p = document.getElementById(side === 'left' ? "memberPanelLeft" : "memberPanelRight");
    var b = document.getElementById(side === 'left' ? "btnToggleMemberLeft" : "btnToggleMemberRight");
    if (!p) return;
    var isOpen = (p.style.display === "flex");
    p.style.display = isOpen ? "none" : "flex";
    if (b) b.classList.toggle("active", !isOpen);
}

function toggleEnsembleAccordionLocal(side) {
    var cont = document.getElementById(side === 'left' ? "ensembleContainerLeft" : "ensembleContainerRight");
    var btn = document.getElementById(side === 'left' ? "btnToggleEnsembleLeft" : "btnToggleEnsembleRight");
    if (!cont) return;
    var isOpen = (cont.style.display !== "none");
    cont.style.display = isOpen ? "none" : "block";
    if (btn) btn.classList.toggle("open", !isOpen);
}

function updateCityLabels() {
    [ { map: mapLeft, group: cityLayerGroupLeft }, { map: mapRight, group: cityLayerGroupRight } ].forEach(item => {
        if (!item.map || !item.group) return;
        item.group.clearLayers();
        var curZoom = item.map.getZoom();
        var bounds = item.map.getBounds();

        CITIES.forEach(city => {
            if (curZoom >= city.minZoom) {
                var latlng = L.latLng(city.lat, city.lon);
                if (bounds.contains(latlng)) {
                    var html = `<div class="city-label-container"><div class="city-dot"></div><span class="city-name">${city.name}</span></div>`;
                    var icon = L.divIcon({ html: html, className: 'city-div-icon', iconSize: [0, 0], iconAnchor: [0, 0] });
                    L.marker(latlng, { icon: icon, pane: 'cityPane', interactive: false }).addTo(item.group);
                }
            }
        });
    });
}

function parseLocalStr(str) {
    if (!str) return new Date();
    var parts = str.split(" ");
    var dateParts = parts[0].split(".");
    var timeParts = parts[1].split(":");
    return new Date(
        parseInt(dateParts[2]),
        parseInt(dateParts[1]) - 1,
        parseInt(dateParts[0]),
        parseInt(timeParts[0]),
        parseInt(timeParts[1] || 0)
    );
}

function getDayNameForStep(stepIdx) {
    var t = modelsState.left.times;
    if (!t || !t[stepIdx]) return "";
    var parts = t[stepIdx].local_str.split(" ")[0].split(".");
    var dateObj = new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
    return weekdays[dateObj.getDay()];
}

function setPopupsDimmed(dimmed) {
    var l = document.getElementById("legendBox");
    if (l) l.classList.toggle("panel-dimmed", dimmed);
}

function closeAllPopups() {
    ['left', 'right'].forEach(side => {
        ALL_MODELS.forEach(m => {
            var el = document.getElementById(`runDropdown-${side}-${m}`);
            if (el) el.style.display = "none";
        });
    });

    var pLeft = document.getElementById("memberPanelLeft");
    var pRight = document.getElementById("memberPanelRight");
    var bLeft = document.getElementById("btnToggleMemberLeft");
    var bRight = document.getElementById("btnToggleMemberRight");
    if (pLeft) pLeft.style.display = "none";
    if (pRight) pRight.style.display = "none";
    if (bLeft) bLeft.classList.remove("active");
    if (bRight) bRight.classList.remove("active");

    var l2 = document.getElementById("layer2Dropdown");
    if (l2) l2.style.display = "none";
    var sp = document.getElementById("settingsPopup");
    if (sp) sp.style.display = "none";
    setPopupsDimmed(false);
}

function setBaseMapOpacity(val) {
    var op = val / 100.0;
    baseMapOpacity = op;
    var lbl = document.getElementById("opacityLabelBase");
    var sld = document.getElementById("opacitySliderBase");
    if (lbl) lbl.innerText = val + "%";
    if (sld) sld.value = val;
    [mapLeft, mapRight].forEach(m => {
        if (m) {
            if (m.getPane('reliefPane')) m.getPane('reliefPane').style.opacity = op;
            if (m.getPane('waterPane')) m.getPane('waterPane').style.opacity = op;
        }
    });
}

function setBaseMapStyle(style) {
    baseMapStyle = style;
    document.getElementById("btnBaseRelief").classList.toggle("active", style === 'relief');
    document.getElementById("btnBaseSimple").classList.toggle("active", style === 'simple');

    [ { map: mapLeft, relief: baseReliefLayerLeft, rivers: riversLayerLeft, cantons: cantonalBoundaryLayerLeft },
      { map: mapRight, relief: baseReliefLayerRight, rivers: riversLayerRight, cantons: cantonalBoundaryLayerRight }
    ].forEach(c => {
        if (!c.map) return;
        var container = c.map.getContainer();
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
    var btn = document.getElementById("navModeBtn");
    if (!btn) return;
    if (verticalNavMode === 'run') {
        btn.innerText = "Lauf";
        btn.classList.add("mode-run");
    } else {
        btn.innerText = "Mbr";
        btn.classList.remove("mode-run");
    }
}

function navRun(dir) {
    var side = isSplitActive ? 'right' : 'left';
    var st = modelsState[side];
    var runs = availableRuns[st.currentModel] || [];
    if (runs.length <= 1) return;
    var currentIdx = runs.findIndex(r => r.id === st.currentRunId);
    if (currentIdx === -1) currentIdx = 0;

    var newIdx = currentIdx + dir;
    if (newIdx >= 0 && newIdx < runs.length) {
        selectRun(side, st.currentModel, runs[newIdx].id);
    }
}

async function handleModelButtonClick(modelName, side) {
    var stateSide = getActiveStateSide(side);
    var st = modelsState[stateSide];

    if (st.currentModel !== modelName) {
        st.currentModel = modelName;
        var runs = availableRuns[modelName] || [];
        var runId = selectedRuns[stateSide][modelName] || (runs.length > 0 ? runs[0].id : null);
        await loadModelAndRun(stateSide, modelName, runId);
    } else {
        toggleRunDropdown(side, modelName);
    }
}

async function fetchAvailableRuns(modelName) {
    try {
        const res = await fetch(`data/${modelName}/runs.json?t=${Date.now()}`);
        if (res.ok) {
            availableRuns[modelName] = await res.json();
        }
    } catch (e) {
        console.warn("Konnte runs.json nicht laden für " + modelName, e);
    }
    updateModelButtonLabels();
}

function getModelShortLabel(m) {
    if (m === "icon-ch1") return "CH1";
    if (m === "icon-ch2") return "CH2";
    if (m === "icon-d2") return "D2";
    return "AROME";
}

function updateModelButtonLabels() {
    ['left', 'right'].forEach(side => {
        var stateSide = getActiveStateSide(side);
        var st = modelsState[stateSide];

        var tabLabel = document.getElementById(side === 'left' ? "tabModelLabelLeft" : "tabModelLabelRight");
        if (tabLabel) {
            tabLabel.innerText = getModelShortLabel(st.currentModel);
        }

        ALL_MODELS.forEach(m => {
            var btn = document.getElementById(`btnModel-${side}-${m}`);
            if (!btn) return;
            var runs = availableRuns[m] || [];
            var activeRun = (st.currentModel === m) ? st.currentRunId : (selectedRuns[stateSide][m] || (runs[0] ? runs[0].id : null));
            var activeObj = runs.find(r => r.id === activeRun) || runs[0];
            var modName = getModelShortLabel(m);
            var timeTxt = activeObj ? activeObj.label : "--";
            btn.innerHTML = `<span class="model-title">${modName} ▾</span><span class="model-time">${timeTxt}</span>`;
            btn.classList.toggle("active", st.currentModel === m);
        });
    });
}

function toggleRunDropdown(side, modelName) {
    var stateSide = getActiveStateSide(side);
    var elId = `runDropdown-${side}-${modelName}`;
    var el = document.getElementById(elId);
    if (!el) return;
    var isAlreadyOpen = (el.style.display === "flex");
    if (isAlreadyOpen) {
        el.style.display = "none";
        return;
    }

    var runs = availableRuns[modelName] || [];
    el.innerHTML = "";

    if (runs.length === 0) {
        el.innerHTML = `<div style="font-size:11px; padding:4px 8px; color:#aaa;">Keine alten Läufe</div>`;
    } else {
        runs.forEach((r) => {
            var item = document.createElement("button");
            item.className = "run-item" + (r.id === modelsState[stateSide].currentRunId ? " active" : "");
            item.innerHTML = `<span>${r.label}</span>`;
            item.onclick = function(e) {
                e.stopPropagation();
                el.style.display = "none";
                selectRun(stateSide, modelName, r.id);
            };
            el.appendChild(item);
        });
    }

    var header = document.getElementById(`modelSelect${side === 'left' ? 'Left' : 'Right'}`);
    var rect = header.getBoundingClientRect();
    el.style.top = (rect.bottom + 5) + "px";
    if (side === 'left') {
        el.style.left = rect.left + "px";
        el.style.right = "auto";
    } else {
        el.style.right = (window.innerWidth - rect.right) + "px";
        el.style.left = "auto";
    }
    el.style.display = "flex";
}

async function selectRun(side, modelName, runId) {
    var stateSide = getActiveStateSide(side);
    modelsState[stateSide].currentModel = modelName;
    modelsState[stateSide].currentRunId = runId;
    selectedRuns[stateSide][modelName] = runId;
    await loadModelAndRun(stateSide, modelName, runId);
}

async function loadModelAndRun(side, modelName, runId) {
    var st = modelsState[side];
    st.currentModel = modelName;

    if (!availableRuns[modelName] || availableRuns[modelName].length === 0) {
        await fetchAvailableRuns(modelName);
    }
    var runs = availableRuns[modelName] || [];
    if (!runId && runs.length > 0) runId = runs[0].id;
    st.currentRunId = runId;
    selectedRuns[side][modelName] = runId;

    updateModelButtonLabels();

    const cacheBuster = Date.now();
    const runPath = runId ? `data/${modelName}/${runId}` : `data/${modelName}`;
    
    try {
        const configRes = await fetch(`${runPath}/config.json?t=${cacheBuster}`);
        if (!configRes.ok) throw new Error("Konnte config.json nicht laden: " + configRes.status);
        st.config = await configRes.json();

        const timesRes = await fetch(`${runPath}/times.json?t=${cacheBuster}`);
        if (!timesRes.ok) throw new Error("Konnte times.json nicht laden: " + timesRes.status);
        st.times = await timesRes.json();
    } catch (e) {
        console.error("Fehler beim Laden von " + modelName, e);
        return;
    }

    // Sicherstellen, dass kein ungültiger Member aktiv bleibt
    if (!modelHasEnsembleForCurrentVar(side)) {
        st.currentMemberIdx = 0;
    }

    initNavigationBars();
    initLayer2Dropdown();
    initDayButtons();
    initMemberPanelsAll();

    await updateForecast();
}

function updateEnsembleToggleState() {
    ['left', 'right'].forEach(side => {
        var stateSide = getActiveStateSide(side);
        var btn = document.getElementById(side === 'left' ? "btnToggleEnsembleLeft" : "btnToggleEnsembleRight");
        var cfg = modelsState[stateSide].config;
        if (!btn || !cfg || !cfg.member_names) return;
        var statOffset = cfg.member_names.length - 6;
        var isMemberActive = (modelsState[stateSide].currentMemberIdx >= 1 && modelsState[stateSide].currentMemberIdx < statOffset);
        btn.classList.toggle("active-indicator", isMemberActive && !isEnsembleOpen);
    });
}

function toggleWetterMenu() {
    isWetterOpen = !isWetterOpen;
    document.getElementById("wetterSubRow").style.display = isWetterOpen ? "flex" : "none";
    document.getElementById("btnToggleWetter").classList.toggle("open", isWetterOpen);
    document.getElementById("btnToggleWetter").innerText = isWetterOpen ? "Wetter ▴" : "Wetter ▾";
}

function toggleHoehenMenu() {
    isHoehenOpen = !isHoehenOpen;
    document.getElementById("hoehenSubRow").style.display = isHoehenOpen ? "flex" : "none";
    document.getElementById("btnToggleHoehen").classList.toggle("open", isHoehenOpen);
    document.getElementById("btnToggleHoehen").innerText = isHoehenOpen ? "Höhenwind ▴" : "Höhenwind ▾";
}

function toggleLayer2Dropdown() {
    var el = document.getElementById("layer2Dropdown");
    var isAlreadyOpen = (el.style.display === "flex");
    if (isAlreadyOpen) {
        el.style.display = "none";
        return;
    }

    var btn = document.getElementById("layer2Btn");
    var rect = btn.getBoundingClientRect();
    el.style.top = (rect.bottom + 6) + "px";
    el.style.left = (rect.left + rect.width / 2) + "px";
    el.style.transform = "translateX(-50%)";
    el.style.display = "flex";
}

function toggleSettings(e) {
    if (e) e.preventDefault();
    var el = document.getElementById("settingsPopup");
    var isAlreadyOpen = (el.style.display === "block");
    el.style.display = isAlreadyOpen ? "none" : "block";
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
    var op = val / 100.0;
    if (layerNum === 1) {
        layer1Opacity = op;
        document.getElementById("opacityLabelL1").innerText = val + "%";
        document.getElementById("opacitySliderL1").value = val;
    } else {
        layer2Opacity = op;
        document.getElementById("opacityLabelL2").innerText = val + "%";
        document.getElementById("opacitySliderL2").value = val;
    }
    [mapLeft, mapRight].forEach(m => {
        if (!m) return;
        var p = m.getPane(layerNum === 1 ? 'contourPane1' : 'contourPane2');
        if (p) p.style.opacity = op;
    });
}

function initNavigationBars() {
    var wetterContainer = document.getElementById("wetterSubRow");
    var hoehenContainer = document.getElementById("hoehenSubRow");
    wetterContainer.innerHTML = "";
    hoehenContainer.innerHTML = "";

    var effectiveSide = 'left';
    var cfg = modelsState[effectiveSide].config;
    if (!cfg) return;
    var vars = cfg.variables || Object.keys(cfg.variables_config);
    if (!layer1Var || !vars.includes(layer1Var)) layer1Var = vars[0];

    var btnWind = document.getElementById("varBtn-wind");
    var btnGust = document.getElementById("varBtn-gust");
    if (btnWind) btnWind.style.display = vars.includes("wind") ? "inline-block" : "none";
    if (btnGust) btnGust.style.display = vars.includes("gust") ? "inline-block" : "none";

    var hasAlt = vars.some(v => cfg.variables_config[v] && cfg.variables_config[v].type === "altitude");
    document.getElementById("btnToggleHoehen").style.display = hasAlt ? "inline-flex" : "none";

    var hasWetter = vars.some(v => v !== "wind" && v !== "gust" && cfg.variables_config[v] && cfg.variables_config[v].type !== "altitude");
    document.getElementById("btnToggleWetter").style.display = hasWetter ? "inline-flex" : "none";

    vars.forEach(vKey => {
        var vCfg = cfg.variables_config[vKey];
        if (!vCfg || vKey === "wind" || vKey === "gust") return;

        var btn = document.createElement("button");
        btn.className = "var-btn";
        btn.id = "varBtn-" + vKey;
        btn.innerText = vCfg.label || vKey;
        btn.onclick = function() { switchLayer1(vKey); };

        if (vCfg.type === "altitude") hoehenContainer.appendChild(btn);
        else wetterContainer.appendChild(btn);
    });

    updateActiveButtonStates();
}

function updateActiveButtonStates() {
    var effectiveSide = 'left';
    var cfg = modelsState[effectiveSide].config;
    if (!cfg) return;
    var vars = cfg.variables || Object.keys(cfg.variables_config);
    var isWetterActive = false;
    var isHoehenActive = false;

    vars.forEach(vKey => {
        var btn = document.getElementById("varBtn-" + vKey);
        var isActive = (vKey === layer1Var);
        if (btn) btn.classList.toggle("active", isActive);

        if (isActive) {
            var vCfg = cfg.variables_config[vKey];
            if (vCfg) {
                if (vCfg.type === "altitude") isHoehenActive = true;
                else if (vKey !== "wind" && vKey !== "gust") isWetterActive = true;
            }
        }
    });

    var btnWetter = document.getElementById("btnToggleWetter");
    var btnHoehen = document.getElementById("btnToggleHoehen");
    if (btnWetter) btnWetter.classList.toggle("has-active", isWetterActive);
    if (btnHoehen) btnHoehen.classList.toggle("has-active", isHoehenActive);

    if (isWetterActive && !isWetterOpen) toggleWetterMenu();
    if (isHoehenActive && !isHoehenOpen) toggleHoehenMenu();
}

function initLayer2Dropdown() {
    var menu = document.getElementById("layer2Dropdown");
    menu.innerHTML = "";

    var clearBtn = document.createElement("button");
    clearBtn.className = "dropdown-item clear";
    clearBtn.innerText = "✖ 2. Ebene deaktivieren";
    clearBtn.onclick = function() { setSecondaryVar(null); };
    menu.appendChild(clearBtn);

    var effectiveSide = 'left';
    var cfg = modelsState[effectiveSide].config;
    if (!cfg) return;
    var vars = cfg.variables || Object.keys(cfg.variables_config);
    vars.forEach(vKey => {
        var vCfg = cfg.variables_config[vKey];
        var btn = document.createElement("button");
        btn.className = "dropdown-item";
        btn.innerText = vCfg ? vCfg.label : vKey;
        btn.onclick = function() { setSecondaryVar(vKey); };
        menu.appendChild(btn);
    });
}

function setSecondaryVar(newVar) {
    layer2Var = newVar;
    var el = document.getElementById("layer2Dropdown");
    if (el) el.style.display = "none";
    
    var btn = document.getElementById("layer2Btn");
    var cfgSec = document.getElementById("cfgSectionL2");
    var titleSec = document.getElementById("cfgTitleL2");
    var effectiveSide = 'left';
    var cfg = modelsState[effectiveSide].config;

    if (layer2Var) {
        var vCfg = (cfg && cfg.variables_config[layer2Var]) || {};
        var lbl = vCfg.label || layer2Var;
        if (btn) btn.innerText = "2. Ebene: " + lbl + " ✕";
        btn.classList.add("active");
        cfgSec.style.opacity = "1";
        titleSec.innerText = "2. Ebene: " + lbl;
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

    // Bei Variablenwechsel prüfen, ob Ensembles existieren
    ['left', 'right'].forEach(s => {
        if (!modelHasEnsembleForCurrentVar(s)) {
            modelsState[s].currentMemberIdx = 0;
        }
    });

    var cfg = modelsState.left.config;
    var vCfg = cfg ? cfg.variables_config[layer1Var] : null;

    document.getElementById("cfgTitleL1").innerText = "1. Ebene: " + (vCfg ? vCfg.label : layer1Var);
    setLayerOpacity(1, (vCfg && vCfg.palette === "cloud") ? 95 : 60);

    initMemberPanelsAll();
    updateForecast();
}

function navLeft() {
    var curDay = getDayNameForStep(currentStepIdx);
    var steps = dayTimesteps[curDay] || [];
    var pos = steps.indexOf(currentStepIdx);

    if (pos > 0) {
        currentStepIdx = steps[pos - 1];
        updateForecast();
    } else {
        var dIdx = uniqueDays.indexOf(curDay);
        if (dIdx > 0) {
            var prevDay = uniqueDays[dIdx - 1];
            var prevSteps = dayTimesteps[prevDay];
            if (prevSteps && prevSteps.length > 0) {
                currentStepIdx = prevSteps[prevSteps.length - 1];
                updateForecast();
            }
        }
    }
}

function navRight() {
    var curDay = getDayNameForStep(currentStepIdx);
    var steps = dayTimesteps[curDay] || [];
    var pos = steps.indexOf(currentStepIdx);

    if (pos < steps.length - 1) {
        currentStepIdx = steps[pos + 1];
        updateForecast();
    } else {
        var dIdx = uniqueDays.indexOf(curDay);
        if (dIdx < uniqueDays.length - 1) {
            var nextDay = uniqueDays[dIdx + 1];
            var nextSteps = dayTimesteps[nextDay];
            if (nextSteps && nextSteps.length > 0) {
                currentStepIdx = nextSteps[0];
                updateForecast();
            }
        }
    }
}

function navUp() {
    var side = 'left';
    if (verticalNavMode === 'run') {
        navRun(-1);
        return;
    }
    var st = modelsState[side];
    if (!modelHasEnsembleForCurrentVar(side)) return;
    var statOffset = st.config.member_names.length - 6;

    if (!isEnsembleOpen) {
        if (st.currentMemberIdx >= statOffset) {
            st.currentMemberIdx = (st.currentMemberIdx === statOffset) ? 0 : st.currentMemberIdx - 1;
        } else {
            st.currentMemberIdx = 0;
        }
    } else {
        st.currentMemberIdx = Math.max(0, st.currentMemberIdx - 1);
    }
    updateForecast();
}

function navDown() {
    var side = 'left';
    if (verticalNavMode === 'run') {
        navRun(1);
        return;
    }
    var st = modelsState[side];
    if (!modelHasEnsembleForCurrentVar(side)) return;
    var maxIdx = st.config.member_names.length - 1;
    var statOffset = st.config.member_names.length - 6;

    if (!isEnsembleOpen) {
        if (st.currentMemberIdx === 0) st.currentMemberIdx = statOffset;
        else if (st.currentMemberIdx >= statOffset) st.currentMemberIdx = Math.min(maxIdx, st.currentMemberIdx + 1);
    } else {
        st.currentMemberIdx = Math.min(maxIdx, st.currentMemberIdx + 1);
    }
    updateForecast();
}

function initDayButtons() {
    var container = document.getElementById("dayButtonsContainer");
    container.innerHTML = "";
    uniqueDays = [];
    dayTimesteps = {};
    
    var times = modelsState.left.times;
    if (!times) return;

    times.forEach((t, idx) => {
        var parts = t.local_str.split(" ")[0].split(".");
        var dateObj = new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
        var dayName = weekdays[dateObj.getDay()];
        if (!uniqueDays.includes(dayName)) {
            uniqueDays.push(dayName);
            dayTimesteps[dayName] = [];
        }
        dayTimesteps[dayName].push(idx);
    });
    
    uniqueDays.forEach(dayName => {
        var btn = document.createElement("button");
        btn.className = "day-btn";
        btn.id = "day-btn-" + dayName;
        btn.innerText = dayName;
        btn.onclick = function() { jumpToDaySameHour(dayName); };
        container.appendChild(btn);
    });
}

function jumpToDaySameHour(targetDayName) {
    var times = modelsState.left.times;
    if (!times || !times[currentStepIdx]) return;
    var currentHour = parseInt(times[currentStepIdx].local_str.split(" ")[1].split(":")[0]);
    var targetIndices = dayTimesteps[targetDayName];
    if (!targetIndices || targetIndices.length === 0) return;

    var bestIdx = targetIndices[0];
    var minDiff = 999;
    targetIndices.forEach(idx => {
        var h = parseInt(times[idx].local_str.split(" ")[1].split(":")[0]);
        var diff = Math.abs(h - currentHour);
        if (diff < minDiff) { 
            minDiff = diff; 
            bestIdx = idx; 
        }
    });
    currentStepIdx = bestIdx;
    updateForecast();
}

// Prüft jedes Modell individuell und rendert Buttons sauber
function renderMemberButtonsForTarget(domSide) {
    var stateSide = getActiveStateSide(domSide);
    var st = modelsState[stateSide];
    if (!st || !st.config) return;
    var cfg = st.config;

    var hCont = document.getElementById(domSide === 'left' ? "hauptlaufContainerLeft" : "hauptlaufContainerRight");
    var eCont = document.getElementById(domSide === 'left' ? "ensembleContainerLeft" : "ensembleContainerRight");
    var sCont = document.getElementById(domSide === 'left' ? "statistikenContainerLeft" : "statistikenContainerRight");
    var ensGroup = document.getElementById(domSide === 'left' ? "ensembleGroupLeft" : "ensembleGroupRight");
    var notice = document.getElementById(domSide === 'left' ? "onlyHlNoticeLeft" : "onlyHlNoticeRight");

    if (!hCont || !eCont || !sCont) return;

    hCont.innerHTML = "";
    eCont.innerHTML = "";
    sCont.innerHTML = "";

    var hasEns = modelHasEnsembleForCurrentVar(stateSide);
    if (!hasEns) {
        st.currentMemberIdx = 0;
    }

    var runs = availableRuns[st.currentModel] || [];
    var isOldRun = (runs.length > 0 && st.currentRunId !== runs[0].id);
    var statOffset = (cfg.member_names && cfg.member_names.length > 6) ? (cfg.member_names.length - 6) : 1;

    cfg.member_names.forEach((name, idx) => {
        var btn = document.createElement("button");
        btn.className = "member-btn";
        btn.id = `${domSide}-member-btn-${idx}`;

        if (idx === 0) {
            btn.innerText = "Hauptlauf";
            btn.onclick = function() {
                st.currentMemberIdx = idx;
                updateForecast();
            };
            hCont.appendChild(btn);
        } else if (hasEns && idx >= 1 && idx < statOffset) {
            btn.innerText = "Member " + idx;
            if (!isOldRun) {
                btn.onclick = function() {
                    st.currentMemberIdx = idx;
                    updateForecast();
                };
            }
            eCont.appendChild(btn);
        } else if (hasEns) {
            btn.innerText = name;
            btn.onclick = function() {
                st.currentMemberIdx = idx;
                updateForecast();
            };
            sCont.appendChild(btn);
        }
    });

    if (ensGroup) ensGroup.style.display = hasEns ? "block" : "none";
    if (notice) notice.style.display = hasEns ? "none" : "block";
}

function initMemberPanelsAll() {
    renderMemberButtonsForTarget('left');
    renderMemberButtonsForTarget('right');
    updateEnsembleToggleState();
}

function renderSingleLegendCol(varName, isIQR) {
    var effectiveSide = 'left';
    var cfg = modelsState[effectiveSide].config || {};
    var vCfg = (cfg.variables_config && cfg.variables_config[varName]) || {};
    var paletteType = isIQR ? ("iqr_" + (vCfg.palette || "wind")) : (vCfg.palette || "wind");
    var p = (cfg.palettes && cfg.palettes[paletteType]) || (cfg.palettes && cfg.palettes["wind"]) || { levels: [], colors: [] };
    var colors = p.colors || [];
    var levels = p.levels || [];

    var title = "";
    if (isIQR) {
        if (vCfg.palette === "sun" || vCfg.palette === "cloud") title = "% (IQR)";
        else if (vCfg.palette === "dbz") title = "dBZ (IQR)";
        else title = "km/h (IQR)";
    } else {
        if (vCfg.palette === "sun") title = "Sun %";
        else if (vCfg.palette === "cloud") title = "Cloud %";
        else if (vCfg.palette === "dbz") title = "dBZ";
        else title = "km/h";
    }

    var barHtml = "";
    for (var i = colors.length - 1; i >= 0; i--) {
        var c = colors[i];
        var isTrans = (c === 'transparent' || c === '#ffffff00' || (c.length === 9 && c.endsWith('00')));
        var bg = isTrans ? 'transparent' : c;
        var border = ((paletteType === "dbz" || paletteType === "cloud") && !isTrans) 
            ? "border-bottom: 1px solid rgba(255,255,255,0.4);" 
            : (c.toLowerCase() === "#ffffff" ? "border-top: 1px solid rgba(0,0,0,0.3); border-bottom: 1px solid rgba(0,0,0,0.3);" : "");
        barHtml += `<div style="background-color: ${bg}; flex: 1; ${border}"></div>`;
    }

    var labelsHtml = "";
    if (paletteType === "dbz") {
        labelsHtml = `<div>64</div><div>61</div><div>60</div><div>59</div><div>58</div><div>57</div><div>56</div><div>55</div><div>54</div><div>53</div><div>52</div><div>51</div><div>49</div><div>47</div><div>45</div><div>41</div><div>31</div><div>24</div><div>19</div><div>7</div>`;
    } else if (paletteType === "sun") {
        labelsHtml = `<div>100</div><div>80</div><div>60</div><div>40</div><div>20</div><div>0</div>`;
    } else if (paletteType === "cloud") {
        labelsHtml = `<div>100</div><div>95</div><div>90</div><div>80</div><div>70</div><div>60</div><div>50</div><div>40</div><div>30</div><div>20</div><div>10</div>`;
    } else if (paletteType === "iqr_dbz") {
        labelsHtml = `<div>+</div><div>65</div><div>56</div><div>48</div><div>40</div><div>32</div><div>25</div><div>18</div><div>12</div><div>6</div><div>0</div>`;
    } else if (paletteType === "iqr_sun" || paletteType === "iqr_cloud") {
        labelsHtml = `<div>100</div><div>90</div><div>80</div><div>70</div><div>60</div><div>50</div><div>40</div><div>30</div><div>20</div><div>10</div><div>0</div>`;
    } else if (paletteType === "iqr_wind") {
        labelsHtml = `<div>+</div><div>30</div><div>24</div><div>18</div><div>14</div><div>10</div><div>8</div><div>6</div><div>4</div><div>2</div><div>0</div>`;
    } else {
        if (levels && levels.length > 15) {
            labelsHtml = `<div>+</div><div>135</div><div>125</div><div>115</div><div>105</div><div>95</div><div>85</div><div>75</div><div>65</div><div>55</div><div>45</div><div>36</div><div>27</div><div>23</div><div>18</div><div>14</div><div>11</div><div>7</div><div>4</div><div>0</div>`;
        } else {
            labelsHtml = `<div>+</div><div>45</div><div>36</div><div>27</div><div>23</div><div>18</div><div>14</div><div>11</div><div>7</div><div>4</div><div>0</div>`;
        }
    }

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
    var box = document.getElementById("legendBox");
    var effectiveSide = 'left';
    var cfg = modelsState[effectiveSide].config;
    if (!cfg) return;
    var hasMultiple = modelHasEnsembleForCurrentVar(effectiveSide);
    var iqrIdx = (cfg.member_names && cfg.member_names.length > 1) ? (cfg.member_names.length - 1) : 0;
    var isIQR1 = (hasMultiple && modelsState[effectiveSide].currentMemberIdx === iqrIdx);
    
    var html = renderSingleLegendCol(layer1Var, isIQR1);
    if (layer2Var && layer2Var !== layer1Var) {
        var vCfg2 = cfg.variables_config[layer2Var] || {};
        var isIQR2 = (hasMultiple && vCfg2.has_ensemble && modelsState[effectiveSide].currentMemberIdx === iqrIdx);
        html += renderSingleLegendCol(layer2Var, isIQR2);
    }
    box.innerHTML = html;
}

async function fetchAndDecompress(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error("Fehler beim Laden von: " + url);
    const ds = new DecompressionStream('gzip');
    const decompressedStream = response.body.pipeThrough(ds);
    return await new Response(decompressedStream).arrayBuffer();
}

function decodeBinaryGrid(buffer, cfg) {
    const totalPoints = cfg.nx * cfg.ny;
    const lowBytes = new Uint8Array(buffer, 0, totalPoints);
    const highBytes = new Uint8Array(buffer, totalPoints, totalPoints);
    const s = new Int16Array(totalPoints);
    for (let i = 0; i < totalPoints; i++) s[i] = (highBytes[i] << 8) | lowBytes[i];
    let d = null;
    if (buffer.byteLength >= (totalPoints * 3)) {
        d = new Uint8Array(buffer, totalPoints * 2, totalPoints);
    }
    return { s: s, d: d };
}

function generateContoursClient(gridObj, paletteType, cfg) {
    const p = cfg.palettes[paletteType] || cfg.palettes["wind"];
    const levels = p.levels;
    const colors = p.colors;
    const s = gridObj.s;
    const values = new Float32Array(s.length);

    for (let i = 0; i < s.length; i++) values[i] = (s[i] < 0) ? NaN : (s[i] / 10.0);
    
    const thresholds = levels.slice(0, levels.length - 1);
    const contourGen = d3.contours().size([cfg.nx, cfg.ny]).smooth(true).thresholds(thresholds);
    const rawContours = contourGen(values);
    const xMin = cfg.xmin, xMax = cfg.xmax, yMin = cfg.ymin, yMax = cfg.ymax;
    const dx = (xMax - xMin) / (cfg.nx - 1);
    const dy = (yMax - yMin) / (cfg.ny - 1);
    
    const features = [];
    for (let i = 0; i < rawContours.length; i++) {
        const c = rawContours[i];
        if (!c.coordinates || c.coordinates.length === 0) continue;
        const color = colors[i] || colors[colors.length - 1];
        const geoCoords = c.coordinates.map(polygon => 
            polygon.map(ring => 
                ring.map(pt => [xMin + (pt[0] - 0.5) * dx, yMin + (pt[1] - 0.5) * dy])
            )
        );
        features.push({
            type: "Feature",
            properties: { fill: color, stroke: color },
            geometry: { type: "MultiPolygon", coordinates: geoCoords }
        });
    }
    return { type: "FeatureCollection", features: features };
}

async function ensureDataLoaded(side, varName, memberIdx, stepIdx) {
    var st = modelsState[side];
    const cacheKey = `${st.currentModel}_${st.currentRunId}_${varName}_${memberIdx}_${stepIdx}`;
    const vCfg = (st.config && st.config.variables_config && st.config.variables_config[varName]) || {};
    var hasMultiple = modelHasEnsembleForCurrentVar(side);
    var iqrIdx = (st.config && st.config.member_names && st.config.member_names.length > 1) ? (st.config.member_names.length - 1) : 0;
    const isIQR = (hasMultiple && memberIdx === iqrIdx);
    const paletteType = isIQR ? ("iqr_" + (vCfg.palette || "wind")) : (vCfg.palette || "wind");

    if (!cacheContours[cacheKey]) {
        const runBuster = encodeURIComponent(st.config.ref_time_utc);
        const basePath = st.currentRunId ? `data/${st.currentModel}/${st.currentRunId}` : `data/${st.currentModel}`;
        if (!cacheGrid[cacheKey]) {
            const rawBuffer = await fetchAndDecompress(`${basePath}/grid_${varName}_m${memberIdx}_s${stepIdx}.bin.gz?v=${runBuster}`);
            cacheGrid[cacheKey] = decodeBinaryGrid(rawBuffer, st.config);
        }
        cacheContours[cacheKey] = generateContoursClient(cacheGrid[cacheKey], paletteType, st.config);
    }
    return cacheKey;
}

function initMapInstance(domId) {
    var swisstopo_relief_url = "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissalti3d-reliefschattierung/default/current/3857/{z}/{x}/{y}.png";
    var swisstopo_lakes_url = "https://wmts.geo.admin.ch/1.0.0/ch.bafu.vec25-seen/default/current/3857/{z}/{x}/{y}.png";
    var swisstopo_rivers_url = "https://wmts.geo.admin.ch/1.0.0/ch.bafu.vec25-gewaessernetz_2000/default/current/3857/{z}/{x}/{y}.png";
    var swisstopo_boundary_url = "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissboundaries3d-land-flaeche.fill/default/current/3857/{z}/{x}/{y}.png";
    var swisstopo_cantons_url = "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissboundaries3d-kanton-flaeche.fill/default/current/3857/{z}/{x}/{y}.png";

    var m = L.map(domId, {
        center: [46.8182, 8.2275],
        zoom: 9, minZoom: 7, maxZoom: 15,
        zoomControl: false, preferCanvas: true
    });

    m.createPane('reliefPane'); m.getPane('reliefPane').style.zIndex = '200'; m.getPane('reliefPane').style.opacity = baseMapOpacity;
    m.createPane('waterPane'); m.getPane('waterPane').style.zIndex = '250'; m.getPane('waterPane').style.opacity = baseMapOpacity;
    m.createPane('boundaryPane'); m.getPane('boundaryPane').style.zIndex = '280'; m.getPane('boundaryPane').style.opacity = '1.0'; m.getPane('boundaryPane').style.pointerEvents = 'none';

    var canvasRendererBoundary = L.canvas({ pane: 'boundaryPane', padding: 0.1 });

    m.createPane('contourPane1'); m.getPane('contourPane1').style.opacity = layer1Opacity; m.getPane('contourPane1').style.zIndex = '400';
    m.createPane('contourPane2'); m.getPane('contourPane2').style.opacity = layer2Opacity; m.getPane('contourPane2').style.zIndex = '450';
    
    m.createPane('arrowPane'); 
    m.getPane('arrowPane').style.zIndex = '500';
    m.getPane('arrowPane').style.pointerEvents = 'none';

    m.createPane('cityPane'); 
    m.getPane('cityPane').style.zIndex = '520'; 
    m.getPane('cityPane').style.pointerEvents = 'none';
    m.getPane('cityPane').style.transition = 'opacity 0.1s ease';

    var arrowPane = m.getPane('arrowPane');
    var arrowCanvas = document.createElement('canvas');
    arrowCanvas.style.position = 'absolute';
    arrowCanvas.style.left = '0';
    arrowCanvas.style.top = '0';
    arrowCanvas.style.pointerEvents = 'none';
    arrowCanvas.style.transition = 'opacity 0.12s ease';
    arrowPane.appendChild(arrowCanvas);
    var arrowCtx = arrowCanvas.getContext('2d');

    var relief = L.tileLayer(swisstopo_relief_url, {
        pane: 'reliefPane',
        attribution: '&copy; swisstopo | Wetter: &copy; MeteoSchweiz, DWD & Météo-France',
        maxZoom: 15, maxNativeZoom: 14
    }).addTo(m);

    L.tileLayer(swisstopo_lakes_url, { pane: 'waterPane', maxZoom: 15, maxNativeZoom: 14, opacity: 0.85 }).addTo(m);
    var rivers = L.tileLayer(swisstopo_rivers_url, { pane: 'waterPane', maxZoom: 15, maxNativeZoom: 14, opacity: 0.35 }).addTo(m);

    L.tileLayer(swisstopo_boundary_url, {
        pane: 'boundaryPane',
        className: 'boundary-national',
        maxZoom: 15, maxNativeZoom: 14
    }).addTo(m);

    var cantons = L.layerGroup();
    fetch("https://cdn.jsdelivr.net/gh/empet/Datasets@master/swiss-cantons.geojson")
        .then(res => res.json())
        .then(geojson => {
            L.geoJSON(geojson, {
                pane: 'boundaryPane',
                renderer: canvasRendererBoundary,
                interactive: false,
                style: { color: "#111111", weight: 0.7, opacity: 1.0, fill: false }
            }).addTo(cantons);
        })
        .catch(() => {
            L.tileLayer(swisstopo_cantons_url, { pane: 'boundaryPane', className: 'boundary-cantonal', maxZoom: 15, maxNativeZoom: 14 }).addTo(cantons);
        });

    var cityGroup = L.layerGroup([], { pane: 'cityPane' }).addTo(m);

    m.on('zoomstart', function() {
        setOverlaysVisible(false);
        if (mapSafetyTimer) clearTimeout(mapSafetyTimer);
        mapSafetyTimer = setTimeout(function() {
            setOverlaysVisible(true);
        }, 1200);
    });

    m.on('move', () => { if (domId === 'mapLeft') syncMap(mapLeft, mapRight); else syncMap(mapRight, mapLeft); });
    m.on('moveend', scheduleMapUpdates);
    m.on('zoomend', scheduleMapUpdates);

    return { 
        map: m, 
        relief: relief, 
        rivers: rivers, 
        cantons: cantons, 
        cities: cityGroup,
        arrowCanvas: arrowCanvas,
        arrowCtx: arrowCtx
    };
}

async function init() {
    try {
        var leftInit = initMapInstance('mapLeft');
        mapLeft = leftInit.map;
        baseReliefLayerLeft = leftInit.relief;
        riversLayerLeft = leftInit.rivers;
        cantonalBoundaryLayerLeft = leftInit.cantons;
        cityLayerGroupLeft = leftInit.cities;
        modelsState.left.arrowCanvas = leftInit.arrowCanvas;
        modelsState.left.arrowCtx = leftInit.arrowCtx;

        var rightInit = initMapInstance('mapRight');
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

        var slider = document.getElementById("timeSlider");
        slider.addEventListener("input", function() {
            var targetHour = parseInt(this.value);
            var curDay = getDayNameForStep(currentStepIdx);
            var steps = dayTimesteps[curDay] || [];
            if (steps.length === 0) return;

            var times = modelsState.left.times;
            var bestIdx = steps[0];
            var minDiff = 999;
            steps.forEach(idx => {
                var h = parseInt(times[idx].local_str.split(" ")[1].split(":")[0]);
                var diff = Math.abs(h - targetHour);
                if (diff < minDiff) { minDiff = diff; bestIdx = idx; }
            });
            currentStepIdx = bestIdx;
            updateForecast();
        });

        document.addEventListener('keydown', function(event) {
            if (event.key === "ArrowLeft") navLeft();
            else if (event.key === "ArrowRight") navRight();
            else if (event.key === "ArrowUp") { event.preventDefault(); navUp(); }
            else if (event.key === "ArrowDown") { event.preventDefault(); navDown(); }
        });

        window.onresize = function() {
            if (window.innerWidth <= 768) {
                toggleMobileModelPanel(false);
            }
            updateModelButtonLabels();
            initMemberPanelsAll();
            updateForecast();
            scheduleMapUpdates();
        };

        updateNavModeButton();

        for (const m of ALL_MODELS) {
            await fetchAvailableRuns(m);
        }

        if (window.innerWidth <= 768) {
            toggleMobileModelPanel(false);
        }

        await loadModelAndRun('left', 'icon-ch1');
        await loadModelAndRun('right', 'icon-d2');
        updateCityLabels();
    } catch (err) {
        console.error("Fehler bei init():", err);
    }
}

async function updateForecast() {
    var sidesToUpdate = isSplitActive ? ['left', 'right'] : ['left'];
    var effectiveSide = 'left';
    var times = modelsState[effectiveSide].times;
    if (!times || !times[currentStepIdx]) return;

    var currentDayName = getDayNameForStep(currentStepIdx);
    var currentHour = parseInt(times[currentStepIdx].local_str.split(" ")[1].split(":")[0]);
    var slider = document.getElementById("timeSlider");
    slider.min = 0; slider.max = 23; slider.value = currentHour;

    document.getElementById("loadingIndicator").style.display = "block";
    try {
        for (const side of sidesToUpdate) {
            var st = modelsState[side];
            if (!st.config) continue;
            var maxSteps = (st.times ? st.times.length : 100);
            var stepForSide = Math.min(currentStepIdx, maxSteps - 1);

            // Prüfung pro Seite
            if (!modelHasEnsembleForCurrentVar(side)) {
                st.currentMemberIdx = 0;
            }

            await ensureDataLoaded(side, layer1Var, st.currentMemberIdx, stepForSide);
            if (layer2Var) {
                var vCfg2 = st.config.variables_config[layer2Var] || {};
                var m2 = vCfg2.has_ensemble ? st.currentMemberIdx : 0;
                await ensureDataLoaded(side, layer2Var, m2, stepForSide);
            }
        }
    } catch (err) {
        console.error("Fehler beim Laden von Forecast-Daten:", err);
    }
    document.getElementById("loadingIndicator").style.display = "none";

    var tInfo = times[currentStepIdx];
    var parts = tInfo.local_str.split(" ")[0].split(".");
    var hourMin = tInfo.local_str.split(" ")[1].substring(0, 5);
    document.getElementById("currentStepLabel").innerText = parts[0] + "." + parts[1] + " " + hourMin + " LT";

    var cfgCurrent = modelsState.left.config;
    var refParts = cfgCurrent ? cfgCurrent.ref_time_utc.split(" ") : ["01.01.", "00:00"];
    var refDateParts = refParts[0].split(".");
    var refTimeHour = refParts[1].split(":")[0];
    
    if (isSplitActive) {
        var modL = getModelShortLabel(modelsState.left.currentModel);
        var modR = getModelShortLabel(modelsState.right.currentModel);
        document.getElementById("modelRunLabel").innerText = `🕒${refDateParts[0]}.${refDateParts[1]} ${refTimeHour}Z | L: ${modL} | R: ${modR}`;
    } else {
        var modShort = getModelShortLabel(modelsState.left.currentModel);
        document.getElementById("modelRunLabel").innerText = `🕒${refDateParts[0]}.${refDateParts[1]} ${refTimeHour}Z ${modShort}`;
    }

    uniqueDays.forEach(d => {
        var btn = document.getElementById("day-btn-" + d);
        if (btn) btn.classList.toggle("active", d === currentDayName);
    });

    ['left', 'right'].forEach(side => {
        var stateSide = getActiveStateSide(side);
        var st = modelsState[stateSide];
        var lbl = document.getElementById(side === 'left' ? "lblMemberBtnLeft" : "lblMemberBtnRight");
        if (lbl && st.config && st.config.member_names) {
            var mName = st.config.member_names[st.currentMemberIdx] || "Hauptlauf";
            lbl.innerText = mName + " ▾";
        }
    });

    ['left', 'right'].forEach(side => {
        var stateSide = getActiveStateSide(side);
        var st = modelsState[stateSide];
        if (st.config && st.config.member_names) {
            for (var i = 0; i < st.config.member_names.length; i++) {
                var btn = document.getElementById((side === 'left' ? "left-" : "right-") + "member-btn-" + i);
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
    var st = modelsState[side];
    var targetMap = (side === 'left') ? mapLeft : mapRight;
    if (!st.config || !targetMap) return;

    if (st.contourLayer1) targetMap.removeLayer(st.contourLayer1);
    var maxSteps = (st.times ? st.times.length : 100);
    var stepForSide = Math.min(currentStepIdx, maxSteps - 1);

    const key1 = `${st.currentModel}_${st.currentRunId}_${layer1Var}_${st.currentMemberIdx}_${stepForSide}`;
    
    st.contourLayer1 = L.geoJson(cacheContours[key1], {
        pane: 'contourPane1',
        renderer: st.canvasRenderer1,
        smoothFactor: 1.0,
        style: function(feature) {
            var fill = feature.properties.fill;
            var isTrans = (fill === 'transparent' || fill === '#ffffff00' || (fill.length === 9 && fill.endsWith('00')));
            if (layer1Mode === 'line') {
                return { fill: false, color: isTrans ? 'transparent' : fill, weight: 1.8, opacity: 1.0 };
            } else {
                return { fillColor: fill, color: isTrans ? 'transparent' : fill, weight: 0.5, fillOpacity: isTrans ? 0 : 1.0 };
            }
        }
    }).addTo(targetMap);

    if (st.contourLayer2) { targetMap.removeLayer(st.contourLayer2); st.contourLayer2 = null; }
    if (layer2Var) {
        var vCfg2 = st.config.variables_config[layer2Var] || {};
        var m2 = vCfg2.has_ensemble ? st.currentMemberIdx : 0;
        const key2 = `${st.currentModel}_${st.currentRunId}_${layer2Var}_${m2}_${stepForSide}`;

        st.contourLayer2 = L.geoJson(cacheContours[key2], {
            pane: 'contourPane2',
            renderer: st.canvasRenderer2,
            smoothFactor: 1.0,
            style: function(feature) {
                var fill = feature.properties.fill;
                var isTrans = (fill === 'transparent' || fill === '#ffffff00' || (fill.length === 9 && fill.endsWith('00')));
                if (layer2Mode === 'line') {
                    return { fill: false, color: isTrans ? 'transparent' : fill, weight: 2.2, opacity: 1.0 };
                } else {
                    return { fillColor: fill, color: isTrans ? 'transparent' : fill, weight: 0.5, fillOpacity: isTrans ? 0 : 1.0 };
                }
            }
        }).addTo(targetMap);
    }
}

function drawVisibleArrows(side) {
    var st = modelsState[side];
    var targetMap = (side === 'left') ? mapLeft : mapRight;
    if (!targetMap || !st.config || !st.arrowCanvas || !st.arrowCtx) return;

    var size = targetMap.getSize();
    if (!size || size.x <= 0 || size.y <= 0) return;

    var canvas = st.arrowCanvas;
    var ctx = st.arrowCtx;
    var dpr = window.devicePixelRatio || 1;

    var pad = 160;
    var topLeft = targetMap.containerPointToLayerPoint([-pad, -pad]);

    L.DomUtil.setPosition(canvas, topLeft);

    var totalW = size.x + pad * 2;
    var totalH = size.y + pad * 2;

    var targetW = Math.round(totalW * dpr);
    var targetH = Math.round(totalH * dpr);

    if (canvas.width !== targetW || canvas.height !== targetH) {
        canvas.width = targetW;
        canvas.height = targetH;
        canvas.style.width = totalW + 'px';
        canvas.style.height = totalH + 'px';
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    var arrowVar = null;
    var arrowMember = 0;
    var vCfg1 = st.config.variables_config[layer1Var];
    var hasMultiple = modelHasEnsembleForCurrentVar(side);
    var iqrIdx = (st.config && st.config.member_names && st.config.member_names.length > 1) ? (st.config.member_names.length - 1) : 0;
    
    if (vCfg1 && vCfg1.has_arrows && (!hasMultiple || st.currentMemberIdx < iqrIdx - 5)) {
        arrowVar = layer1Var;
        arrowMember = st.currentMemberIdx;
    } else if (layer2Var) {
        var vCfg2 = st.config.variables_config[layer2Var];
        if (vCfg2 && vCfg2.has_arrows) {
            arrowVar = layer2Var;
            arrowMember = vCfg2.has_ensemble ? st.currentMemberIdx : 0;
        }
    }

    if (!arrowVar) return;

    var maxSteps = (st.times ? st.times.length : 100);
    var stepForSide = Math.min(currentStepIdx, maxSteps - 1);
    const cacheKey = `${st.currentModel}_${st.currentRunId}_${arrowVar}_${arrowMember}_${stepForSide}`;
    const gridData = cacheGrid[cacheKey];
    if (!gridData || !gridData.s || !gridData.d) return;

    var bounds = targetMap.getBounds();
    var zoom = targetMap.getZoom();

    var step = 16;
    if (zoom >= 9 && zoom <= 10) step = 7;
    else if (zoom === 11) step = 4;
    else if (zoom === 12) step = 3;
    else if (zoom === 13) step = 2;
    else if (zoom >= 14) step = 1;

    if (st.config.nx <= 200) {
        step = Math.max(1, Math.round(step / 2));
    }

    var speeds = gridData.s;
    var dirs_half = gridData.d;

    var nx = st.config.nx, ny = st.config.ny;
    var xmin = st.config.xmin, xmax = st.config.xmax;
    var ymin = st.config.ymin, ymax = st.config.ymax;

    var bNorth = bounds.getNorth() + 0.15, bSouth = bounds.getSouth() - 0.15;
    var bWest = bounds.getWest() - 0.20, bEast = bounds.getEast() + 0.20;

    var rMin = Math.max(0, Math.floor((bSouth - ymin) / (ymax - ymin) * (ny - 1)));
    var rMax = Math.min(ny - 1, Math.ceil((bNorth - ymin) / (ymax - ymin) * (ny - 1)));
    var cMin = Math.max(0, Math.floor((bWest - xmin) / (xmax - xmin) * (nx - 1)));
    var cMax = Math.min(nx - 1, Math.ceil((bEast - xmin) / (xmax - xmin) * (nx - 1)));

    rMin = Math.floor(rMin / step) * step;
    cMin = Math.floor(cMin / step) * step;

    for (var r = rMin; r <= rMax; r += step) {
        var lat = ymin + r * (ymax - ymin) / (ny - 1);
        var rowOffset = r * nx;

        for (var c = cMin; c <= cMax; c += step) {
            var i = rowOffset + c;
            var sVal = speeds[i];
            if (sVal < 25) continue;

            var dirVal = dirs_half[i];
            if (dirVal === 255) continue;

            var lon = xmin + c * (xmax - xmin) / (nx - 1);
            var layerPt = targetMap.latLngToLayerPoint(L.latLng(lat, lon));
            
            var px = (layerPt.x - topLeft.x) * dpr;
            var py = (layerPt.y - topLeft.y) * dpr;

            if (px < -40 || px > canvas.width + 40 || py < -40 || py > canvas.height + 40) continue;

            var speed = sVal / 10.0;
            var dir = dirVal * 2.0;

            var arrow_w = Math.min(20, Math.max(4.5, 3.2 + Math.pow(speed, 0.58) * 1.2));
            var scale = (arrow_w / 15.0) * dpr;

            ctx.save();
            ctx.translate(px, py);
            ctx.rotate(dir * Math.PI / 180.0);
            ctx.scale(scale, scale);

            ctx.beginPath();
            ctx.moveTo(0, -10.5);   // Spitze
            ctx.lineTo(4.2, -3.0);  // Flügel rechts
            ctx.lineTo(0.9, -3.0);  // Schaftansatz rechts
            ctx.lineTo(0.9, 11.0);  // Schaftende rechts
            ctx.lineTo(-0.9, 11.0); // Schaftende links
            ctx.lineTo(-0.9, -3.0); // Schaftansatz links
            ctx.lineTo(-4.2, -3.0); // Flügel links
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
