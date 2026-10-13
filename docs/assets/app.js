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
  yt: { logo: "assets/logo-yt.svg", alt: "유튜브", title: "유튜브" },
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

const STOP_WORDS = new Set(
  `그리고 근데 그런데 그래서 하지만 그러나 그러면 그러니까 그래도 이거 저거 그거 이게 그게 저게
진짜 정말 너무 그냥 뭔가 좀 지금 오늘 어제 내일 이번 저번 요즘 최근 현재 당시 계속 항상 아직 이미 벌써 방금
하는 하면 해서 한데 인데 거든 잖아 아니 아님 뭐야 우리 너희 자기 사람 때문 위해 대해 관련 나는 솔로
있는 없는 같은 같이 이야 ㅋㅋ ㅎㅎ ㅠㅠ ㅜㅜ 남자 여자 이런 그런 저런 어떤 모든 무슨 아무
여기 거기 저기 어디 언제 누구 무엇 어떻게 왜 아주 매우 완전 굉장히 상당히 제법 은근 솔직히 사실 역시 어차피
갑자기 드디어 과연 아마 혹시 만약 비록 설마 도대체 대체 물론 당연히 확실히 분명히 약간 조금 많이 잘 다시
자주 가끔 별로 전혀 절대 결코 막 살짝 정도 만큼 바로 제일 이제 가장 먼저 나중 굳이 오히려 차라리 결국
아무튼 어쨌든 하여튼 좀더 뭔가 거 것 곳 수 때 중 등 분 데 바 줄 뿐 채 척 법 듯 양 편 쪽
나솔 미방 미방분 여출 남출 다둥 다둥이 솔솔 몰표 몰표녀 여돌 남돌 솔로녀 솔로남 존버 억까 인싸 아싸 점메추
존나 졸라 존내 좆나 씨발 시발 씨팔 시팔 씨벌 시벌 병신 븅신 병쉰 지랄 지럴 좆 좇 새끼 개새끼 미친 미쳤
꺼져 닥쳐 죽어 디질 뒤질 씹 보지 자지 걸레 창녀 창년 썅 니미 애미 애비 등신 호로 또라이 싸가지 개소리
좆밥 찌질 느금 느금마 염병 엠창 개년 개놈 개새 씨발롬 시발롬 환장 빡치 빡쳐 개자식 후레 쉬발 쉬벌 스발 슈발`.split(/\s+/),
);
const SWEAR_PARTS = ["씨발", "시발", "씨팔", "시팔", "씨벌", "시벌", "병신", "븅신", "지랄", "좆", "존나", "졸라", "새끼", "개새끼", "니미", "느금", "염병", "개소리", "쉬발", "쉬벌"];
const BOUND_NOUNS = new Set("곳 것 수 거 때 중 분 데 바 줄 뿐 채 척 법 듯 양 편 쪽".split(" "));
const PRED_RE = /(?:습니다|입니다|합니다|했습니다|됐습니다|였습니다|겠습니다|어요|아요|여요|해요|돼요|예요|이에요|네요|군요|잖아요|거든요|는데요|인데요|었어요|았어요|였어요|겠어요|했어|됐어|였어|겠어|았어|었어|봐줘|해줘|주세요|한다|된다|인다|운다|간다|온다|본다|준다|친다|난다|만든다|싶다|같다|없다|있다|하다|되다|이다|아니다|않다|했다|됐다|였다|겠다|았다|었다|않았다|해서|돼서|여서|아서|어서|면서|지만|니까|려고|도록|하면|되면|이면|아니면|하며|되며|이며|하고|되고|이고|아니고|하는|되는|이는|라는|이라는|않는|없는|있는|할까|될까|인가|건가|거야|거예요|거죠|건데|인데|하네|되네|이네|하지|되지|이지|보면|으며|으니|겁니다|겠죠|거든|잖아|더라|던데|더라고|스러운|스럽게|스러워|적인|답게|다운|은데|는데|한데|같아|같지|같음|같아서|같으면)$/;
const SHORT_RE = /(?:하|되|됐|했|돼|해)(?:다|요|까|지|네|면|며|고|서|니|게|라|어|아|여|죠|군|구|든|던|음)$|된$|될$/;
const PASTELS = [
  "#ffb4c8", "#ffd0a8", "#fff3a8", "#b8f2c2", "#9eecf5",
  "#b7d0ff", "#d4c4ff", "#ffc2f2", "#ffb8b0", "#c9e4ff",
  "#a8f0e0", "#ffe0a3", "#e4c6ff", "#ffc4d4", "#c8f5c4",
  "#ffd0c2", "#cdd0ff", "#fff0b0", "#b7ead8", "#ffc9b8",
];
const PARTICLES = ["께서는", "에서부터", "으로서", "로써", "처럼", "보다", "에서", "으로", "부터", "까지", "마저", "조차", "밖에", "마다", "에게", "한테", "이라고", "이든", "이나", "이랑", "라도", "라고", "이고", "은", "는", "이", "가", "을", "를", "도", "만", "와", "과", "의", "께", "랑", "에", "로", "들"];
const WORD_RE = /[가-힣]{2,}|\d+기/g;
const cloudEl = document.querySelector("#cloud");
const realtimeBox = document.querySelector("#realtime");
const realtimeBtn = document.querySelector(".realtime-current");
const realtimeRank = document.querySelector("#realtime-rank");
const realtimeTrack = document.querySelector("#realtime-track");
const realtimePanel = document.querySelector("#realtime-list");
const realtimeItems = document.querySelector("#realtime-items");
let baselineWords = null;
let baselineAt = 0;
let liveRanks = [];
let rollIndex = 0;
let rolling = false;
let rollSignature = "";

