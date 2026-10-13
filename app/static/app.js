const state = {
  source: "all",
  q: "",
  pinned: true,
  pending: 0,
  matched: 0,
  done: false,
  loadingOlder: false,
  reloading: false,
  maxId: 0,
};

const seen = new Set();
const scroller = document.querySelector("#scroller");
const feed = document.querySelector("#feed");
const jump = document.querySelector("#jump");
const input = document.querySelector("#q");
const clearBtn = document.querySelector("#clear");
const note = document.querySelector("#result-note");
const chips = [...document.querySelectorAll(".chip")];

const numberFormat = new Intl.NumberFormat("ko-KR");
let composing = false;
let searchTimer = 0;
let buffer = [];

function nickColor(seed) {
  let hash = 0;
  for (const ch of seed || "익명") hash = (hash * 31 + ch.codePointAt(0)) >>> 0;
  return `hsl(${hash % 360} 82% 70%)`;
}

function matches(post) {
  if (state.source !== "all" && post.source !== state.source) return false;
  if (!state.q) return true;
  const hay = [post.title, post.excerpt, post.author, post.company].join("\n").toLowerCase();
  return hay.includes(state.q.toLowerCase());
}

function highlight(el, text) {
  const q = state.q.trim();
  if (!q) {
    el.append(text);
    return;
  }
  const lower = text.toLowerCase();
  const needle = q.toLowerCase();
  let index = 0;
  while (index < text.length) {
    const found = lower.indexOf(needle, index);
    if (found < 0) {
      el.append(text.slice(index));
      break;
    }
    if (found > index) el.append(text.slice(index, found));
    const mark = document.createElement("mark");
    mark.textContent = text.slice(found, found + needle.length);
    el.append(mark);
    index = found + needle.length;
  }
}

function metaText(post) {
  const parts = [];
  if (post.postedLabel) parts.push(post.postedLabel);
  if (post.comments) parts.push(`댓글 ${numberFormat.format(post.comments)}`);
  if (post.recommends) parts.push(`추천 ${numberFormat.format(post.recommends)}`);
  return parts.join(" · ");
}

function divider() {
  const el = document.createElement("div");
  el.className = "divider";
  el.textContent = "여기서부터 새로 올라오는 글";
  return el;
}

function renderMsg(post, animate) {
  const msg = document.createElement("article");
  msg.className = "msg" + (animate ? " enter" : "");
  msg.dataset.id = String(post.id);
  msg.dataset.seed = post.isSeed ? "1" : "0";
  const hot = (post.recommends || 0) >= 15 || (post.comments || 0) >= 40;
  if (hot) msg.classList.add("hot");

  const avatar = document.createElement("img");
  avatar.className = "avatar " + post.source;
  avatar.src = post.source === "dc" ? "/static/logo-dc.png" : "/static/logo-blind.svg";
  avatar.alt = post.source === "dc" ? "디시" : "블라인드";
  avatar.title = post.source === "dc" ? "디시인사이드" : "블라인드";

  const who = document.createElement("div");
  who.className = "who";
  if (post.company) {
    const company = document.createElement("span");
    company.className = "company";
    company.textContent = post.company;
    who.append(company);
  }
  const nick = document.createElement("span");
  nick.className = "nick";
  nick.style.color = nickColor((post.author || "") + (post.ip || "") + (post.company || ""));
  nick.textContent = post.author || "익명";
  who.append(nick);
  if (post.ip) {
    const ip = document.createElement("span");
    ip.className = "ip";
    ip.textContent = `(${post.ip})`;
    who.append(ip);
  }

  const body = document.createElement("div");
  body.className = "body";
  const text = document.createElement(post.url ? "a" : "span");
  text.className = "text";
  if (post.url) {
    text.href = post.url;
    text.target = "_blank";
    text.rel = "noopener noreferrer";
  }
  if (post.badge) {
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = post.badge;
    text.append(badge);
  }
  highlight(text, post.title);
  body.append(text);
  if (post.excerpt) {
    const excerpt = document.createElement("p");
    excerpt.className = "excerpt";
    highlight(excerpt, post.excerpt);
    body.append(excerpt);
  }

  const meta = document.createElement("time");
  meta.className = "meta";
  meta.textContent = metaText(post);

  msg.append(avatar, who, body, meta);
  return msg;
}

