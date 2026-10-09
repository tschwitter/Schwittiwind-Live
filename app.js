var map, config, times;

var currentModel = "icon-ch1";
var layer1Var = null;
var layer2Var = null;

var layer1Mode = 'fill';
var layer2Mode = 'fill';
var layer1Opacity = 0.55;
var layer2Opacity = 0.65;

var isWetterOpen = false;
var isHoehenOpen = false;

var currentMemberIdx = 0;
var currentStepIdx = 0;

var contourLayer1 = null;
var contourLayer2 = null;
var activeMarkers = null;
var cityLayerGroup = null;

var cacheGrid = {};
var cacheContours = {};

var uniqueDays = [];
var dayTimesteps = {};
var weekdays = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

// ================= DYNAMISCHES ORTSNETZ DER SCHWEIZ =================
var CITIES = [
    // Stufe 1: minZoom = 7 (Ganze Schweiz - Großzentren)
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

    // Stufe 2: minZoom = 9 (Wichtige Kantons- & Regionalzentren)
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

    // Stufe 3: minZoom = 10 (Größere Talschaften, Seen & Tourismusorte)
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
    { name: "Glarus", lat: 47.0406, lon: 9.0678, minZoom: 10 },

    // Stufe 4: minZoom = 11 (Täler, Pässe & Berggemeinden)
    { name: "Grindelwald", lat: 46.6242, lon: 8.0414, minZoom: 11 },
    { name: "Lauterbrunnen", lat: 46.5935, lon: 7.9077, minZoom: 11 },
    { name: "Mürren", lat: 46.5594, lon: 7.8927, minZoom: 11 },
    { name: "Adelboden", lat: 46.4927, lon: 7.5606, minZoom: 11 },
    { name: "Kandersteg", lat: 46.4957, lon: 7.6743, minZoom: 11 },
    { name: "Lenk", lat: 46.4581, lon: 7.4439, minZoom: 11 },
    { name: "Gstaad", lat: 46.4744, lon: 7.2863, minZoom: 11 },
    { name: "Meiringen", lat: 46.7283, lon: 8.1882, minZoom: 11 },
    { name: "Engelberg", lat: 46.8206, lon: 8.4072, minZoom: 11 },
    { name: "Einsiedeln", lat: 47.1278, lon: 8.7472, minZoom: 11 },
    { name: "Brunnen", lat: 46.9956, lon: 8.6053, minZoom: 11 },
    { name: "Weggis", lat: 47.0325, lon: 8.4344, minZoom: 11 },
    { name: "Flüelen", lat: 46.9014, lon: 8.6239, minZoom: 11 },
    { name: "Erstfeld", lat: 46.8336, lon: 8.6494, minZoom: 11 },
    { name: "Göschenen", lat: 46.6675, lon: 8.5861, minZoom: 11 },
    { name: "Airolo", lat: 46.5286, lon: 8.6083, minZoom: 11 },
    { name: "Faido", lat: 46.4772, lon: 8.7997, minZoom: 11 },
    { name: "Biasca", lat: 46.3589, lon: 8.9706, minZoom: 11 },
    { name: "Ascona", lat: 46.1558, lon: 8.7725, minZoom: 11 },
    { name: "Mendrisio", lat: 45.8703, lon: 8.9875, minZoom: 11 },
    { name: "Chiasso", lat: 45.8344, lon: 9.0322, minZoom: 11 },
    { name: "Leukerbad", lat: 46.3797, lon: 7.6289, minZoom: 11 },
    { name: "Crans-Montana", lat: 46.3119, lon: 7.4822, minZoom: 11 },
    { name: "Saas-Fee", lat: 46.1097, lon: 7.9286, minZoom: 11 },
    { name: "Verbier", lat: 46.0968, lon: 7.2286, minZoom: 11 },
    { name: "Champéry", lat: 46.1764, lon: 6.8708, minZoom: 11 },
    { name: "Aigle", lat: 46.3174, lon: 6.9686, minZoom: 11 },
    { name: "Saint-Maurice", lat: 46.2189, lon: 7.0028, minZoom: 11 },
    { name: "Disentis", lat: 46.7056, lon: 8.8556, minZoom: 11 },
    { name: "Ilanz", lat: 46.7744, lon: 9.2044, minZoom: 11 },
    { name: "Flims", lat: 46.8375, lon: 9.2842, minZoom: 11 },
    { name: "Thusis", lat: 46.6975, lon: 9.4406, minZoom: 11 },
    { name: "Tiefencastel", lat: 46.6622, lon: 9.5761, minZoom: 11 },
    { name: "Klosters", lat: 46.8697, lon: 9.8797, minZoom: 11 },
    { name: "Arosa", lat: 46.7789, lon: 9.6806, minZoom: 11 },
    { name: "Pontresina", lat: 46.4917, lon: 9.9042, minZoom: 11 },
    { name: "Zernez", lat: 46.6997, lon: 10.0939, minZoom: 11 },
    { name: "Scuol", lat: 46.7972, lon: 10.2989, minZoom: 11 },
    { name: "Samnaun", lat: 46.9536, lon: 10.3639, minZoom: 11 },
    { name: "Poschiavo", lat: 46.3267, lon: 10.0578, minZoom: 11 },
    { name: "Herisau", lat: 47.3858, lon: 9.2789, minZoom: 11 },
    { name: "Wattwil", lat: 47.3006, lon: 9.0864, minZoom: 11 },
    { name: "Wildhaus", lat: 47.2028, lon: 9.3514, minZoom: 11 },
    { name: "Murten", lat: 46.9281, lon: 7.1172, minZoom: 11 },
    { name: "Payerne", lat: 46.8211, lon: 6.9367, minZoom: 11 },
    { name: "Estavayer", lat: 46.8500, lon: 6.8481, minZoom: 11 },
    { name: "Le Locle", lat: 47.0583, lon: 6.7497, minZoom: 11 },
    { name: "Saint-Imier", lat: 47.1528, lon: 7.0003, minZoom: 11 },
    { name: "Moutier", lat: 47.2803, lon: 7.3711, minZoom: 11 },
    { name: "Laufen", lat: 47.4222, lon: 7.5008, minZoom: 11 },
    { name: "Rheinfelden", lat: 47.5542, lon: 7.7942, minZoom: 11 },
    { name: "Brugg", lat: 47.4853, lon: 8.2078, minZoom: 11 },
    { name: "Wohlen", lat: 47.3514, lon: 8.2781, minZoom: 11 },
    { name: "Zofingen", lat: 47.2881, lon: 7.9458, minZoom: 11 },
    { name: "Sursee", lat: 47.1722, lon: 8.1097, minZoom: 11 },
    { name: "Willisau", lat: 47.1206, lon: 7.9908, minZoom: 11 },
    { name: "Langnau i.E.", lat: 46.9389, lon: 7.7872, minZoom: 11 },
    { name: "Frutigen", lat: 46.5886, lon: 7.6492, minZoom: 11 },
    { name: "Brienz", lat: 46.7558, lon: 8.0375, minZoom: 11 }
];