function stemWord(word) {
  if (/^\d+기$/.test(word)) return word;
  for (const particle of PARTICLES) {
    if (!word.endsWith(particle) || word.length <= particle.length) continue;
    const stem = word.slice(0, -particle.length);
    if (stem.length >= 2 || BOUND_NOUNS.has(stem)) return stemWord(stem);
  }
  return word;
}

function isCountedWord(word) {
  if (/^\d+기$/.test(word)) return true;
  if (word.length < 2 || STOP_WORDS.has(word)) return false;
  if (SWEAR_PARTS.some((part) => word.includes(part))) return false;
  if (PRED_RE.test(word) || SHORT_RE.test(word)) return false;
  return true;
}

function countedText(post) {
  if (post.source === "yt") return post.title || "";
  return `${post.title || ""} ${post.excerpt || ""}`;
}

function wordCounts(posts, since) {
  const counts = new Map();
  for (const post of posts) {
    if (since && timeValue(post) < since) continue;
    const seen = new Set();
    for (const raw of countedText(post).match(WORD_RE) || []) {
      const word = stemWord(raw);
      if (!isCountedWord(word)) continue;
      seen.add(word);
    }
    for (const word of seen) counts.set(word, (counts.get(word) || 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ko"));
}

function applyQuery(word) {
  input.value = word;
  clearBtn.hidden = false;
  state.q = word;
  state.limit = 120;
  reload();
}

let cloudKey = "";
let cloudWords = [];
let cloudLayoutWidth = 0;

function renderCloud(posts) {
  const key = `${posts.length}:${posts[posts.length - 1]?.id || 0}`;
  if (key !== cloudKey) {
    cloudKey = key;
    cloudWords = wordCounts(posts).slice(0, 20).map(([word, count], index) => ({
      word,
      count,
      color: PASTELS[index % PASTELS.length],
    }));
    cloudLayoutWidth = 0;
  }
  if (cloudEl.clientWidth && cloudEl.clientWidth !== cloudLayoutWidth) layoutCloud();
}

function cloudFont(index, count, max, min, total, maxPx, minPx) {
  const rankT = total <= 1 ? 1 : 1 - index / (total - 1);
  const weight = max === min ? 1 : (count - min) / (max - min);
  const mix = (rankT * 0.58 + weight * 0.42) ** 1.75;
  return minPx + mix * (maxPx - minPx);
}

function overlaps(a, b, pad) {
  return a.x < b.x + b.w + pad && a.x + a.w + pad > b.x && a.y < b.y + b.h + pad && a.y + a.h + pad > b.y;
}

function layoutCloud() {
  if (!cloudWords.length) {
    cloudEl.replaceChildren();
    cloudLayoutWidth = cloudEl.clientWidth;
    return;
  }
  const width = cloudEl.clientWidth;
  const height = cloudEl.clientHeight;
  if (width < 40 || height < 40) return;
  cloudLayoutWidth = width;
  const max = cloudWords[0].count;
  const min = cloudWords[cloudWords.length - 1].count;
  const baseMax = Math.max(34, Math.min(width * 0.24, height * 0.32, 60));
  const baseMin = Math.max(12, baseMax * 0.17);
  let scale = 1;
  let buttons = [];
  let points = [];
  for (let attempt = 0; attempt < 6; attempt += 1) {
    const maxPx = baseMax * scale;
    const minPx = Math.max(11, baseMin * scale);
    buttons = cloudWords.map((item, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = item.word;
      button.title = `${numberFormat.format(item.count)}번`;
      button.style.color = item.color;
      button.style.fontSize = `${cloudFont(index, item.count, max, min, cloudWords.length, maxPx, minPx).toFixed(1)}px`;
      button.addEventListener("click", () => applyQuery(item.word));
      return button;
    });
    cloudEl.replaceChildren(...buttons);
    const measures = buttons.map((button) => ({ w: button.offsetWidth, h: button.offsetHeight }));
    const cx = width / 2;
    const cy = height / 2;
    const limit = Math.min(width, height) / 2 - 1;
    const placed = [];
    points = [];
    let missed = false;
    for (let index = 0; index < buttons.length; index += 1) {
      const w = measures[index].w;
      const h = measures[index].h;
      let spot = null;
      for (let step = 0; step < 1600; step += 1) {
        const angle = step * 0.42;
        const radius = step * 0.38;
        const px = cx + Math.cos(angle) * radius;
        const py = cy + Math.sin(angle) * radius;
        if (Math.hypot(px - cx, py - cy) > limit) continue;
        const box = { x: px - w / 2, y: py - h / 2, w, h };
        if (box.x < -1 || box.y < -1 || box.x + box.w > width + 1 || box.y + box.h > height + 1) continue;
        if (placed.some((item) => overlaps(item, box, 2))) continue;
        spot = { x: px, y: py };
        placed.push(box);
        break;
      }
      if (!spot) {
        missed = true;
        break;
      }
      points.push(spot);
    }
    if (!missed) break;
    scale *= 0.88;
  }
  buttons.forEach((button, index) => {
    const spot = points[index];
    if (!spot) {
      button.remove();
      return;
    }
    button.style.left = `${spot.x}px`;
    button.style.top = `${spot.y}px`;
  });
}

if (document.fonts?.ready) {
  document.fonts.ready.then(() => {
    cloudLayoutWidth = 0;
    if (cloudWords.length && cloudEl?.clientWidth) layoutCloud();
  });
}

new ResizeObserver(() => {
  if (!cloudWords.length) return;
  const width = cloudEl.clientWidth;
  if (width && width !== cloudLayoutWidth) layoutCloud();
}).observe(cloudEl);

function deltaMark(word, rank, previous) {
  if (!previous) return { className: "same", text: "" };
  const before = previous.indexOf(word);
  if (before < 0) return { className: "new", text: "NEW" };
  if (before > rank) return { className: "up", text: "▲" };
  if (before < rank) return { className: "down", text: "▼" };
  return { className: "same", text: "–" };
}

function renderRealtime(posts) {
  const now = Date.now();
  const ranked = wordCounts(posts, now - 2 * 60 * 60 * 1000).slice(0, 10);
  const words = ranked.map(([word]) => word);
  let compare = null;
  if (!baselineWords) {
    baselineWords = words.slice();
    baselineAt = now;
  } else if (now - baselineAt > 3 * 60 * 1000) {
    baselineWords = words.slice();
    baselineAt = now;
  } else {
    compare = baselineWords;
  }
  liveRanks = ranked.map(([word, count], index) => ({
    word,
    count,
    rank: index,
    ...deltaMark(word, index, compare),
  }));
  realtimeItems.replaceChildren();
  if (!liveRanks.length) {
    realtimeRank.textContent = "–";
    rollSignature = "";
    if (!rolling) {
      const line = document.createElement("span");
      line.textContent = "집계 중";
      realtimeTrack.replaceChildren(line);
    }
    return;
  }
  for (const item of liveRanks) {
    const li = document.createElement("li");
    const n = document.createElement("span");
    n.className = "n";
    n.textContent = String(item.rank + 1);
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = item.word;
    button.addEventListener("click", () => applyQuery(item.word));
    const delta = document.createElement("span");
    delta.className = `delta ${item.className}`;
    delta.textContent = item.text;
    li.append(n, button, delta);
    realtimeItems.append(li);
  }
  const signature = words.join("\n");
  if (signature !== rollSignature) {
    rollSignature = signature;
    rollIndex = 0;
    rolling = false;
    paintRoll(false);
  }
}

function paintRoll(advance) {
  if (!liveRanks.length) return;
  if (!advance) {
    rolling = false;
    realtimeTrack.classList.remove("roll");
    const item = liveRanks[rollIndex % liveRanks.length];
    realtimeRank.textContent = String(item.rank + 1);
    const line = document.createElement("span");
    line.textContent = item.word;
    realtimeTrack.replaceChildren(line);
    return;
  }
  if (liveRanks.length < 2 || rolling || realtimeBtn.getAttribute("aria-expanded") === "true") return;
  const next = liveRanks[(rollIndex + 1) % liveRanks.length];
  const line = document.createElement("span");
  line.textContent = next.word;
  realtimeTrack.append(line);
  rolling = true;
  requestAnimationFrame(() => realtimeTrack.classList.add("roll"));
}

function renderKeywords(posts) {
  const source = posts && posts.length ? posts : allPosts;
  renderCloud(source);
  renderRealtime(source);
}

realtimeTrack.addEventListener("transitionend", () => {
  if (!realtimeTrack.classList.contains("roll")) return;
  realtimeTrack.classList.remove("roll");
  rollIndex = (rollIndex + 1) % Math.max(liveRanks.length, 1);
  rolling = false;
  paintRoll(false);
});

function setRealtimeOpen(open) {
  realtimeBtn.setAttribute("aria-expanded", String(open));
  realtimePanel.hidden = !open;
}

if (window.matchMedia("(hover: hover)").matches) {
  realtimeBox.addEventListener("mouseenter", () => setRealtimeOpen(true));
  realtimeBox.addEventListener("mouseleave", () => setRealtimeOpen(false));
} else {
  realtimeBtn.addEventListener("click", () => setRealtimeOpen(realtimeBtn.getAttribute("aria-expanded") !== "true"));
}

setInterval(() => paintRoll(true), 2800);

function renderStatus(board) {
  const posts = board.posts || allPosts;
  document.querySelector("#stat-total").textContent = numberFormat.format(posts.length);
  const today = kstDay(new Date().toISOString());
  document.querySelector("#stat-live").textContent = numberFormat.format(
    posts.filter((post) => kstDay(post.postedAt || post.firstSeenAt) === today).length,
  );
  for (const source of ["dc", "blind", "qoo", "yt"]) {
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
    since.textContent = "모으는 중입니다.";
  }
  renderKeywords(posts);
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
        const extra = await loadYoutube();
        if ((extra?.updatedAt || "") === ytStamp) {
          renderStatus({ ...meta, posts: allPosts });
          return null;
        }
        ytStamp = extra?.updatedAt || "";
        return absorbYoutube({ ...meta, posts: allPosts }, extra);
      }
    }
  } catch {
    /* 메타가 없으면 목록 파일을 그대로 읽는다. */
  }
  const url = new URL("data/posts.json", document.baseURI);
  url.searchParams.set("t", String(Date.now()));
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error("목록을 불러오지 못했습니다");
  const extra = await loadYoutube();
  ytStamp = extra?.updatedAt || "";
  return absorbYoutube(await response.json(), extra);
}

let ytStamp = "";

async function loadYoutube() {
  const url = new URL("data/youtube.json", document.baseURI);
  url.searchParams.set("t", String(Date.now()));
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

function absorbYoutube(board, extra) {
  if (!extra?.posts?.length) return board;
  const posts = [...(board.posts || [])];
  const seen = new Set(posts.map((post) => `${post.source}:${post.externalId}`));
  let next = posts.reduce((max, post) => Math.max(max, post.id || 0), 0);
  for (const post of extra.posts) {
    if (post.source !== "yt" || seen.has(`yt:${post.externalId}`)) continue;
    next += 1;
    seen.add(`yt:${post.externalId}`);
    posts.push({ ...post, id: next });
  }
  return { ...board, posts };
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
if (initialSource === "dc" || initialSource === "blind" || initialSource === "qoo" || initialSource === "yt") state.source = initialSource;
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
