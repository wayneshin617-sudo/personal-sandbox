const SAVE_KEY = "reversal-gonan-v1";

const $ = (id) => document.getElementById(id);

const ui = {
  stage: $("stage"),
  scene: $("scene-art"),
  actors: $("actors"),
  hotspots: $("hotspots"),
  hp: $("hp-bar"),
  recordBtn: $("btn-record"),
  loc: $("location-tag"),
  splash: $("splash"),
  textbox: $("textbox"),
  speaker: $("speaker"),
  line: $("line"),
  cont: $("cont"),
  choices: $("choices"),
  cross: $("cross-ui"),
  invest: $("invest-ui"),
  moves: $("move-row"),
  title: $("title-ui"),
  record: $("record"),
  recordList: $("record-list"),
  recordDetail: $("record-detail"),
  recordPresent: $("record-present"),
  help: $("help"),
};

const audio = createAudio();

const state = {
  hp: 5,
  maxHp: 5,
  evidence: [],
  flags: {},
  sceneId: "title",
  locId: null,
  lineIndex: 0,
  queue: [],
  typing: false,
  typed: "",
  full: "",
  afterLine: null,
  mode: "title",
  cross: null,
  stmt: 0,
  presentMode: false,
  selectedItem: null,
  recordTab: "evidence",
  checkpoint: null,
};

function createAudio() {
  let ctx;
  const ensure = () => {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  };
  const beep = (freq, dur, type = "square", gain = 0.05) => {
    try {
      const c = ensure();
      const o = c.createOscillator();
      const g = c.createGain();
      o.type = type;
      o.frequency.value = freq;
      g.gain.setValueAtTime(gain, c.currentTime);
      g.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + dur);
      o.connect(g);
      g.connect(c.destination);
      o.start();
      o.stop(c.currentTime + dur);
    } catch {
      /* ignore */
    }
  };
  return {
    click: () => beep(420, 0.05),
    type: () => beep(220, 0.02, "triangle", 0.015),
    objection: () => {
      beep(140, 0.28, "sawtooth", 0.07);
      setTimeout(() => beep(90, 0.32, "sawtooth", 0.07), 80);
    },
    hold: () => beep(520, 0.16, "square", 0.05),
    damage: () => beep(80, 0.4, "sawtooth", 0.08),
    win: () => {
      beep(523, 0.12);
      setTimeout(() => beep(659, 0.12), 100);
      setTimeout(() => beep(784, 0.2), 200);
    },
    find: () => beep(880, 0.1, "triangle", 0.05),
  };
}

function save() {
  const dump = {
    hp: state.hp,
    evidence: state.evidence,
    flags: state.flags,
    checkpoint: state.checkpoint,
  };
  localStorage.setItem(SAVE_KEY, JSON.stringify(dump));
}

function loadSave() {
  try {
    return JSON.parse(localStorage.getItem(SAVE_KEY) || "null");
  } catch {
    return null;
  }
}

function hasSave() {
  return Boolean(loadSave());
}

function portrait(id, mood = "normal", extra = "") {
  const el = document.createElement("div");
  el.className = `portrait ${id} mood-${mood} ${extra}`.trim();
  if (id === "gonan") el.classList.add("tiny");
  el.innerHTML = `
    <div class="hair"></div>
    <div class="head">
      <div class="glass"></div>
      <div class="eye l"></div>
      <div class="eye r"></div>
      <div class="mouth"></div>
    </div>
    <div class="body"><div class="badge"></div></div>
  `;
  return el;
}

function setBg(name) {
  ui.stage.className = `bg-${name || "court"}`;
}

function setActors(who, mood, extra) {
  ui.actors.innerHTML = "";
  if (!who || who === "none") return;
  const list = Array.isArray(who) ? who : [who];
  ui.actors.className = list.length > 1 ? "split" : "solo";
  list.forEach((id, i) => {
    const m = Array.isArray(mood) ? mood[i] : mood;
    const x = Array.isArray(extra) ? extra[i] : extra;
    ui.actors.appendChild(portrait(id, m, x || ""));
  });
}

function showSplash(kind, text) {
  return new Promise((resolve) => {
    ui.splash.hidden = false;
    ui.splash.className = kind;
    ui.splash.innerHTML = `<div class="stamp">${text}</div>`;
    if (kind === "objection" || kind === "take" || kind === "reveal") audio.objection();
    else audio.hold();
    ui.stage.classList.add("shake");
    setTimeout(() => ui.stage.classList.remove("shake"), 420);
    setTimeout(() => {
      ui.splash.hidden = true;
      ui.splash.innerHTML = "";
      resolve();
    }, 720);
  });
}

