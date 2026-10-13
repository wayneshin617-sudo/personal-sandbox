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

const SOURCES = {
  dc: { logo: "assets/logo-dc.png", alt: "디시", title: "디시인사이드" },
  blind: { logo: "assets/logo-blind.svg", alt: "블라인드", title: "블라인드" },
  qoo: { logo: "assets/logo-qoo.svg", alt: "더쿠", title: "더쿠" },
};

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

function timeValue(post) {
  const parsed = Date.parse(post.postedAt || post.firstSeenAt || "");
  return Number.isFinite(parsed) ? parsed : 0;
}

function matchingAsc() {
  return allPosts.filter(matches).sort((a, b) => timeValue(a) - timeValue(b) || a.id - b.id);
}

function kstDay(iso) {
  const parsed = Date.parse(iso || "");
  if (!Number.isFinite(parsed)) return "";
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(parsed));
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

function postedClock(post) {
  const parsed = Date.parse(post.postedAt || "");
  if (!Number.isFinite(parsed)) return post.postedLabel || "";
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(parsed));
}

function metaText(post) {
  const parts = [];
  const clock = postedClock(post);
  if (clock) parts.push(clock);
  if (post.comments) parts.push(`댓글 ${numberFormat.format(post.comments)}`);
  if (post.recommends) parts.push(`추천 ${numberFormat.format(post.recommends)}`);
  return parts.join(" · ");
}

function renderMsg(post, animate) {
  const msg = document.createElement("article");
  msg.className = "msg" + (animate ? " enter" : "");
  msg.dataset.id = String(post.id);
  msg.dataset.time = String(timeValue(post));
  if ((post.recommends || 0) >= 15 || (post.comments || 0) >= 40) msg.classList.add("hot");

  const avatar = document.createElement("img");
  avatar.className = "avatar " + post.source;
  const source = SOURCES[post.source] || SOURCES.dc;
  avatar.src = asset(source.logo);
  avatar.alt = source.alt;
  avatar.title = source.title;

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
  feed.append(renderMsg(post, animate));
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
  for (const post of posts) addOne(post, false);
  showEmpty();
  requestAnimationFrame(scrollToBottom);
}

function newestSlice() {
  const asc = matchingAsc();
  state.matched = asc.length;
  const start = Math.max(0, asc.length - state.limit);
  state.done = start === 0;
  return asc.slice(start);
}

function reload() {
  state.maxId = allPosts.reduce((max, post) => Math.max(max, post.id), 0);
  renderAll(newestSlice());
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
  const asc = matchingAsc();
  const index = asc.findIndex((post) => String(post.id) === oldest.dataset.id);
  if (index <= 0) {
    state.done = true;
    return;
  }
  const start = Math.max(0, index - 120);
  const older = asc.slice(start, index);
  state.loadingOlder = true;
  const beforeHeight = scroller.scrollHeight;
  const fragment = document.createDocumentFragment();
  for (const post of older) {
    if (seen.has(post.id) || !matches(post)) continue;
    fragment.append(renderMsg(post, false));
    seen.add(post.id);
    if (post.id > state.maxId) state.maxId = post.id;
  }
  const first = feed.firstChild;
  if (first) feed.insertBefore(fragment, first);
  else feed.append(fragment);
  if (start === 0) state.done = true;
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
  const today = kstDay(new Date().toISOString());
  document.querySelector("#stat-live").textContent = numberFormat.format(
    posts.filter((post) => kstDay(post.postedAt || post.firstSeenAt) === today).length,
  );
  for (const source of ["dc", "blind", "qoo"]) {
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
    since.textContent = `${when}부터 모으고 있습니다. 오래된 글이 위, 최신이 아래입니다. 새 글은 1분마다 가져와 맨 아래에 붙입니다.`;
  }
}

function replacePosts(posts) {
  allPosts.splice(0, allPosts.length, ...posts);
}

async function pull() {
  const board = await loadBoard();
  if (!board) return;
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
  const added = posts.filter((post) => !known.has(post.id)).sort((a, b) => timeValue(a) - timeValue(b) || a.id - b.id);
  replacePosts(posts);
  stamp = board.updatedAt || "";
  state.matched = matchingAsc().length;
  if (!added.length) {
    updateNote();
    return;
  }
  if (!state.pinned) {
    state.pending += added.filter(matches).length;
    updateJump();
    updateNote();
    return;
  }
  const visibleTimes = [...feed.querySelectorAll(".msg")].map((el) => Number(el.dataset.time) || 0);
  const oldestVisible = visibleTimes.length ? Math.min(...visibleTimes) : 0;
  const newestVisible = visibleTimes.length ? Math.max(...visibleTimes) : 0;
  const landsInside = added.some((post) => {
    const at = timeValue(post);
    return at > oldestVisible && at < newestVisible;
  });
  if (!visibleTimes.length || landsInside) {
    reload();
    return;
  }
  for (const post of added) {
    if (timeValue(post) >= newestVisible) onPost(post, true);
  }
  updateNote();
}

async function loadBoard() {
  const metaUrl = new URL("data/meta.json", document.baseURI);
  metaUrl.searchParams.set("t", String(Date.now()));
  try {
    const metaResponse = await fetch(metaUrl, { cache: "no-store" });
    if (metaResponse.ok) {
      const meta = await metaResponse.json();
      if (state.ready && (meta.updatedAt || "") === stamp) {
        renderStatus({ ...meta, posts: allPosts });
        return null;
      }
    }
  } catch {
    /* 메타가 없으면 목록 파일을 그대로 읽는다. */
  }
  const url = new URL("data/posts.json", document.baseURI);
  url.searchParams.set("t", String(Date.now()));
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error("목록을 불러오지 못했습니다");
  return response.json();
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
if (initialSource === "dc" || initialSource === "blind" || initialSource === "qoo") state.source = initialSource;
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