function updateCityLabels() {
    if (!map) return;
    if (!cityLayerGroup) {
        cityLayerGroup = L.layerGroup().addTo(map);
    } else {
        cityLayerGroup.clearLayers();
    }

    var curZoom = map.getZoom();
    var bounds = map.getBounds();

    CITIES.forEach(city => {
        if (curZoom >= city.minZoom) {
            var latlng = L.latLng(city.lat, city.lon);
            if (bounds.contains(latlng)) {
                var html = `<div class="city-label-container"><div class="city-dot"></div><span class="city-name">${city.name}</span></div>`;
                var icon = L.divIcon({
                    html: html,
                    className: 'city-div-icon',
                    iconSize: [0, 0],
                    iconAnchor: [0, 0]
                });
                L.marker(latlng, { icon: icon, pane: 'cityPane', interactive: false }).addTo(cityLayerGroup);
            }
        }
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
    if (!times || !times[stepIdx]) return "";
    var parts = times[stepIdx].local_str.split(" ")[0].split(".");
    var dateObj = new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
    return weekdays[dateObj.getDay()];
}

function closeAllPopups() {
    document.getElementById("layer2Dropdown").style.display = "none";
    document.getElementById("settingsPopup").style.display = "none";
}

// ================= MODELL-UMSCHALTEN =================
async function switchModel(newModel) {
    if (currentModel === newModel && config) return;

    var prevValidDate = (times && times[currentStepIdx]) ? parseLocalStr(times[currentStepIdx].local_str) : null;
    var prevMember = currentMemberIdx;

    currentModel = newModel;

    document.getElementById("btnModel-icon-ch1").classList.toggle("active", currentModel === "icon-ch1");
    document.getElementById("btnModel-icon-ch2").classList.toggle("active", currentModel === "icon-ch2");

    document.getElementById("loadingIndicator").style.display = "block";
    try {
        const cacheBuster = Date.now();
        
        // KORREKTE DIREKTE PFADE: data/${currentModel}/config.json
        const configRes = await fetch(`data/${currentModel}/config.json?t=${cacheBuster}`);
        if (!configRes.ok) throw new Error("Konnte config.json nicht laden: " + configRes.status);
        config = await configRes.json();

        const timesRes = await fetch(`data/${currentModel}/times.json?t=${cacheBuster}`);
        if (!timesRes.ok) throw new Error("Konnte times.json nicht laden: " + timesRes.status);
        times = await timesRes.json();

        var vars = config.variables || Object.keys(config.variables_config);
        if (!vars.includes(layer1Var)) layer1Var = vars[0];
        if (layer2Var && !vars.includes(layer2Var)) setSecondaryVar(null);

        initNavigationBars();
        initLayer2Dropdown();
        initDayButtons();
        initMemberPanel();

        // 1. Exakt gleiche Lokalzeit im neuen Modell beibehalten
        var bestStepIdx = 0;
        if (prevValidDate && times && times.length > 0) {
            var minDiff = Infinity;
            times.forEach((t, idx) => {
                var d = parseLocalStr(t.local_str);
                var diff = Math.abs(d - prevValidDate);
                if (diff < minDiff) { 
                    minDiff = diff; 
                    bestStepIdx = idx;
                }
            });
        }
        currentStepIdx = bestStepIdx;

        // 2. Member / Statistik beibehalten
        var vCfg = config.variables_config[layer1Var];
        var hasEns = vCfg ? vCfg.has_ensemble : true;
        if (!hasEns) {
            currentMemberIdx = 0;
        } else {
            currentMemberIdx = Math.min(prevMember, config.member_names.length - 1);
        }

        updateMemberPanelVisibility(hasEns);
        document.getElementById("cfgTitleL1").innerText = "1. Ebene: " + (vCfg ? vCfg.label : layer1Var);

        var initialOp1 = (vCfg && vCfg.palette === "cloud") ? 95 : 55;
        setLayerOpacity(1, initialOp1);

        await updateForecast(currentMemberIdx, currentStepIdx);
    } catch (err) {
        console.error("Fehler beim Modellwechsel:", err);
    }
    document.getElementById("loadingIndicator").style.display = "none";
}

// ================= MENÜS =================
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
    closeAllPopups();
    if (isAlreadyOpen) return;

    var btn = document.getElementById("layer2Btn");
    var rect = btn.getBoundingClientRect();
    el.style.top = (rect.bottom + 6) + "px";
    el.style.left = (rect.left + rect.width / 2) + "px";
    el.style.transform = "translateX(-50%)";
    el.style.display = "flex";
}

function toggleSettings() {
    var el = document.getElementById("settingsPopup");
    var isAlreadyOpen = (el.style.display === "block");
    closeAllPopups();
    if (isAlreadyOpen) return;

    var btn = document.getElementById("settingsBtn");
    var rect = btn.getBoundingClientRect();
    el.style.top = (rect.bottom + 6) + "px";
    el.style.right = (window.innerWidth - rect.right) + "px";
    el.style.display = "block";
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
    renderContours();
}

function setLayerOpacity(layerNum, val) {
    var op = val / 100.0;
    if (layerNum === 1) {
        layer1Opacity = op;
        document.getElementById("opacityLabelL1").innerText = val + "%";
        document.getElementById("opacitySliderL1").value = val;
        if (map && map.getPane('contourPane1')) map.getPane('contourPane1').style.opacity = op;
    } else {
        layer2Opacity = op;
        document.getElementById("opacityLabelL2").innerText = val + "%";
        document.getElementById("opacitySliderL2").value = val;
        if (map && map.getPane('contourPane2')) map.getPane('contourPane2').style.opacity = op;
    }
}

function initNavigationBars() {
    var wetterContainer = document.getElementById("wetterSubRow");
    var hoehenContainer = document.getElementById("hoehenSubRow");
    wetterContainer.innerHTML = "";
    hoehenContainer.innerHTML = "";

    var vars = config.variables || Object.keys(config.variables_config);
    if (!layer1Var || !vars.includes(layer1Var)) layer1Var = vars[0];

    var btnWind = document.getElementById("varBtn-wind");
    var btnGust = document.getElementById("varBtn-gust");
    if (btnWind) btnWind.style.display = vars.includes("wind") ? "inline-block" : "none";
    if (btnGust) btnGust.style.display = vars.includes("gust") ? "inline-block" : "none";

    var hasAlt = vars.some(v => config.variables_config[v] && config.variables_config[v].type === "altitude");
    document.getElementById("btnToggleHoehen").style.display = hasAlt ? "inline-flex" : "none";

    var hasWetter = vars.some(v => v !== "wind" && v !== "gust" && config.variables_config[v] && config.variables_config[v].type !== "altitude");
    document.getElementById("btnToggleWetter").style.display = hasWetter ? "inline-flex" : "none";

    vars.forEach(vKey => {
        var vCfg = config.variables_config[vKey];
        if (!vCfg || vKey === "wind" || vKey === "gust") return;

        var btn = document.createElement("button");
        btn.className = "var-btn";
        btn.id = "varBtn-" + vKey;
        btn.innerText = vCfg.label || vKey;
        btn.onclick = function() { switchLayer1(vKey); };

        if (vCfg.type === "altitude") {
            hoehenContainer.appendChild(btn);
        } else {
            wetterContainer.appendChild(btn);
        }
    });

    updateActiveButtonStates();
}

function updateActiveButtonStates() {
    var vars = config.variables || Object.keys(config.variables_config);
    var isWetterActive = false;
    var isHoehenActive = false;

    vars.forEach(vKey => {
        var btn = document.getElementById("varBtn-" + vKey);
        var isActive = (vKey === layer1Var);
        if (btn) btn.classList.toggle("active", isActive);

        if (isActive) {
            var vCfg = config.variables_config[vKey];
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

    var vars = config.variables || Object.keys(config.variables_config);
    vars.forEach(vKey => {
        var vCfg = config.variables_config[vKey];
        var btn = document.createElement("button");
        btn.className = "dropdown-item";
        btn.innerText = vCfg ? vCfg.label : vKey;
        btn.onclick = function() { setSecondaryVar(vKey); };
        menu.appendChild(btn);
    });
}

function setSecondaryVar(newVar) {
    layer2Var = newVar;
    closeAllPopups();
    
    var btn = document.getElementById("layer2Btn");
    var cfgSec = document.getElementById("cfgSectionL2");
    var titleSec = document.getElementById("cfgTitleL2");

    if (layer2Var) {
        var vCfg = config.variables_config[layer2Var] || {};
        var lbl = vCfg.label || layer2Var;
        btn.innerText = "2. Ebene: " + lbl + " ✕";
        btn.classList.add("active");
        cfgSec.style.opacity = "1";
        titleSec.innerText = "2. Ebene: " + lbl;

        var targetOp = (vCfg.palette === "cloud") ? 95 : 65;
        setLayerOpacity(2, targetOp);
    } else {
        btn.innerText = "+ 2. Ebene";
        btn.classList.remove("active");
        cfgSec.style.opacity = "0.5";
        titleSec.innerText = "2. Ebene: Keine";
    }

    updateForecast(currentMemberIdx, currentStepIdx);
}

function switchLayer1(newVar) {
    if (layer1Var === newVar) return;
    layer1Var = newVar;

    updateActiveButtonStates();

    var vCfg = config.variables_config[layer1Var];
    var hasEns = vCfg ? vCfg.has_ensemble : true;
    if (!hasEns) currentMemberIdx = 0;

    document.getElementById("cfgTitleL1").innerText = "1. Ebene: " + (vCfg ? vCfg.label : layer1Var);

    var targetOp = (vCfg && vCfg.palette === "cloud") ? 95 : 55;
    setLayerOpacity(1, targetOp);

    updateMemberPanelVisibility(hasEns);
    updateForecast(currentMemberIdx, currentStepIdx);
}

function updateMemberPanelVisibility(hasEns) {
    var ensGroup = document.getElementById("ensembleGroup");
    var notice = document.getElementById("onlyHlNotice");
    if (ensGroup) ensGroup.style.display = hasEns ? "block" : "none";
    if (notice) notice.style.display = hasEns ? "none" : "block";
}

// ================= 24H-SLIDER & DYNAMISCHE TAGES-PAGINIERUNG =================
function navLeft() {
    var curDay = getDayNameForStep(currentStepIdx);
    var steps = dayTimesteps[curDay] || [];
    var pos = steps.indexOf(currentStepIdx);

    if (pos > 0) {
        updateForecast(currentMemberIdx, steps[pos - 1]);
    } else {
        var dIdx = uniqueDays.indexOf(curDay);
        if (dIdx > 0) {
            var prevDay = uniqueDays[dIdx - 1];
            var prevSteps = dayTimesteps[prevDay];
            if (prevSteps && prevSteps.length > 0) {
                updateForecast(currentMemberIdx, prevSteps[prevSteps.length - 1]);
            }
        }
    }
}

function navRight() {
    var curDay = getDayNameForStep(currentStepIdx);
    var steps = dayTimesteps[curDay] || [];
    var pos = steps.indexOf(currentStepIdx);

    if (pos < steps.length - 1) {
        updateForecast(currentMemberIdx, steps[pos + 1]);
    } else {
        var dIdx = uniqueDays.indexOf(curDay);
        if (dIdx < uniqueDays.length - 1) {
            var nextDay = uniqueDays[dIdx + 1];
            var nextSteps = dayTimesteps[nextDay];
            if (nextSteps && nextSteps.length > 0) {
                updateForecast(currentMemberIdx, nextSteps[0]);
            }
        }
    }
}

function navUp() {
    var vCfg = config.variables_config[layer1Var];
    if (vCfg && !vCfg.has_ensemble) return;
    updateForecast(Math.max(0, currentMemberIdx - 1), currentStepIdx);
}

function navDown() {
    var vCfg = config.variables_config[layer1Var];
    if (vCfg && !vCfg.has_ensemble) return;
    updateForecast(Math.min(config.member_names.length - 1, currentMemberIdx + 1), currentStepIdx);
}

function initDayButtons() {
    var container = document.getElementById("dayButtonsContainer");
    container.innerHTML = "";
    uniqueDays = [];
    dayTimesteps = {};
    
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
    var currentHour = parseInt(times[currentStepIdx].local_str.split(" ")[1].split(":")[0]);
    var targetIndices = dayTimesteps[targetDayName];
    if (!targetIndices || targetIndices.length === 0) return;

    var bestIdx = targetIndices[0];
    var minDiff = 999;
    targetIndices.forEach(idx => {
        var h = parseInt(times[idx].local_str.split(" ")[1].split(":")[0]);
        var diff = Math.abs(h - currentHour);
        if (diff < minDiff) { minDiff = diff; bestIdx = idx; }
    });
    updateForecast(currentMemberIdx, bestIdx);
}

function initMemberPanel() {
    var hauptContainer = document.getElementById("hauptlaufContainer");
    var ensembleContainer = document.getElementById("ensembleContainer");
    var statistikenContainer = document.getElementById("statistikenContainer");
    hauptContainer.innerHTML = ""; ensembleContainer.innerHTML = ""; statistikenContainer.innerHTML = "";
    var isMobile = window.innerWidth <= 768;

    config.member_names.forEach((name, idx) => {
        var btn = document.createElement("button");
        btn.className = "member-btn";
        btn.id = "member-btn-" + idx;
        
        if (idx === 0) {
            btn.innerText = isMobile ? "HL" : "Hauptlauf";
            hauptContainer.appendChild(btn);
        } else if (idx >= 1 && idx < config.member_names.length - 6) {
            btn.innerText = isMobile ? "M" + idx : name;
            ensembleContainer.appendChild(btn);
        } else {
            var statOffset = config.member_names.length - 6;
            if (idx === statOffset) btn.innerText = isMobile ? "MD" : name;
            else if (idx === statOffset + 1) btn.innerText = "Min";
            else if (idx === statOffset + 2) btn.innerText = "Max";
            else if (idx === statOffset + 3) btn.innerText = isMobile ? "%25" : name;
            else if (idx === statOffset + 4) btn.innerText = isMobile ? "%75" : name;
            else if (idx === statOffset + 5) btn.innerText = isMobile ? "IQ" : name;
            statistikenContainer.appendChild(btn);
        }
        btn.onclick = function() { updateForecast(idx, currentStepIdx); };
    });
}

function renderSingleLegendCol(varName, isIQR) {
    var vCfg = config.variables_config[varName] || {};
    var paletteType = isIQR ? ("iqr_" + (vCfg.palette || "wind")) : (vCfg.palette || "wind");
    var p = config.palettes[paletteType] || config.palettes["wind"];
    var colors = p.colors;

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
        var border = ((paletteType === "dbz" || paletteType === "cloud") && !isTrans) ? "border-bottom: 1px solid rgba(255,255,255,0.4);" : "";
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
        labelsHtml = `<div>+</div><div>45</div><div>36</div><div>27</div><div>23</div><div>18</div><div>14</div><div>11</div><div>7</div><div>4</div><div>0</div>`;
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
    var iqrIdx = config.member_names.length - 1;
    var isIQR1 = (currentMemberIdx === iqrIdx);
    
    var html = renderSingleLegendCol(layer1Var, isIQR1);
    if (layer2Var && layer2Var !== layer1Var) {
        var vCfg2 = config.variables_config[layer2Var] || {};
        var isIQR2 = (vCfg2.has_ensemble && currentMemberIdx === iqrIdx);
        html += renderSingleLegendCol(layer2Var, isIQR2);
    }
    box.innerHTML = html;
}

async function fetchAndDecompress(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error("Fehler beim Laden von: " + url);
    const ds = new DecompressionStream('gzip');
    const decompressedStream = response.body.pipeThrough(ds);
    const decompressedResponse = new Response(decompressedStream);
    const text = await decompressedResponse.text();
    return JSON.parse(text);
}

function generateContoursClient(s_flat, paletteType) {
    const p = config.palettes[paletteType] || config.palettes["wind"];
    const levels = p.levels;
    const colors = p.colors;
    
    const values = new Float32Array(s_flat.length);
    for (let i = 0; i < s_flat.length; i++) {
        values[i] = (s_flat[i] < 0) ? NaN : (s_flat[i] / 10.0);
    }
    
    const thresholds = levels.slice(0, levels.length - 1);
    const contourGen = d3.contours()
        .size([config.nx, config.ny])
        .smooth(true)
        .thresholds(thresholds);
                
    const rawContours = contourGen(values);
    const xMin = config.xmin, xMax = config.xmax;
    const yMin = config.ymin, yMax = config.ymax;
    const dx = (xMax - xMin) / (config.nx - 1);
    const dy = (yMax - yMin) / (config.ny - 1);
    
    const features = [];
    for (let i = 0; i < rawContours.length; i++) {
        const c = rawContours[i];
        if (!c.coordinates || c.coordinates.length === 0) continue;
        const color = colors[i] || colors[colors.length - 1];
        
        const geoCoords = c.coordinates.map(polygon => 
            polygon.map(ring => 
                ring.map(pt => [
                    xMin + (pt[0] - 0.5) * dx,
                    yMin + (pt[1] - 0.5) * dy
                ])
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

async function ensureDataLoaded(varName, memberIdx, stepIdx) {
    const cacheKey = `${currentModel}_${varName}_${memberIdx}_${stepIdx}`;
    const vCfg = config.variables_config[varName] || {};
    var iqrIdx = config.member_names.length - 1;
    const isIQR = (vCfg.has_ensemble && memberIdx === iqrIdx);
    const paletteType = isIQR ? ("iqr_" + (vCfg.palette || "wind")) : (vCfg.palette || "wind");

    if (!cacheContours[cacheKey]) {
        const runBuster = encodeURIComponent(config.ref_time_utc);
        // KORREKTE DIREKTE URL: data/{currentModel}/grid_...
        if (!cacheGrid[cacheKey]) {
            cacheGrid[cacheKey] = await fetchAndDecompress(`data/${currentModel}/grid_${varName}_m${memberIdx}_s${stepIdx}.json.gz?v=${runBuster}`);
        }
        cacheContours[cacheKey] = generateContoursClient(cacheGrid[cacheKey].s, paletteType);
    }
    return cacheKey;
}

async function init() {
    try {
        // 1. Relief
        var swisstopo_relief_url = "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissalti3d-reliefschattierung/default/current/3857/{z}/{x}/{y}.png";
        // 2. Seen
        var swisstopo_lakes_url = "https://wmts.geo.admin.ch/1.0.0/ch.bafu.vec25-seen/default/current/3857/{z}/{x}/{y}.png";
        // 3. Flüsse
        var swisstopo_rivers_url = "https://wmts.geo.admin.ch/1.0.0/ch.bafu.vec25-gewaessernetz_2000/default/current/3857/{z}/{x}/{y}.png";

        map = L.map('map', {
            center: [46.8182, 8.2275],
            zoom: 9, minZoom: 7, maxZoom: 15,
            preferCanvas: true
        });

        map.createPane('waterPane');
        map.getPane('waterPane').style.zIndex = '250';

        map.createPane('contourPane1');
        map.getPane('contourPane1').style.opacity = layer1Opacity;
        map.getPane('contourPane1').style.zIndex = '400';

        map.createPane('contourPane2');
        map.getPane('contourPane2').style.opacity = layer2Opacity;
        map.getPane('contourPane2').style.zIndex = '450';

        map.createPane('cityPane');
        map.getPane('cityPane').style.zIndex = '520';
        map.getPane('cityPane').style.pointerEvents = 'none';

        L.tileLayer(swisstopo_relief_url, {
            attribution: '&copy; <a href="https://www.swisstopo.admin.ch/" target="_blank">swisstopo</a> | Wetterdaten: &copy; <a href="https://www.meteoschweiz.admin.ch/" target="_blank">MeteoSchweiz</a>',
            maxZoom: 15, maxNativeZoom: 14
        }).addTo(map);

        L.tileLayer(swisstopo_lakes_url, {
            pane: 'waterPane',
            maxZoom: 15, maxNativeZoom: 14,
            opacity: 0.85
        }).addTo(map);

        L.tileLayer(swisstopo_rivers_url, {
            pane: 'waterPane',
            maxZoom: 15, maxNativeZoom: 14,
            opacity: 0.38
        }).addTo(map);

        map.on('moveend', function() {
            drawVisibleArrows();
            updateCityLabels();
        });
        map.on('zoomend', function() {
            drawVisibleArrows();
            updateCityLabels();
        });

        map.on('click', function() {
            closeAllPopups();
        });

        var slider = document.getElementById("timeSlider");
        slider.addEventListener("input", function() {
            var targetHour = parseInt(this.value);
            var curDay = getDayNameForStep(currentStepIdx);
            var steps = dayTimesteps[curDay] || [];
            if (steps.length === 0) return;

            var bestIdx = steps[0];
            var minDiff = 999;
            steps.forEach(idx => {
                var h = parseInt(times[idx].local_str.split(" ")[1].split(":")[0]);
                var diff = Math.abs(h - targetHour);
                if (diff < minDiff) {
                    minDiff = diff;
                    bestIdx = idx;
                }
            });
            updateForecast(currentMemberIdx, bestIdx);
        });

        document.addEventListener('keydown', function(event) {
            if (event.key === "ArrowLeft") navLeft();
            else if (event.key === "ArrowRight") navRight();
            else if (event.key === "ArrowUp") { event.preventDefault(); navUp(); }
            else if (event.key === "ArrowDown") { event.preventDefault(); navDown(); }
        });

        window.onresize = function() {
            closeAllPopups();
            initMemberPanel();
            updateForecast(currentMemberIdx, currentStepIdx);
            updateCityLabels();
        };

        // Starte direkt mit ICON-CH1
        await switchModel("icon-ch1");
        updateCityLabels();
    } catch (err) {
        console.error("Fehler beim Laden:", err);
    }
}

async function updateForecast(newMemberIdx, newStepIdx) {
    currentMemberIdx = parseInt(newMemberIdx);
    currentStepIdx = parseInt(newStepIdx);

    var currentDayName = getDayNameForStep(currentStepIdx);
    var currentHour = parseInt(times[currentStepIdx].local_str.split(" ")[1].split(":")[0]);
    var slider = document.getElementById("timeSlider");
    
    slider.min = 0;
    slider.max = 23;
    slider.value = currentHour;

    document.getElementById("loadingIndicator").style.display = "block";
    try {
        await ensureDataLoaded(layer1Var, currentMemberIdx, currentStepIdx);

        if (layer2Var) {
            var vCfg2 = config.variables_config[layer2Var] || {};
            var m2 = (vCfg2.has_ensemble) ? currentMemberIdx : 0;
            await ensureDataLoaded(layer2Var, m2, currentStepIdx);
        }
    } catch (err) {
        console.error("Fehler beim Laden:", err);
        document.getElementById("loadingIndicator").style.display = "none";
        return;
    }
    document.getElementById("loadingIndicator").style.display = "none";

    var tInfo = times[currentStepIdx];
    var parts = tInfo.local_str.split(" ")[0].split(".");
    var hourMin = tInfo.local_str.split(" ")[1].substring(0, 5);
    document.getElementById("currentStepLabel").innerText = parts[0] + "." + parts[1] + " " + hourMin + " LT";
    
    var refParts = config.ref_time_utc.split(" ");
    var refDateParts = refParts[0].split(".");
    var refTimeHour = refParts[1].split(":")[0];
    var modShort = (currentModel === "icon-ch2") ? "CH2" : "CH1";
    document.getElementById("modelRunLabel").innerText = `🕒${refDateParts[0]}.${refDateParts[1]} ${refTimeHour}Z ${modShort}`;

    uniqueDays.forEach(d => {
        var btn = document.getElementById("day-btn-" + d);
        if (btn) btn.classList.toggle("active", d === currentDayName);
    });

    for (var i = 0; i < config.member_names.length; i++) {
        var btn = document.getElementById("member-btn-" + i);
        if (btn) btn.classList.toggle("active", i === currentMemberIdx);
    }

    updateLegend();
    renderContours();
    drawVisibleArrows();
    updateCityLabels();
}

function renderContours() {
    if (contourLayer1) map.removeLayer(contourLayer1);
    const key1 = `${currentModel}_${layer1Var}_${currentMemberIdx}_${currentStepIdx}`;
    
    contourLayer1 = L.geoJson(cacheContours[key1], {
        pane: 'contourPane1',
        style: function(feature) {
            var fill = feature.properties.fill;
            var isTrans = (fill === 'transparent' || fill === '#ffffff00' || (fill.length === 9 && fill.endsWith('00')));
            
            if (layer1Mode === 'line') {
                return { fill: false, color: isTrans ? 'transparent' : fill, weight: 1.8, opacity: 1.0 };
            } else {
                return { fillColor: fill, color: isTrans ? 'transparent' : fill, weight: 0.5, fillOpacity: isTrans ? 0 : 1.0 };
            }
        }
    }).addTo(map);

    if (contourLayer2) { map.removeLayer(contourLayer2); contourLayer2 = null; }
    if (layer2Var) {
        var vCfg2 = config.variables_config[layer2Var] || {};
        var m2 = (vCfg2.has_ensemble) ? currentMemberIdx : 0;
        const key2 = `${currentModel}_${layer2Var}_${m2}_${currentStepIdx}`;

        contourLayer2 = L.geoJson(cacheContours[key2], {
            pane: 'contourPane2',
            style: function(feature) {
                var fill = feature.properties.fill;
                var isTrans = (fill === 'transparent' || fill === '#ffffff00' || (fill.length === 9 && fill.endsWith('00')));

                if (layer2Mode === 'line') {
                    return { fill: false, color: isTrans ? 'transparent' : fill, weight: 2.2, opacity: 1.0 };
                } else {
                    return { fillColor: fill, color: isTrans ? 'transparent' : fill, weight: 0.5, fillOpacity: isTrans ? 0 : 1.0 };
                }
            }
        }).addTo(map);
    }
}

function drawVisibleArrows() {
    if (!map || !config) return;
    if (!activeMarkers) { activeMarkers = L.layerGroup().addTo(map); } else { activeMarkers.clearLayers(); }

    var arrowVar = null;
    var arrowMember = 0;

    var vCfg1 = config.variables_config[layer1Var];
    var iqrIdx = config.member_names.length - 1;
    if (vCfg1 && vCfg1.has_arrows && currentMemberIdx < iqrIdx - 5) {
        arrowVar = layer1Var;
        arrowMember = currentMemberIdx;
    } else if (layer2Var) {
        var vCfg2 = config.variables_config[layer2Var];
        if (vCfg2 && vCfg2.has_arrows) {
            arrowVar = layer2Var;
            arrowMember = vCfg2.has_ensemble ? currentMemberIdx : 0;
        }
    }

    if (!arrowVar) return;

    const cacheKey = `${currentModel}_${arrowVar}_${arrowMember}_${currentStepIdx}`;
    const gridData = cacheGrid[cacheKey];
    if (!gridData || !gridData.s || !gridData.d || gridData.d.length === 0) return;

    var bounds = map.getBounds();
    var zoom = map.getZoom();
    var step = 32;
    if (zoom > 8 && zoom <= 10) step = 16;
    else if (zoom > 10 && zoom <= 11) step = 8;
    else if (zoom == 12) step = 4;
    else if (zoom == 13) step = 2;
    else if (zoom >= 14) step = 1;

    var speeds = gridData.s;
    var dirs = gridData.d;
    var labelType = config.variables_config[arrowVar].label || "Wind";

    for (var i = 0; i < speeds.length; i++) {
        var sVal = speeds[i];
        if (sVal < 30) continue;

        var r = Math.floor(i / config.nx);
        var c = i % config.nx;
        if (r % step !== 0 || c % step !== 0) continue;

        var lat = config.ymin + r * (config.ymax - config.ymin) / (config.ny - 1);
        var lon = config.xmin + c * (config.xmax - config.xmin) / (config.nx - 1);
        var latlng = L.latLng(lat, lon);

        if (bounds.contains(latlng)) {
            var speed = sVal / 10.0;
            var dir = dirs[i];
            var arrow_w = Math.min(35, Math.max(8, 6 + Math.pow(speed, 1.15) * 0.55));
            var arrow_h = Math.min(100, Math.max(16, 12 + Math.pow(speed, 1.4) * 1.0));

            var svg = '<div style="transform: rotate(' + dir + 'deg); width: 110px; height: 110px; display: flex; align-items: center; justify-content: center;">' +
                      '<svg viewBox="0 0 24 24" width="' + arrow_w.toFixed(1) + 'px" height="' + arrow_h.toFixed(1) + 'px">' +
                      '<path d="M11 22 H13 V10 H17 L12 2 L7 10 H11 Z" fill="black" stroke="white" stroke-width="0.8"/>' +
                      '</svg></div>';

            var icon = L.divIcon({ html: svg, iconSize: [110, 110], iconAnchor: [55, 55], className: 'wind-arrow-icon' });
            var modLabel = (currentModel === "icon-ch2") ? "ICON-CH2" : "ICON-CH1";
            L.marker(latlng, { icon: icon }).bindPopup(`<b>${labelType} (${modLabel}):</b><br>Stärke: ${speed.toFixed(1)} km/h<br>Richtung: ${dir.toFixed(0)}°`).addTo(activeMarkers);
        }
    }
}

window.onload = init;