function renderHp() {
  ui.hp.hidden = state.mode === "title" || state.mode === "invest";
  ui.hp.innerHTML = "";
  for (let i = 0; i < state.maxHp; i += 1) {
    const s = document.createElement("span");
    s.textContent = "!";
    if (i >= state.hp) s.className = "off";
    ui.hp.appendChild(s);
  }
}

function addEvidence(id) {
  if (!id || state.evidence.includes(id)) return false;
  state.evidence.push(id);
  audio.find();
  save();
  return true;
}

function flag(id, value = true) {
  state.flags[id] = value;
  save();
}

function names(who) {
  return CASE.names[who] || "";
}

function hidePlayUi() {
  ui.textbox.hidden = true;
  ui.choices.hidden = true;
  ui.cross.hidden = true;
  ui.invest.hidden = true;
  ui.loc.hidden = true;
  ui.hotspots.innerHTML = "";
  ui.choices.innerHTML = "";
  ui.moves.innerHTML = "";
}

function showTextbox(who, text, done = false) {
  ui.textbox.hidden = false;
  ui.speaker.textContent = names(who) || (who === "narrator" ? "" : who);
  ui.speaker.className = who === "narrator" || who === "inner" ? "narrator" : "";
  if (who === "inner") ui.speaker.textContent = "고난의 속마음";
  ui.line.textContent = text;
  ui.cont.style.opacity = done ? "1" : "0";
}

function typeLine(who, text) {
  return new Promise((resolve) => {
    state.typing = true;
    state.full = text;
    state.typed = "";
    state.afterLine = resolve;
    showTextbox(who, "", false);
    const tick = () => {
      if (!state.typing) return;
      state.typed = text.slice(0, state.typed.length + 1);
      ui.line.textContent = state.typed;
      if (state.typed.length % 2 === 0) audio.type();
      if (state.typed.length >= text.length) {
        state.typing = false;
        ui.cont.style.opacity = "1";
        resolve();
        return;
      }
      const ch = text[state.typed.length - 1];
      const delay = "….!?".includes(ch) ? 90 : 18;
      setTimeout(tick, delay);
    };
    tick();
  });
}

function skipOrAdvance() {
  if (ui.record.hidden === false || ui.help.hidden === false) return;
  if (state.mode === "title") return;
  if (state.typing) {
    state.typing = false;
    ui.line.textContent = state.full;
    ui.cont.style.opacity = "1";
    if (state.afterLine) state.afterLine();
    return;
  }
  if (state.mode === "talk" || state.mode === "crossTalk") advanceQueue();
}

async function playLines(lines, then) {
  state.queue = lines.slice();
  state.lineIndex = 0;
  state.mode = state.mode === "cross" ? "crossTalk" : "talk";
  state.afterQueue = then;
  hidePlayUi();
  ui.recordBtn.hidden = false;
  ui.textbox.hidden = false;
  renderHp();
  await runLine();
}

async function runLine() {
  const line = state.queue[state.lineIndex];
  if (!line) {
    const next = state.afterQueue;
    state.afterQueue = null;
    if (next) next();
    return;
  }
  if (line.bg) setBg(line.bg);
  if (line.who && line.who !== "narrator" && line.who !== "inner") {
    setActors(line.who, line.mood, line.extra);
  }
  if (line.splash) await showSplash(line.splash, line.stamp || splashText(line.splash));
  if (line.give) {
    if (addEvidence(line.give)) {
      state.queue.splice(state.lineIndex + 1, 0, {
        who: "inner",
        text: `증거 입수: ${CASE.evidence[line.give].name}`,
      });
    }
  }
  if (line.flag) flag(line.flag);
  if (line.shake) {
    ui.stage.classList.add("shake");
    setTimeout(() => ui.stage.classList.remove("shake"), 420);
  }
  await typeLine(line.who || "narrator", line.text);
}

function splashText(kind) {
  return {
    objection: "이의 있음!",
    hold: "기다려!",
    take: "받아라!",
    guilty: "유죄",
    reveal: "범인은 바로 너야!",
  }[kind];
}

function advanceQueue() {
  state.lineIndex += 1;
  runLine();
}