function ensureDividerBeforeLive() {
  if (feed.querySelector(".divider")) return;
  if (!feed.querySelector('.msg[data-seed="1"]')) return;
  const firstLive = feed.querySelector('.msg[data-seed="0"]');
  const line = divider();
  if (firstLive) firstLive.before(line);
  else feed.append(line);
}

function place(post, msg) {
  const line = feed.querySelector(".divider");
  if (post.isSeed) {
    if (line) line.before(msg);
    else feed.append(msg);
    return;
  }
  ensureDividerBeforeLive();
  feed.append(msg);
}

function showEmpty() {
  feed.querySelector(".empty")?.remove();
  if (feed.querySelector(".msg")) return;
  const box = document.createElement("div");
  box.className = "empty";
  const strong = document.createElement("strong");
  const copy = document.createElement("p");
  if (state.q) {
    strong.textContent = `‘${state.q}’에 맞는 글이 없습니다`;
    copy.textContent = "이어서 수집하면서, 걸리는 글만 여기에 올립니다.";
  } else {
    strong.textContent = "새 글을 기다리고 있습니다";
    copy.textContent = "2초마다 두 게시판 목록을 확인합니다.";
  }
  box.append(strong, copy);
  feed.append(box);
}

function addOne(post, animate) {
  if (post.id > state.maxId) state.maxId = post.id;
  if (seen.has(post.id) || !matches(post)) return false;
  feed.querySelector(".empty")?.remove();
  const msg = renderMsg(post, animate);
  place(post, msg);
  if (post.isSeed && !feed.querySelector('.msg[data-seed="0"]') && !feed.querySelector(".divider")) {
    feed.append(divider());
  }
  seen.add(post.id);
  return true;
}

function overflow() {
  return scroller.scrollHeight - scroller.clientHeight;
}

function distanceFromBottom() {
  return scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
}

function scrollToBottom() {
  scroller.scrollTop = scroller.scrollHeight;
  state.pinned = true;
  state.pending = 0;
  updateJump();
}

function updateJump() {
  if (state.pinned) {
    jump.hidden = true;
    return;
  }
  jump.hidden = false;
  jump.textContent = state.pending > 0 ? `새 댓글 ${numberFormat.format(state.pending)}` : "맨 아래로";
}

function renderAll(posts) {
  feed.replaceChildren();
  seen.clear();
  const asc = posts.slice().reverse();
  for (const post of asc) addOne(post, false);
  if (posts.some((post) => post.isSeed) && !posts.some((post) => !post.isSeed)) {
    ensureDividerBeforeLive();
    if (!feed.querySelector(".divider")) feed.append(divider());
  }
  showEmpty();
  requestAnimationFrame(scrollToBottom);
}

async function fetchPosts(params) {
  const url = new URL("/api/posts", location.origin);
  if (params.q) url.searchParams.set("q", params.q);
  if (params.source && params.source !== "all") url.searchParams.set("source", params.source);
  url.searchParams.set("limit", String(params.limit || 120));
  if (params.before) url.searchParams.set("before", String(params.before));
  if (params.after) url.searchParams.set("after", String(params.after));
  const response = await fetch(url);
  if (!response.ok) throw new Error("목록을 불러오지 못했습니다");
  const data = await response.json();
  return data;
}

