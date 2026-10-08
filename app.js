var map, config, times;

var currentModel = "icon-ch1";
var currentRunId = null;
var availableRuns = { "icon-ch1": [], "icon-ch2": [] };

var verticalNavMode = 'member'; // 'member' oder 'run'

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

var cacheGrid = {};
var cacheContours = {};

var uniqueDays = [];
var dayTimesteps = {};
var weekdays = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

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
    document.getElementById("runDropdown-icon-ch1").style.display = "none";
    document.getElementById("runDropdown-icon-ch2").style.display = "none";
    document.getElementById("layer2Dropdown").style.display = "none";
    document.getElementById("settingsPopup").style.display = "none";
}

// ================= VERTIKAL-MODUS (MEMBER VS. LÄUFE) =================
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
        btn.title = "▲/▼ wechselt Modelläufe (z.B. 18Z, 12Z). Klick für Member-Modus";
    } else {
        btn.innerText = "Mbr";
        btn.classList.remove("mode-run");
        btn.title = "▲/▼ wechselt Ensemble-Member. Klick für Lauf-Modus";
    }
}

function navRun(dir) {
    var runs = availableRuns[currentModel] || [];
    if (runs.length <= 1) return;
    var currentIdx = runs.findIndex(r => r.id === currentRunId);
    if (currentIdx === -1) currentIdx = 0;

    var newIdx = currentIdx + dir;
    if (newIdx >= 0 && newIdx < runs.length) {
        selectRun(currentModel, runs[newIdx].id);
    }
}

