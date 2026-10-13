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
  ready: false,
  limit: 120,
};

const allPosts = [];
const seen = new Set();
let stamp = "";

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

function asset(path) {
  return new URL(path, document.baseURI).href;
}

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

function matchingDesc() {
  return allPosts.filter(matches).sort((a, b) => b.id - a.id);
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
  if ((post.recommends || 0) >= 15 || (post.comments || 0) >= 40) msg.classList.add("hot");

  const avatar = document.createElement("img");
  avatar.className = "avatar " + post.source;
  avatar.src = asset(post.source === "dc" ? "assets/logo-dc.png" : "assets/logo-blind.svg");
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
    copy.textContent = "새로 쌓이는 글 중에 걸리면 여기에 올립니다.";
  } else {
    strong.textContent = "아직 모인 글이 없습니다";
    copy.textContent = "이 페이지를 연 사람 모두 같은 목록을 봅니다.";
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
  seen.add(post.id);
  if (post.isSeed && !feed.querySelector('.msg[data-seed="0"]') && !feed.querySelector(".divider")) {
    feed.append(divider());
  }
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

function pageDesc() {
  const desc = matchingDesc();
  state.matched = desc.length;
  return desc.slice(0, state.limit);
}

function reload() {
  const posts = pageDesc();
  const total = state.matched;
  state.done = posts.length >= total;
  state.maxId = allPosts.reduce((max, post) => Math.max(max, post.id), 0);
  renderAll(posts);
  syncUrl();
  updateNote();
}

function updateNote() {
  if (!state.q) {
    note.hidden = true;
    note.textContent = "";
    clearBtn.hidden = true;
    return;
  }
  clearBtn.hidden = false;
  note.hidden = false;
  note.textContent = `‘${state.q}’ ${numberFormat.format(state.matched)}건 · 이 페이지를 보는 사람은 같은 결과를 봅니다`;
}

function onPost(post, animate) {
  if (post.id > state.maxId) state.maxId = post.id;
  if (!matches(post) || seen.has(post.id)) return;
  const wasPinned = state.pinned;
  if (!addOne(post, animate)) return;
  if (state.q) state.matched += 1;
  if (wasPinned) scrollToBottom();
  else {
    state.pending += 1;
    updateJump();
  }
  updateNote();
}

function loadOlder() {
  if (state.loadingOlder || state.done) return;
  const oldest = feed.querySelector(".msg");
  if (!oldest) return;
  const older = matchingDesc().filter((post) => post.id < Number(oldest.dataset.id)).slice(0, 120);
  if (!older.length) {
    state.done = true;
    return;
  }
  state.loadingOlder = true;
  const beforeHeight = scroller.scrollHeight;
  for (const post of older.slice().reverse()) addOne(post, false);
  if (older.length < 120) state.done = true;
  scroller.scrollTop += scroller.scrollHeight - beforeHeight;
  state.loadingOlder = false;
}

function relative(iso) {
  if (!iso) return "모으는 중";
  const delta = Math.max(0, Date.now() - new Date(iso).getTime());
  const sec = Math.round(delta / 1000);
  if (sec < 90) return "방금 반영";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}분 전 반영`;
  return `${Math.round(min / 60)}시간 전 반영`;
}

function renderStatus(board) {
  const posts = board.posts || allPosts;
  document.querySelector("#stat-total").textContent = numberFormat.format(posts.length);
  document.querySelector("#stat-live").textContent = numberFormat.format(posts.filter((post) => !post.isSeed).length);
  for (const source of ["dc", "blind"]) {
    const el = document.querySelector("#source-" + source);
    const health = el.querySelector(".health");
    const detail = el.querySelector(".detail");
    const count = posts.filter((post) => post.source === source).length;
    health.dataset.health = count ? "ok" : "wait";
    health.textContent = count ? `${numberFormat.format(count)}건` : "대기";
    detail.textContent = relative(board.updatedAt);
  }
  const since = document.querySelector("#since");
  if (board.startedAt) {
    const when = new Intl.DateTimeFormat("ko-KR", {
      timeZone: "Asia/Seoul",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(new Date(board.startedAt));
    since.textContent = `${when}부터 이 주소에 글을 쌓고 있습니다. 화면은 2초마다 다시 읽고, 새 글은 몇 분 간격으로 더해집니다.`;
  }
}

function replacePosts(posts) {
  allPosts.splice(0, allPosts.length, ...posts);
}

async function pull() {
  const url = new URL("data/posts.json", document.baseURI);
  url.searchParams.set("t", String(Date.now()));
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error("목록을 불러오지 못했습니다");
  const board = await response.json();
  renderStatus(board);
  const posts = board.posts || [];
  if (!state.ready) {
    replacePosts(posts);
    stamp = board.updatedAt || "";
    state.ready = true;
    reload();
    return;
  }
  if ((board.updatedAt || "") === stamp && posts.length === allPosts.length) return;
  const known = new Set(allPosts.map((post) => post.id));
  replacePosts(posts);
  stamp = board.updatedAt || "";
  state.matched = matchingDesc().length;
  for (const post of posts.filter((post) => !known.has(post.id)).sort((a, b) => a.id - b.id)) onPost(post, true);
  updateNote();
}

function scheduleSearch() {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    state.q = input.value.trim();
    state.limit = 120;
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
if (initialSource === "dc" || initialSource === "blind") state.source = initialSource;
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
    state.limit = 120;
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
  state.limit = 120;
  input.focus();
  reload();
});
document.querySelector("#composer").addEventListener("submit", (event) => {
  event.preventDefault();
  state.q = input.value.trim();
  state.limit = 120;
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

pull().catch(() => {
  const since = document.querySelector("#since");
  since.textContent = "목록 파일을 아직 읽지 못했습니다.";
});
setInterval(() => {
  pull().catch(() => {});
}, 2000);