async function reload() {
  const token = ++reload.token;
  state.reloading = true;
  state.done = false;
  try {
    const data = await fetchPosts({ q: state.q, source: state.source, limit: 120 });
    if (token !== reload.token) return;
    const posts = data.posts || [];
    state.matched = data.matched || posts.length;
    state.maxId = posts.reduce((max, post) => Math.max(max, post.id), state.maxId);
    renderAll(posts);
    state.done = posts.length < 120;
    syncUrl();
  } catch (error) {
    if (token !== reload.token) return;
    feed.replaceChildren();
    const box = document.createElement("div");
    box.className = "empty";
    const strong = document.createElement("strong");
    strong.textContent = "글을 불러오지 못했습니다";
    const copy = document.createElement("p");
    copy.textContent = "잠시 후 다시 시도해 주세요.";
    box.append(strong, copy);
    feed.append(box);
  } finally {
    if (token === reload.token) {
      state.reloading = false;
      const pending = buffer.splice(0);
      for (const post of pending) onPost(post, true);
      updateNote();
    }
  }
}
reload.token = 0;

function updateNote() {
  const shown = feed.querySelectorAll(".msg").length;
  if (!state.q) {
    note.hidden = true;
    note.textContent = "";
    clearBtn.hidden = true;
    return;
  }
  clearBtn.hidden = false;
  note.hidden = false;
  const count = Math.max(state.matched, shown);
  note.textContent = `‘${state.q}’ ${numberFormat.format(count)}건 · 새로 올라오는 글도 바로 걸러집니다`;
}

function onPost(post, animate) {
  if (state.reloading) {
    buffer.push(post);
    return;
  }
  if (post.id > state.maxId) state.maxId = post.id;
  if (!matches(post) || seen.has(post.id)) return;
  const wasPinned = state.pinned;
  if (!addOne(post, animate)) return;
  if (state.q) state.matched += 1;
  if (wasPinned) {
    if (feed.querySelectorAll(".msg").length > 500) trimOld();
    scrollToBottom();
  } else {
    state.pending += 1;
    updateJump();
  }
  updateNote();
}

function trimOld() {
  const msgs = [...feed.querySelectorAll(".msg")];
  const extra = msgs.length - 400;
  for (let i = 0; i < extra; i += 1) {
    seen.delete(Number(msgs[i].dataset.id));
    msgs[i].remove();
  }
}

async function loadOlder() {
  if (state.loadingOlder || state.done || state.reloading) return;
  const oldest = feed.querySelector(".msg");
  if (!oldest) return;
  state.loadingOlder = true;
  const beforeHeight = scroller.scrollHeight;
  try {
    const data = await fetchPosts({
      q: state.q,
      source: state.source,
      limit: 120,
      before: Number(oldest.dataset.id),
    });
    const posts = data.posts || [];
    if (posts.length < 120) state.done = true;
    const asc = posts.slice().reverse();
    for (const post of asc) addOne(post, false);
    scroller.scrollTop += scroller.scrollHeight - beforeHeight;
  } catch (_error) {
    state.done = false;
  } finally {
    state.loadingOlder = false;
  }
}