// ================= MODELL-BUTTON KLICK =================
async function handleModelButtonClick(modelName) {
    if (currentModel !== modelName) {
        closeAllPopups();
        await switchModel(modelName);
    } else {
        toggleRunDropdown(modelName);
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

function updateModelButtonLabels() {
    var isMobile = window.innerWidth <= 768;
    ["icon-ch1", "icon-ch2"].forEach(m => {
        var btn = document.getElementById(`btnModel-${m}`);
        var runs = availableRuns[m] || [];
        var activeRun = (currentModel === m) ? currentRunId : (runs[0] ? runs[0].id : null);
        var activeObj = runs.find(r => r.id === activeRun) || runs[0];
        var modName = (m === "icon-ch1") ? "CH1" : "CH2";
        
        var runTxt = (activeObj && !isMobile) ? ` (${activeObj.label})` : "";
        btn.innerText = `${modName}${runTxt} ▾`;
    });
}

function toggleRunDropdown(modelName) {
    var el = document.getElementById(`runDropdown-${modelName}`);
    var isAlreadyOpen = (el.style.display === "flex");
    closeAllPopups();
    if (isAlreadyOpen) return;

    var btn = document.getElementById(`btnModel-${modelName}`);
    var runs = availableRuns[modelName] || [];
    el.innerHTML = "";

    if (runs.length === 0) {
        el.innerHTML = `<div style="font-size:11px; padding:4px 8px; color:#aaa;">Keine alten Läufe</div>`;
    } else {
        runs.forEach((r, idx) => {
            var item = document.createElement("button");
            item.className = "run-item" + (r.id === currentRunId ? " active" : "");
            var labelHtml = `<span>${r.label}</span>`;
            if (idx === 0) labelHtml += `<span class="run-tag-latest">Neu</span>`;
            item.innerHTML = labelHtml;
            item.onclick = function(e) {
                e.stopPropagation();
                selectRun(modelName, r.id);
            };
            el.appendChild(item);
        });
    }

    var rect = btn.getBoundingClientRect();
    el.style.top = (rect.bottom + 6) + "px";
    el.style.left = (rect.left + rect.width / 2) + "px";
    el.style.transform = "translateX(-50%)";
    el.style.display = "flex";
}

async function selectRun(modelName, runId) {
    closeAllPopups();
    currentModel = modelName;
    currentRunId = runId;
    await loadModelAndRun(currentModel, currentRunId);
}

async function switchModel(newModel) {
    if (currentModel === newModel && config) return;
    currentModel = newModel;
    var runs = availableRuns[currentModel] || [];
    var runId = (runs.length > 0) ? runs[0].id : null;
    await loadModelAndRun(currentModel, runId);
}

// ================= KERN-LADEN: MERKT SICH ZEIT, MEMBER & VARIABLEN =================
async function loadModelAndRun(modelName, runId) {
    var prevValidDate = (times && times[currentStepIdx]) ? parseLocalStr(times[currentStepIdx].local_str) : null;
    var prevMember = currentMemberIdx;

    document.getElementById("btnModel-icon-ch1").classList.toggle("active", modelName === "icon-ch1");
    document.getElementById("btnModel-icon-ch2").classList.toggle("active", modelName === "icon-ch2");

    document.getElementById("loadingIndicator").style.display = "block";
    try {
        if (!availableRuns[modelName] || availableRuns[modelName].length === 0) {
            await fetchAvailableRuns(modelName);
        }
        var runs = availableRuns[modelName] || [];
        if (!runId && runs.length > 0) runId = runs[0].id;
        currentRunId = runId;

        updateModelButtonLabels();

        const cacheBuster = Date.now();
        const runPath = runId ? `data/${modelName}/${runId}` : `data/${modelName}`;
        
        const configRes = await fetch(`${runPath}/config.json?t=${cacheBuster}`);
        if (!configRes.ok) throw new Error("Konnte config.json nicht laden: " + configRes.status);
        config = await configRes.json();

        const timesRes = await fetch(`${runPath}/times.json?t=${cacheBuster}`);
        if (!timesRes.ok) throw new Error("Konnte times.json nicht laden: " + timesRes.status);
        times = await timesRes.json();

        var vars = config.variables || Object.keys(config.variables_config);
        if (!vars.includes(layer1Var)) layer1Var = vars[0];
        if (layer2Var && !vars.includes(layer2Var)) setSecondaryVar(null);

        initNavigationBars();
        initLayer2Dropdown();
        initDayButtons();
        initMemberPanel();

        // 1. Exakt gleiche Lokalzeit im neuen Modelllauf beibehalten
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
        console.error("Fehler beim Laden des Laufs:", err);
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
    if (verticalNavMode === 'run') {
        navRun(-1);
    } else {
        var vCfg = config.variables_config[layer1Var];
        if (vCfg && !vCfg.has_ensemble) return;
        updateForecast(Math.max(0, currentMemberIdx - 1), currentStepIdx);
    }
}

function navDown() {
    if (verticalNavMode === 'run') {
        navRun(1);
    } else {
        var vCfg = config.variables_config[layer1Var];
        if (vCfg && !vCfg.has_ensemble) return;
        updateForecast(Math.min(config.member_names.length - 1, currentMemberIdx + 1), currentStepIdx);
    }
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
    const cacheKey = `${currentModel}_${currentRunId}_${varName}_${memberIdx}_${stepIdx}`;
    const vCfg = config.variables_config[varName] || {};
    var iqrIdx = config.member_names.length - 1;
    const isIQR = (vCfg.has_ensemble && memberIdx === iqrIdx);
    const paletteType = isIQR ? ("iqr_" + (vCfg.palette || "wind")) : (vCfg.palette || "wind");

    if (!cacheContours[cacheKey]) {
        const runBuster = encodeURIComponent(config.ref_time_utc);
        const basePath = currentRunId ? `data/${currentModel}/${currentRunId}` : `data/${currentModel}`;
        if (!cacheGrid[cacheKey]) {
            cacheGrid[cacheKey] = await fetchAndDecompress(`${basePath}/grid_${varName}_m${memberIdx}_s${stepIdx}.json.gz?v=${runBuster}`);
        }
        cacheContours[cacheKey] = generateContoursClient(cacheGrid[cacheKey].s, paletteType);
    }
    return cacheKey;
}

async function init() {
    try {
        // 1. Basiskarte: SwissALTI3D Reliefschattierung (reines 3D-Gelände, keine störenden Namen)
        var swisstopo_relief_url = "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissalti3d-reliefschattierung/default/current/3857/{z}/{x}/{y}.png";
        
        // 2. Offizieller Schweizer Seen-Layer (Lakes / Seen mit Uferkontur und zartem Blau)
        var swisstopo_lakes_url = "https://wmts.geo.admin.ch/1.0.0/ch.bafu.vec25-seen/default/current/3857/{z}/{x}/{y}.png";

        map = L.map('map', {
            center: [46.8182, 8.2275],
            zoom: 9, minZoom: 7, maxZoom: 15,
            preferCanvas: true
        });

        // Dedizierte Panes für saubere Schichtung
        map.createPane('lakePane');
        map.getPane('lakePane').style.zIndex = '250'; // Liegt direkt auf dem Relief, unter dem Wetter!

        map.createPane('contourPane1');
        map.getPane('contourPane1').style.opacity = layer1Opacity;
        map.getPane('contourPane1').style.zIndex = '400';

        map.createPane('contourPane2');
        map.getPane('contourPane2').style.opacity = layer2Opacity;
        map.getPane('contourPane2').style.zIndex = '450';

        // 1. Relief einfügen
        L.tileLayer(swisstopo_relief_url, {
            attribution: '&copy; <a href="https://www.swisstopo.admin.ch/" target="_blank">swisstopo</a> | Wetterdaten: &copy; <a href="https://www.meteoschweiz.admin.ch/" target="_blank">MeteoSchweiz</a>',
            maxZoom: 15, maxNativeZoom: 14
        }).addTo(map);

        // 2. Schweizer Seen einfügen (gestochen scharfe Umrisse auf dem Relief)
        L.tileLayer(swisstopo_lakes_url, {
            pane: 'lakePane',
            maxZoom: 15, maxNativeZoom: 14,
            opacity: 0.85
        }).addTo(map);

        map.on('moveend', drawVisibleArrows);
        map.on('zoomend', drawVisibleArrows);

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
            updateModelButtonLabels();
            initMemberPanel();
            updateForecast(currentMemberIdx, currentStepIdx);
        };

        updateNavModeButton();

        await fetchAvailableRuns("icon-ch1");
        await fetchAvailableRuns("icon-ch2");

        await switchModel("icon-ch1");
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
}

function renderContours() {
    if (contourLayer1) map.removeLayer(contourLayer1);
    const key1 = `${currentModel}_${currentRunId}_${layer1Var}_${currentMemberIdx}_${currentStepIdx}`;
    
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
        const key2 = `${currentModel}_${currentRunId}_${layer2Var}_${m2}_${currentStepIdx}`;

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

    const cacheKey = `${currentModel}_${currentRunId}_${arrowVar}_${arrowMember}_${currentStepIdx}`;
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
