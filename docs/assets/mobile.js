const backButton = document.querySelector("#m-back");
const titleEl = document.querySelector("#m-title");
const railButton = document.querySelector("#m-rail");
const appRoot = document.querySelector(".app");
const board = document.querySelector("#pair-board");

const VIEW_TITLE = {
  feed: "나솔 왈가왈부",
  profile: "현 기수 프로필",
  pair: "사랑의 짝대기",
};

let navLock = false;
let primed = false;
let lastKey = "";

function currentView() {
  if (document.querySelector("#tab-pair")?.getAttribute("aria-selected") === "true") return "pair";
  if (document.querySelector("#tab-profile")?.getAttribute("aria-selected") === "true") return "profile";
  return "feed";
}

function snapshot() {
  const railOpen = !appRoot.classList.contains("rail-closed");
  const pin = board?.dataset.focus || "";
  return `${railOpen ? "rail" : currentView()}|${pin}`;
}

function urlFor(key) {
  const [head, pin] = key.split("|");
  let hash = "";
  if (head === "rail") hash = "#status";
  else if (head === "profile") hash = "#profile";
  else if (head === "pair") hash = pin ? `#pairing/${encodeURIComponent(pin)}` : "#pairing";
  return `${location.pathname}${location.search}${hash}`;
}

function syncBar() {
  const railOpen = !appRoot.classList.contains("rail-closed");
  const view = currentView();
  const pin = board?.dataset.focus || "";
  if (railOpen) {
    backButton.hidden = false;
    titleEl.textContent = "현황";
    return;
  }
  if (view === "pair" && pin) {
    backButton.hidden = false;
    titleEl.textContent = pairPerson(pin)?.name || VIEW_TITLE.pair;
    return;
  }
  backButton.hidden = true;
  titleEl.textContent = VIEW_TITLE[view];
}

function remember() {
  syncBar();
  if (navLock) return;
  const key = snapshot();
  const url = urlFor(key);
  if (!primed) {
    primed = true;
    lastKey = key;
    history.replaceState({ key, pushed: false }, "", url);
    return;
  }
  if (key === lastKey) return;
  lastKey = key;
  history.pushState({ key, pushed: true }, "", url);
}

function applyHash() {
  navLock = true;
  const hash = location.hash;
  if (hash === "#status") {
    setRailOpen(true);
  } else {
    if (!appRoot.classList.contains("rail-closed")) setRailOpen(false);
    if (hash === "#profile") setStageView("profile");
    else if (hash.startsWith("#pairing")) {
      setStageView("pair");
      const id = decodeURIComponent(hash.slice("#pairing".length).replace(/^\//, ""));
      pinPair(id, { force: true });
    } else {
      setStageView("feed");
    }
  }
  lastKey = snapshot();
  navLock = false;
  syncBar();
}

function stepBack() {
  const railOpen = !appRoot.classList.contains("rail-closed");
  const pin = board?.dataset.focus || "";
  if (!railOpen && !pin) return;
  if (history.state?.pushed) {
    history.back();
    return;
  }
  navLock = true;
  if (railOpen) setRailOpen(false);
  else pinPair("", { force: true });
  lastKey = snapshot();
  history.replaceState({ key: lastKey, pushed: false }, "", urlFor(lastKey));
  navLock = false;
  syncBar();
}

function settle() {
  lastKey = snapshot();
  primed = true;
  history.replaceState({ key: lastKey, pushed: false }, "", urlFor(lastKey));
  syncBar();
}

backButton.addEventListener("click", stepBack);
railButton.addEventListener("click", () => setRailOpen(true));
document.addEventListener("board-chrome", remember);
window.addEventListener("popstate", applyHash);
document.addEventListener("board-ready", () => {
  navLock = true;
  if (location.hash === "#status") setRailOpen(true);
  else if (location.hash.startsWith("#pairing")) {
    setStageView("pair");
    const id = decodeURIComponent(location.hash.slice("#pairing".length).replace(/^\//, ""));
    if (id) pinPair(id, { force: true });
  }
  navLock = false;
  settle();
}, { once: true });
syncBar();
