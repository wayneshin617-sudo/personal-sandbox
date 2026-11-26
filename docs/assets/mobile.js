const backButton = document.querySelector("#m-back");
const titleEl = document.querySelector("#m-title");
const railButton = document.querySelector("#m-rail");
const appRoot = document.querySelector(".app");

const VIEW_TITLE = {
  feed: "나솔 왈가왈부",
  profile: "현 기수 프로필",
};

let navLock = false;
let primed = false;
let lastKey = "";

function currentView() {
  if (document.querySelector("#tab-profile")?.getAttribute("aria-selected") === "true") return "profile";
  return "feed";
}

function snapshot() {
  const railOpen = !appRoot.classList.contains("rail-closed");
  return railOpen ? "rail" : currentView();
}

function urlFor(key) {
  let hash = "";
  if (key === "rail") hash = "#status";
  else if (key === "profile") hash = "#profile";
  return `${location.pathname}${location.search}${hash}`;
}

function syncBar() {
  const railOpen = !appRoot.classList.contains("rail-closed");
  const view = currentView();
  if (railOpen) {
    backButton.hidden = false;
    titleEl.textContent = "현황";
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
    if (hash === "#profile" || hash.startsWith("#pairing")) setStageView("profile");
    else setStageView("feed");
  }
  lastKey = snapshot();
  navLock = false;
  syncBar();
}

function stepBack() {
  const railOpen = !appRoot.classList.contains("rail-closed");
  if (!railOpen) return;
  if (history.state?.pushed) {
    history.back();
    return;
  }
  navLock = true;
  setRailOpen(false);
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
  else if (location.hash === "#profile" || location.hash.startsWith("#pairing")) setStageView("profile");
  navLock = false;
  settle();
}, { once: true });
syncBar();