function relative(iso) {
  if (!iso) return "";
  const delta = Math.max(0, Date.now() - new Date(iso).getTime());
  const sec = Math.round(delta / 1000);
  if (sec < 5) return "방금 확인";
  if (sec < 60) return `${sec}초 전 확인`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}분 전 확인`;
  return `${Math.round(min / 60)}시간 전 확인`;
}

function renderStatus(status) {
  document.querySelector("#stat-total").textContent = numberFormat.format(status.total || 0);
  document.querySelector("#stat-minute").textContent = numberFormat.format(status.lastMinute || 0);
  paintSource(document.querySelector("#source-dc"), status.sources?.dc);
  paintSource(document.querySelector("#source-blind"), status.sources?.blind);
  const since = document.querySelector("#since");
  if (status.startedAt) {
    const when = new Intl.DateTimeFormat("ko-KR", {
      timeZone: "Asia/Seoul",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(new Date(status.startedAt));
    const every = status.intervalSec || 2;
    since.textContent = `${when}부터 목록에 잡힌 글을 쌓는 중입니다. ${every}초마다 확인하고, 이전 페이지는 가져오지 않습니다.`;
  }
}

function paintSource(el, source) {
  const health = el.querySelector(".health");
  const detail = el.querySelector(".detail");
  if (!source) return;
  if (source.ok) {
    health.dataset.health = "ok";
    health.textContent = "연결됨";
    const fresh = source.lastNew ? `새 글 ${numberFormat.format(source.lastNew)} · ` : "";
    detail.textContent = fresh + relative(source.lastOkAt);
  } else if (source.message) {
    health.dataset.health = "bad";
    health.textContent = "다시 시도";
    detail.textContent = source.message;
  } else {
    health.dataset.health = "wait";
    health.textContent = "확인 중";
    detail.textContent = "목록을 읽고 있습니다";
  }
}

function scheduleSearch() {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    state.q = input.value.trim();
    reload();
  }, 180);
}

const initial = new URLSearchParams(location.search);
const initialQuery = (initial.get("q") || "").slice(0, 80);
const initialSource = initial.get("source");
if (initialQuery) {
  input.value = initialQuery;
  state.q = initialQuery.trim();
  clearBtn.hidden = false;
}
if (initialSource === "dc" || initialSource === "blind") {
  state.source = initialSource;
}
chips.forEach((chip) => chip.setAttribute("aria-pressed", String(chip.dataset.source === state.source)));

function syncUrl() {
  const url = new URL(location.href);
  if (state.q) url.searchParams.set("q", state.q);
  else url.searchParams.delete("q");
  if (state.source !== "all") url.searchParams.set("source", state.source);
  else url.searchParams.delete("source");
  history.replaceState(null, "", url);
}

chips.forEach((chip) => {
  chip.addEventListener("click", () => {
    state.source = chip.dataset.source;
    chips.forEach((item) => item.setAttribute("aria-pressed", String(item === chip)));
    reload();
  });
});

input.addEventListener("compositionstart", () => {
  composing = true;
});
input.addEventListener("compositionend", () => {
  composing = false;
  scheduleSearch();
});
input.addEventListener("input", () => {
  clearBtn.hidden = input.value.length === 0;
  if (!composing) scheduleSearch();
});
clearBtn.addEventListener("click", () => {
  input.value = "";
  state.q = "";
  input.focus();
  reload();
});
document.querySelector("#composer").addEventListener("submit", (event) => {
  event.preventDefault();
  state.q = input.value.trim();
  reload();
});

jump.addEventListener("click", scrollToBottom);

scroller.addEventListener("scroll", () => {
  const room = overflow();
  state.pinned = room <= 8 || distanceFromBottom() < 72;
  if (state.pinned) state.pending = 0;
  updateJump();
  if (room > 0 && scroller.scrollTop < 48) loadOlder();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "/" && document.activeElement !== input) {
    event.preventDefault();
    input.focus();
  } else if (event.key === "Escape" && document.activeElement === input) {
    event.preventDefault();
    input.blur();
  }
});

const stream = new EventSource("/api/stream");
stream.addEventListener("post", (event) => {
  onPost(JSON.parse(event.data), true);
});
stream.addEventListener("status", (event) => {
  renderStatus(JSON.parse(event.data));
});
stream.addEventListener("open", async () => {
  if (!state.maxId || state.reloading) return;
  try {
    const data = await fetchPosts({ q: state.q, source: state.source, after: state.maxId, limit: 200 });
    for (const post of data.posts || []) onPost(post, false);
  } catch (_error) {
    /* 다음 연결에서 다시 메웁니다. */
  }
});

if (window.ResizeObserver) {
  let frame = 0;
  new ResizeObserver(() => {
    if (!state.pinned || state.loadingOlder) return;
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      if (state.pinned && !state.loadingOlder) scroller.scrollTop = scroller.scrollHeight;
    });
  }).observe(feed);
}

reload();
fetch("/api/status").then((response) => response.json()).then(renderStatus).catch(() => {});
setInterval(() => {
  fetch("/api/status").then((response) => response.json()).then(renderStatus).catch(() => {});
}, 5000);