function startNew() {
  localStorage.removeItem(SAVE_KEY);
  Object.assign(state, {
    hp: 5,
    evidence: ["badge", "overview"],
    flags: {},
    locId: null,
    presentMode: false,
    selectedItem: null,
    checkpoint: { type: "scene", id: "prologue" },
  });
  ui.title.hidden = true;
  goScene("prologue");
}

function continueGame() {
  const saved = loadSave();
  if (!saved || !saved.checkpoint) {
    startNew();
    return;
  }
  state.hp = saved.hp;
  state.evidence = saved.evidence;
  state.flags = saved.flags;
  state.checkpoint = saved.checkpoint;
  ui.title.hidden = true;
  if (saved.checkpoint.type === "invest") enterLocation(saved.checkpoint.id);
  else goScene(saved.checkpoint.id);
}

function goScene(id) {
  const scene = CASE.scenes[id];
  if (!scene) {
    console.error("missing scene", id);
    return;
  }
  state.sceneId = id;
  if (scene.checkpoint !== false) {
    state.checkpoint = { type: "scene", id };
    save();
  }
  hidePlayUi();
  ui.title.hidden = true;
  ui.recordBtn.hidden = false;
  setBg(scene.bg || "court");
  if (scene.type === "talk") {
    playLines(scene.lines, () => {
      if (scene.choice) showChoices(scene.choice);
      else follow(scene.next);
    });
  } else if (scene.type === "cross") {
    startCross(scene);
  } else if (scene.type === "present") {
    playLines(scene.lines, () => openRecord(true, scene.accept, scene.fail));
  } else if (scene.type === "invest") {
    enterLocation(scene.loc);
  } else if (scene.type === "ending") {
    endGame(scene);
  }
}

function follow(next) {
  if (!next) return;
  if (next === "RETRY") {
    state.hp = state.maxHp;
    save();
    if (state.checkpoint?.type === "invest") enterLocation(state.checkpoint.id);
    else goScene(state.checkpoint?.id || "prologue");
    return;
  }
  if (next === "RESUME_CROSS") {
    showStatement();
    return;
  }
  if (next.startsWith("invest:")) enterLocation(next.slice(7));
  else goScene(next);
}

function trialReady() {
  return CASE.trialReady(state);
}

function enterLocation(id) {
  const loc = CASE.locations[id];
  if (!loc) return;
  state.mode = "invest";
  state.locId = id;
  state.checkpoint = { type: "invest", id };
  save();
  hidePlayUi();
  ui.title.hidden = true;
  ui.recordBtn.hidden = false;
  ui.loc.hidden = false;
  ui.loc.textContent = loc.name;
  ui.invest.hidden = false;
  ui.hp.hidden = true;
  setBg(loc.bg);
  setActors(loc.actor || "gonan", loc.mood || "normal");
  ui.hotspots.innerHTML = "";
  loc.hotspots.forEach((spot) => {
    if (spot.require && !spot.require.every((f) => state.flags[f] || state.evidence.includes(f))) return;
    if (spot.hideIf && state.flags[spot.hideIf]) return;
    const b = document.createElement("button");
    b.className = "spot";
    b.style.left = `${spot.x}%`;
    b.style.top = `${spot.y}%`;
    b.style.width = `${spot.w}%`;
    b.style.height = `${spot.h}%`;
    b.title = spot.label;
    b.addEventListener("click", () => examine(spot));
    ui.hotspots.appendChild(b);
  });
  ui.moves.innerHTML = "";
  loc.moves.forEach((m) => {
    const b = document.createElement("button");
    b.textContent = m.label;
    b.addEventListener("click", () => {
      if (m.requireTrial && !trialReady()) {
        playLines(
          [
            {
              who: "gonan",
              mood: "sweat",
              text: "아직이다. 단서도 없는데 법정에 들어가면 무명한만 감방 구경이야. 내가 아니라 그 새끼가.",
            },
          ],
          () => enterLocation(id)
        );
        return;
      }
      follow(m.to);
    });
    ui.moves.appendChild(b);
  });
}

function examine(spot) {
  const lines = typeof spot.lines === "function" ? spot.lines(state) : spot.lines.slice();
  if (spot.give && !state.evidence.includes(spot.give)) {
    lines.push({ who: "inner", text: `(${CASE.evidence[spot.give].name}… 이건 챙긴다.)` });
  }
  playLines(lines, () => {
    if (spot.give) addEvidence(spot.give);
    if (spot.flag) flag(spot.flag);
    enterLocation(state.locId);
  });
}

function startCross(scene) {
  state.mode = "cross";
  state.cross = {
    ...scene,
    statements: scene.statements.map((s) => ({
      ...s,
      present: { ...(s.present || {}) },
      press: s.press
        ? {
            ...s.press,
            added: false,
            add: s.press.add
              ? { ...s.press.add, present: { ...(s.press.add.present || {}) } }
              : undefined,
          }
        : s.press,
    })),
  };
  state.stmt = 0;
  state.checkpoint = { type: "scene", id: scene.id || state.sceneId };
  save();
  setBg(scene.bg || "court");
  renderHp();
  playLines(scene.intro || [{ who: "judge", text: "증인을 심문하시오." }], () => showStatement());
}

function currentStmt() {
  return state.cross.statements[state.stmt];
}

function showStatement() {
  state.mode = "cross";
  const s = currentStmt();
  hidePlayUi();
  ui.recordBtn.hidden = false;
  ui.cross.hidden = false;
  ui.textbox.hidden = false;
  renderHp();
  setActors(state.cross.witness, s.mood || "normal", s.extra || "");
  showTextbox(state.cross.witness, s.text, true);
  $("stmt-count").textContent = `${state.stmt + 1} / ${state.cross.statements.length}`;
}

function moveStmt(dir) {
  if (state.mode !== "cross") return;
  const n = state.cross.statements.length;
  state.stmt = (state.stmt + dir + n) % n;
  audio.click();
  showStatement();
}

async function pressStmt() {
  if (state.mode !== "cross") return;
  const s = currentStmt();
  await showSplash("hold", "기다려!");
  const fallback = [
    { who: "gonan", mood: "smirk", text: "그거 진짜야? 아니면 그냥 입에서 나온 거야." },
    { who: state.cross.witness, text: "…사실입니다. 아마도." },
  ];
  const lines = Array.isArray(s.press) ? s.press : s.press?.lines || fallback;
  playLines(lines, () => {
    if (s.press && s.press.add && !s.press.added) {
      s.press.added = true;
      state.cross.statements.splice(state.stmt + 1, 0, s.press.add);
      playLines(
        [{ who: "yujoe", mood: "angry", text: "증언을 정정하겠다. 쓸데없는 추궁 덕분에 시간만 버렸군." }],
        () => {
          state.stmt += 1;
          showStatement();
        }
      );
      return;
    }
    showStatement();
  });
}

function presentFromCross() {
  if (state.mode !== "cross") return;
  openRecord(true, null, null);
}

function openRecord(forPresent, acceptMap, failScene) {
  state.presentMode = Boolean(forPresent);
  state.acceptMap = acceptMap || null;
  state.failScene = failScene || null;
  state.selectedItem = null;
  ui.record.hidden = false;
  ui.recordPresent.hidden = !forPresent;
  renderRecord();
}

function renderRecord() {
  const tab = state.recordTab;
  ui.recordList.innerHTML = "";
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t.dataset.tab === tab));
  const ids = tab === "evidence" ? state.evidence : CASE.profileOrder.filter((id) => CASE.profiles[id].seen || true);
  const source = tab === "evidence" ? CASE.evidence : CASE.profiles;
  ids.forEach((id) => {
    const item = source[id];
    if (!item) return;
    const b = document.createElement("button");
    b.textContent = item.name;
    if (state.selectedItem === id) b.classList.add("on");
    b.addEventListener("click", () => {
      state.selectedItem = id;
      ui.recordDetail.innerHTML = `<h3>${item.name}</h3><p>${item.desc}</p>`;
      renderRecord();
    });
    ui.recordList.appendChild(b);
  });
}

async function submitEvidence() {
  const id = state.selectedItem;
  if (!id || state.recordTab !== "evidence") {
    playLines([{ who: "inner", text: "제출할 증거를 골라." }], () => {});
    return;
  }
  ui.record.hidden = true;
  if (state.acceptMap) {
    const hit = state.acceptMap[id];
    if (hit) {
      await showSplash("take", "받아라!");
      follow(typeof hit === "string" ? hit : hit.next);
      return;
    }
    await wrongPresent();
    follow(state.failScene || state.sceneId);
    return;
  }
  const s = currentStmt();
  const hit = s.present && s.present[id];
  if (hit) {
    await showSplash("objection", "이의 있음!");
    follow(typeof hit === "string" ? hit : hit.next);
    return;
  }
  await wrongPresent();
  showStatement();
}

async function wrongPresent() {
  audio.damage();
  state.hp -= 1;
  renderHp();
  save();
  ui.stage.classList.add("shake");
  setTimeout(() => ui.stage.classList.remove("shake"), 420);
  if (state.hp <= 0) {
    await showSplash("guilty", "유죄");
    goScene("gameover");
    return;
  }
  await new Promise((r) => {
    playLines(
      [
        { who: "yujoe", mood: "smirk", text: "그게 모순이라고? 유치하군. 명탐정 맞나?" },
        { who: "judge", text: "변호인, 근거가 부족하오. 인내심이 남아 있을 때 제대로 내놓으시오." },
        { who: "gonan", mood: "sweat", text: "……착수금은 이미 썼는데." },
      ],
      r
    );
  });
}

function showChoices(options) {
  state.mode = "choice";
  ui.choices.hidden = false;
  ui.choices.innerHTML = "";
  options.forEach((opt) => {
    const b = document.createElement("button");
    b.textContent = opt.label;
    b.addEventListener("click", async () => {
      ui.choices.hidden = true;
      if (opt.wrong) {
        await wrongPresent();
        if (state.hp > 0) showChoices(options);
        return;
      }
      follow(opt.next);
    });
    ui.choices.appendChild(b);
  });
}

function endGame(scene) {
  state.mode = "ending";
  hidePlayUi();
  ui.recordBtn.hidden = true;
  ui.loc.hidden = true;
  setBg(scene.bg || "ending");
  playLines(scene.lines, () => {
    ui.title.hidden = false;
    $("btn-continue").disabled = !hasSave();
    hidePlayUi();
    ui.recordBtn.hidden = true;
    ui.hp.hidden = true;
    ui.loc.hidden = true;
    setActors("none");
    setBg("title");
    state.mode = "title";
  });
}

function bind() {
  $("btn-new").addEventListener("click", startNew);
  $("btn-continue").addEventListener("click", continueGame);
  $("btn-help").addEventListener("click", () => {
    ui.help.hidden = false;
  });
  $("help-close").addEventListener("click", () => {
    ui.help.hidden = true;
  });
  $("record-close").addEventListener("click", () => {
    ui.record.hidden = true;
    state.presentMode = false;
  });
  ui.recordBtn.addEventListener("click", () => openRecord(state.mode === "cross"));
  ui.recordPresent.addEventListener("click", submitEvidence);
  $("btn-press").addEventListener("click", pressStmt);
  $("btn-present").addEventListener("click", presentFromCross);
  $("btn-prev").addEventListener("click", () => moveStmt(-1));
  $("btn-next").addEventListener("click", () => moveStmt(1));
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      state.recordTab = tab.dataset.tab;
      renderRecord();
    });
  });
  ui.stage.addEventListener("click", (e) => {
    if (e.target.closest("button") || e.target.closest(".spot")) return;
    skipOrAdvance();
  });
  document.addEventListener("keydown", (e) => {
    if (["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
    if (e.key === "z" || e.key === "Z" || e.key === " " || e.key === "Enter") {
      e.preventDefault();
      skipOrAdvance();
    } else if (e.key === "r" || e.key === "R") {
      if (state.mode !== "title") openRecord(state.mode === "cross");
    } else if (e.key === "a" || e.key === "A") {
      if (state.mode === "cross") pressStmt();
    } else if (e.key === "s" || e.key === "S") {
      if (state.mode === "cross") presentFromCross();
    } else if (e.key === "ArrowLeft") {
      moveStmt(-1);
    } else if (e.key === "ArrowRight") {
      moveStmt(1);
    }
  });
  $("btn-continue").disabled = !hasSave();
}

function fillForCourt() {
  state.hp = 5;
  state.evidence = Object.keys(CASE.evidence);
  state.flags = {
    talked_muhyeong: true,
    got_tranq: true,
    examined_body: true,
    examined_prints: true,
    talked_baksa: true,
  };
  state.checkpoint = { type: "scene", id: "trial_intro" };
  save();
}

bind();

if (new URLSearchParams(location.search).has("court")) {
  ui.title.hidden = true;
  fillForCourt();
  goScene("trial_intro");
}
