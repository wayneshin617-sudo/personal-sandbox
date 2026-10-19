const PAGE = 50;

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
  limit: PAGE,
};

const allPosts = [];
const seen = new Set();
let stamp = "";
let matchCache = { key: "", list: [] };

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
  if (!isVisiblePost(post)) return false;
  if (state.source !== "all" && post.source !== state.source) return false;
  if (!state.q) return true;
  const hay = [post.title, post.excerpt, post.author, post.company].join("\n").toLowerCase();
  return hay.includes(state.q.toLowerCase());
}

function timeValue(post) {
  if (post._t != null) return post._t;
  const parsed = Date.parse(post.postedAt || post.firstSeenAt || "");
  post._t = Number.isFinite(parsed) ? parsed : 0;
  return post._t;
}

function matchingKey() {
  const last = allPosts[allPosts.length - 1];
  return `${state.source}|${state.q}|${allPosts.length}|${last?.id || 0}`;
}

function matchingAsc() {
  const key = matchingKey();
  if (matchCache.key === key) return matchCache.list;
  if (state.source === "all" && !state.q) {
    matchCache = { key, list: allPosts };
    return allPosts;
  }
  const list = [];
  for (const post of allPosts) {
    if (matches(post)) list.push(post);
  }
  matchCache = { key, list };
  return list;
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

const olderSentinel = document.createElement("div");
olderSentinel.className = "feed-older";
olderSentinel.hidden = true;

function syncOlderSentinel() {
  if (!allPosts.length) {
    olderSentinel.hidden = true;
    olderSentinel.textContent = "";
    return;
  }
  olderSentinel.hidden = false;
  if (state.loadingOlder) olderSentinel.textContent = "이전 글 불러오는 중…";
  else if (state.done) olderSentinel.textContent = "처음 글까지 다 봤습니다";
  else olderSentinel.textContent = `위로 올리면 이전 글 ${PAGE}개가 붙습니다`;
}

function renderAll(posts) {
  seen.clear();
  const fragment = document.createDocumentFragment();
  fragment.append(olderSentinel);
  for (const post of posts) {
    if (post.id > state.maxId) state.maxId = post.id;
    if (seen.has(post.id) || !matches(post)) continue;
    fragment.append(renderMsg(post, false));
    seen.add(post.id);
  }
  feed.replaceChildren(fragment);
  showEmpty();
  syncOlderSentinel();
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
    syncOlderSentinel();
    return;
  }
  const start = Math.max(0, index - PAGE);
  const older = asc.slice(start, index);
  state.loadingOlder = true;
  syncOlderSentinel();
  const beforeHeight = scroller.scrollHeight;
  const fragment = document.createDocumentFragment();
  for (const post of older) {
    if (seen.has(post.id)) continue;
    fragment.append(renderMsg(post, false));
    seen.add(post.id);
    if (post.id > state.maxId) state.maxId = post.id;
  }
  feed.insertBefore(fragment, olderSentinel.nextSibling);
  if (start === 0) state.done = true;
  scroller.scrollTop += scroller.scrollHeight - beforeHeight;
  state.loadingOlder = false;
  syncOlderSentinel();
  if (!state.done && olderSentinel.getBoundingClientRect().bottom > scroller.getBoundingClientRect().top + 8) {
    requestAnimationFrame(loadOlder);
  }
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
이유 근황 미국 한국 일본 중국 해외 느낌 생각 마음 이야기 얘기 본인 애들 미래 상황 문제
댓글 영상 사진 유튜브 유튭 링크 좌표 링크좌표 친구 회사 학교 시간 다들 저렇게 내가 보고 멋진 나가서 삭제직전
없음 같음 있음 얼마나 둘이
나솔 미방 미방분 여출 남출 다둥 다둥이 솔솔 몰표 몰표녀 여돌 남돌 솔로녀 솔로남 존버 억까 인싸 아싸 점메추`.split(/\s+/),
);
const SWEAR_WORDS = new Set(
  `존나 졸라 존내 좆나 씨발 시발 씨팔 시팔 씨벌 시벌 병신 븅신 병쉰 지랄 지럴 좆 좇 새끼 개새끼 미친 미쳤
꺼져 닥쳐 죽어 디질 뒤질 씹 보지 자지 걸레 창녀 창년 썅 니미 애미 애비 등신 호로 또라이 싸가지 개소리
좆밥 찌질 느금 느금마 염병 엠창 개년 개놈 개새 씨발롬 시발롬 환장 빡치 빡쳐 개자식 후레 쉬발 쉬벌 스발 슈발`.split(/\s+/),
);
const SWEAR_PARTS = ["씨발", "시발", "씨팔", "시팔", "씨벌", "시벌", "병신", "븅신", "지랄", "좆", "존나", "졸라", "새끼", "개새끼", "니미", "느금", "염병", "개소리", "쉬발", "쉬벌"];
const OFFTOPIC_TALK = ["근황", "미국", "일본", "중국", "해외"];
const SCREEN_PARTS = [
  "정치", "대통령", "민주당", "국민의힘", "국힘", "윤석열", "이재명", "문재인", "박근혜", "이명박",
  "한동훈", "조국", "이준석", "홍준표", "탄핵", "좌파", "우파", "여당", "야당", "국회", "김정은",
  "극우", "극좌", "친윤", "친문", "개딸", "보수", "선거",
  "가슴", "엉덩이", "슴가", "유방", "젖꼭지", "유두", "섹스", "몰카", "도촬", "불법촬영",
  "성희롱", "성추행", "성폭행", "성폭력", "성매매", "강간", "음란", "팬티", "속옷", "보빨", "호빠",
  "꼴리", "변태", "자위", "젖", "섹드립",
];
const GENERIC_AUTHORS = new Set(["", "ㅇㅇ", "ㅇㅇㅇ", "ㅁㅁ", "익명", "무명의 더쿠", "유튜브"]);
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

function isScreenedWord(word) {
  if (SCREEN_PARTS.some((part) => word.includes(part))) return true;
  if (word.includes("북한") && !word.includes("거북한")) return true;
  if (word.includes("진보") && !word.includes("사진")) return true;
  if (word.includes("야동") && !word.includes("야동생")) return true;
  return false;
}

function isSwearWord(word) {
  if (SWEAR_WORDS.has(word)) return true;
  return SWEAR_PARTS.some((part) => word.includes(part));
}

function isCountedWord(word, allowSwears) {
  if (/^\d+기$/.test(word)) return true;
  if (word.length < 2 || STOP_WORDS.has(word) || isScreenedWord(word)) return false;
  if (!allowSwears && isSwearWord(word)) return false;
  if (PRED_RE.test(word) || SHORT_RE.test(word)) return false;
  return true;
}

let floodStamp = "";
let floodTitles = new Set();

function floodTitle(post) {
  return `${post.source || ""}:${(post.title || "").replace(/\s+/g, " ").trim()}`;
}

function refreshFlood(posts) {
  const list = posts && posts.length > allPosts.length ? posts : allPosts;
  if (!list.length) return;
  const last = list[list.length - 1];
  const stamp = `${list.length}:${last?.id || 0}`;
  if (stamp === floodStamp) return;
  const counts = new Map();
  for (const post of list) {
    const key = floodTitle(post);
    if (key.endsWith(":")) continue;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  floodTitles = new Set();
  for (const [key, count] of counts) {
    if (count >= 4) floodTitles.add(key);
  }
  floodStamp = stamp;
}

function isFloodPost(post) {
  const key = floodTitle(post);
  if (key.endsWith(":")) return false;
  refreshFlood(allPosts);
  return floodTitles.has(key);
}

function isVisiblePost(post) {
  if (isFloodPost(post)) return false;
  const text = countedText(post);
  if (OFFTOPIC_TALK.some((part) => text.includes(part))) return false;
  for (const raw of text.match(WORD_RE) || []) {
    if (isScreenedWord(stemWord(raw))) return false;
  }
  return true;
}

function personKey(post) {
  const author = (post.author || "").trim();
  const ip = (post.ip || "").trim();
  const company = (post.company || "").trim();
  if (GENERIC_AUTHORS.has(author) && !ip && !company) return "";
  return `${post.source || ""}:${author}:${ip}:${company}`;
}

function countedText(post) {
  if (post.source === "yt") return post.title || "";
  return `${post.title || ""} ${post.excerpt || ""}`;
}

function wordCounts(posts, since, allowSwears) {
  const counts = new Map();
  const people = new Map();
  refreshFlood(posts);
  for (const post of posts) {
    if (!isVisiblePost(post)) continue;
    if (since && timeValue(post) < since) continue;
    const person = personKey(post) || `post:${post.source || ""}:${post.id}`;
    const seen = new Set();
    for (const raw of countedText(post).match(WORD_RE) || []) {
      const word = stemWord(raw);
      if (!isCountedWord(word, allowSwears)) continue;
      seen.add(word);
    }
    for (const word of seen) {
      let group = people.get(word);
      if (!group) {
        group = new Set();
        people.set(word, group);
      }
      if (group.has(person)) continue;
      group.add(person);
      counts.set(word, (counts.get(word) || 0) + 1);
    }
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ko"));
}

function applyQuery(word) {
  input.value = word;
  clearBtn.hidden = false;
  state.q = word;
  state.limit = PAGE;
  reload();
}

let cloudKey = "";
let cloudWords = [];
let cloudLayoutKey = "";

function renderCloud(posts) {
  const key = `${posts.length}:${posts[posts.length - 1]?.id || 0}`;
  if (key !== cloudKey) {
    cloudKey = key;
    cloudWords = wordCounts(posts).slice(0, 72).map(([word, count], index) => ({
      word,
      count,
      color: PASTELS[index % PASTELS.length],
    }));
    cloudLayoutKey = "";
  }
  const boxKey = `${cloudEl.clientWidth}x${cloudEl.clientHeight}`;
  if (cloudEl.clientWidth && boxKey !== cloudLayoutKey) layoutCloud();
}

const HEART_STEPS = 360;
const HEART_PTS = Array.from({ length: HEART_STEPS }, (_, index) => {
  const turn = (index / HEART_STEPS) * Math.PI * 2;
  return [
    16 * Math.sin(turn) ** 3,
    13 * Math.cos(turn) - 5 * Math.cos(2 * turn) - 2 * Math.cos(3 * turn) - Math.cos(4 * turn),
  ];
});
const HEART_LIMIT = HEART_PTS.reduce(
  (box, [x, y]) => ({
    minX: Math.min(box.minX, x),
    maxX: Math.max(box.maxX, x),
    minY: Math.min(box.minY, y),
    maxY: Math.max(box.maxY, y),
  }),
  { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity },
);

function rasterHeart(width, height) {
  const pad = 2;
  const spanX = HEART_LIMIT.maxX - HEART_LIMIT.minX;
  const spanY = HEART_LIMIT.maxY - HEART_LIMIT.minY;
  const fit = Math.min((width - pad * 2) / spanX, (height - pad * 2) / spanY);
  const originX = (width - spanX * fit) / 2;
  const originY = (height - spanY * fit) / 2;
  const poly = HEART_PTS.map(([x, y]) => [
    originX + (x - HEART_LIMIT.minX) * fit,
    originY + (HEART_LIMIT.maxY - y) * fit,
  ]);
  const mask = new Uint8Array(width * height);
  let top = height;
  let bottom = 0;
  for (let y = 0; y < height; y += 1) {
    const sampleY = y + 0.5;
    const crosses = [];
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const y1 = poly[j][1];
      const y2 = poly[i][1];
      if ((y1 > sampleY) === (y2 > sampleY)) continue;
      crosses.push(poly[j][0] + ((poly[i][0] - poly[j][0]) * (sampleY - y1)) / (y2 - y1));
    }
    crosses.sort((a, b) => a - b);
    for (let k = 0; k + 1 < crosses.length; k += 2) {
      const from = Math.max(0, Math.ceil(crosses[k]));
      const to = Math.min(width - 1, Math.floor(crosses[k + 1]));
      if (from <= to) {
        top = Math.min(top, y);
        bottom = Math.max(bottom, y);
      }
      const row = y * width;
      for (let x = from; x <= to; x += 1) mask[row + x] = 1;
    }
  }
  return { mask, top, bottom };
}

function heartFont(t, scale = 1) {
  let font;
  if (t < 0.16) font = 12 + t * 10;
  else if (t < 0.36) font = 14 + ((t - 0.16) / 0.2) * 17;
  else if (t < 0.5) font = 31 - ((t - 0.36) / 0.14) * 6;
  else if (t < 0.72) font = 24 - ((t - 0.5) / 0.22) * 11;
  else font = 12.5 - ((t - 0.72) / 0.28) * 2;
  return Math.max(10, Math.max(11, Math.min(32, font)) * scale);
}

function heartRuns(mask, width, y0, y1) {
  const runs = [];
  let start = -1;
  const yStart = Math.max(0, y0);
  const yEnd = Math.min(mask.length / width - 1, y1);
  for (let x = 0; x <= width; x += 1) {
    let solid = x < width;
    if (solid) {
      for (let y = yStart; y <= yEnd; y += 1) {
        if (!mask[y * width + x]) {
          solid = false;
          break;
        }
      }
    }
    if (solid && start < 0) start = x;
    if (!solid && start >= 0) {
      const from = start + 1;
      const to = x - 2;
      if (to - from >= 16) runs.push({ x0: from, x1: to, w: to - from });
      start = -1;
    }
  }
  return runs;
}

function heartBands(mask, width, top, bottom, scale) {
  const bands = [];
  let y = top;
  while (y < bottom - 8) {
    const t = (y - top) / Math.max(1, bottom - top);
    const font = heartFont(t, scale);
    const bandHeight = Math.round(font + 1);
    const y1 = Math.min(bottom, y + bandHeight);
    const runs = heartRuns(mask, width, y, y1).filter((run) => run.w >= Math.max(18, font * 1.82));
    if (!runs.length) {
      y += 2;
      continue;
    }
    bands.push({ y, y1, cy: (y + y1) / 2, font, runs });
    y = y1 + 1;
  }
  return bands;
}

function estimateWidth(word, font) {
  return Math.max(font, word.length * font * 0.94);
}

function assignHeart(words, bands) {
  const pool = words.slice();
  const rows = [];
  const order = bands
    .map((band, index) => index)
    .sort((a, b) => bands[b].font - bands[a].font || bands[a].y - bands[b].y);
  for (const bandIndex of order) {
    const band = bands[bandIndex];
    const gap = Math.max(2, band.font * 0.1);
    for (const run of band.runs) {
      const items = [];
      let used = 0;
      while (pool.length) {
        let pick = -1;
        const limit = Math.min(pool.length, 6);
        for (let index = 0; index < limit; index += 1) {
          const width = estimateWidth(pool[index].word, band.font);
          if (used + (items.length ? gap : 0) + width <= run.w + 1) {
            pick = index;
            break;
          }
        }
        if (pick < 0) break;
        const item = pool.splice(pick, 1)[0];
        items.push(item);
        used += (items.length > 1 ? gap : 0) + estimateWidth(item.word, band.font);
      }
      if (items.length) rows.push({ band, run, gap, font: band.font, items });
    }
  }
  return rows;
}

function layoutCloud() {
  if (!cloudWords.length) {
    cloudEl.replaceChildren();
    cloudLayoutKey = `${cloudEl.clientWidth}x${cloudEl.clientHeight}`;
    return;
  }
  const width = cloudEl.clientWidth;
  const height = cloudEl.clientHeight;
  if (width < 40 || height < 40) return;
  cloudLayoutKey = `${width}x${height}`;
  const { mask, top, bottom } = rasterHeart(width, height);
  if (bottom <= top) return;
  const scale = Math.min(1, width / 240, height / 240);
  const bands = heartBands(mask, width, top, bottom, scale);
  const rows = assignHeart(cloudWords, bands);
  const buttons = [];
  for (const row of rows) {
    row.buttons = row.items.map((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = item.word;
      button.title = `${numberFormat.format(item.count)}번`;
      button.style.color = item.color;
      button.style.fontSize = `${row.font.toFixed(1)}px`;
      button.addEventListener("click", () => applyQuery(item.word));
      buttons.push(button);
      return button;
    });
  }
  cloudEl.replaceChildren(...buttons);
  for (const row of rows) {
    let guard = 0;
    while (guard < 3) {
      guard += 1;
      const widths = row.buttons.map((button) => button.offsetWidth);
      const sum = widths.reduce((total, item) => total + item, 0) + row.gap * Math.max(0, widths.length - 1);
      if (sum <= row.run.w + 0.5 || row.buttons.length === 1) {
        if (sum > row.run.w + 0.5) {
          const scale = row.run.w / Math.max(1, widths[0]);
          row.buttons[0].style.fontSize = `${Math.max(10, row.font * scale).toFixed(1)}px`;
        }
        break;
      }
      const extra = row.buttons.pop();
      extra.remove();
    }
  }
  for (const row of rows) {
    const widths = row.buttons.map((button) => button.offsetWidth);
    const sum = widths.reduce((total, item) => total + item, 0) + row.gap * Math.max(0, widths.length - 1);
    let x = row.run.x0 + Math.max(0, row.run.w - sum) / 2;
    row.buttons.forEach((button, index) => {
      const wordWidth = widths[index];
      button.style.left = `${x + wordWidth / 2}px`;
      button.style.top = `${row.band.cy}px`;
      x += wordWidth + row.gap;
    });
  }
}

if (document.fonts?.ready) {
  document.fonts.ready.then(() => {
    cloudLayoutKey = "";
    if (cloudWords.length && cloudEl?.clientWidth) layoutCloud();
  });
}

new ResizeObserver(() => {
  if (!cloudWords.length) return;
  const boxKey = `${cloudEl.clientWidth}x${cloudEl.clientHeight}`;
  if (cloudEl.clientWidth && boxKey !== cloudLayoutKey) layoutCloud();
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
  const ranked = wordCounts(posts, now - 4 * 60 * 60 * 1000, true).slice(0, 10);
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
    const when = source === "yt" ? board.youtubeUpdatedAt || board.updatedAt : board.updatedAt;
    detail.textContent = relative(when);
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
  posts.sort((a, b) => timeValue(a) - timeValue(b) || a.id - b.id);
  allPosts.splice(0, allPosts.length, ...posts);
  matchCache = { key: "", list: [] };
  floodStamp = "";
}

async function pull() {
  const board = await loadBoard();
  if (!board) return;
  const posts = board.posts || [];
  if (!state.ready) {
    replacePosts(posts);
    renderStatus(board);
    stamp = board.updatedAt || "";
    state.ready = true;
    reload();
    return;
  }
  renderStatus(board);
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
          renderStatus({ ...meta, posts: allPosts, youtubeUpdatedAt: ytStamp });
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
  const youtubeUpdatedAt = extra?.updatedAt || board.youtubeUpdatedAt || "";
  if (!extra?.posts?.length) return { ...board, youtubeUpdatedAt };
  const posts = [...(board.posts || [])];
  const seen = new Set(posts.map((post) => `${post.source}:${post.externalId}`));
  let next = posts.reduce((max, post) => Math.max(max, post.id || 0), 0);
  for (const post of extra.posts) {
    if (post.source !== "yt" || seen.has(`yt:${post.externalId}`)) continue;
    next += 1;
    seen.add(`yt:${post.externalId}`);
    posts.push({ ...post, id: next });
  }
  return { ...board, posts, youtubeUpdatedAt };
}

function scheduleSearch() {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    state.q = input.value.trim();
    state.limit = PAGE;
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
    state.limit = PAGE;
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
  state.limit = PAGE;
  input.focus();
  reload();
});
document.querySelector("#composer").addEventListener("submit", (event) => {
  event.preventDefault();
  state.q = input.value.trim();
  state.limit = PAGE;
  reload();
});

jump.addEventListener("click", scrollToBottom);

const railToggle = document.querySelector("#rail-toggle");
const appEl = document.querySelector(".app");
function setRailOpen(open) {
  appEl.classList.toggle("rail-closed", !open);
  railToggle.setAttribute("aria-expanded", String(open));
  document.querySelector("#rail-toggle-label").textContent = open ? "옆 화면 접기" : "옆 화면 열기";
  document.dispatchEvent(new Event("board-chrome"));
}
railToggle.addEventListener("click", () => setRailOpen(appEl.classList.contains("rail-closed")));

scroller.addEventListener("scroll", () => {
  const room = overflow();
  state.pinned = room <= 8 || distanceFromBottom() < 72;
  if (state.pinned) state.pending = 0;
  updateJump();
});

if (window.IntersectionObserver) {
  new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) loadOlder();
  }, { root: scroller, rootMargin: "160px 0px 0px 0px" }).observe(olderSentinel);
} else {
  scroller.addEventListener("scroll", () => {
    if (overflow() > 0 && scroller.scrollTop < 64) loadOlder();
  });
}

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

const PAIR_COLORS = {
  youngsoo: "#9eecf5",
  youngho: "#a8f0e0",
  youngsik: "#d4c4ff",
  youngchul: "#ffe0a3",
  gwangsoo: "#ffc4d4",
  sangchul: "#b7d0ff",
  youngsook: "#ffb4c8",
  jeongsook: "#fff3a8",
  soonja: "#b8f2c2",
  youngja: "#ffd0a8",
  oksoon: "#e4c6ff",
  hyunsook: "#ffb8b0",
};
const RANK_LABEL = { 1: "1순위", 2: "2지망", 3: "3지망", 0: "관심" };
const svgNS = "http://www.w3.org/2000/svg";
const pairBoard = document.querySelector("#pair-board");
const pairLines = document.querySelector("#pair-lines");
const pairFocus = document.querySelector("#pair-focus");
let pairData = null;
let pairPinned = "";
let pairRestoreRail = false;

function pairPeople() {
  return [...(pairData?.men || []), ...(pairData?.women || [])];
}

function pairPerson(id) {
  return pairPeople().find((person) => person.id === id);
}

const PAIR_TYPE_LABEL = { dark: "악", normal: "노말", fairy: "페어리" };
const PAIR_TYPE_NOTE = { dark: "악평", normal: "무난", fairy: "호평" };
const TYPE_FILL = { dark: "#5a4a6e", normal: "#a8a878", fairy: "#ee99ac" };

function personTypes(person) {
  const list = Array.isArray(person.types) && person.types.length ? person.types : [person.type];
  return list.filter((kind) => PAIR_TYPE_LABEL[kind]);
}

// Pokémon-style type emblems: a tinted disc with the type's symbol knocked out of it.
function typeIcon(kind) {
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", "0 0 20 20");
  svg.setAttribute("class", "type-logo");
  svg.setAttribute("aria-hidden", "true");
  const disc = document.createElementNS(svgNS, "circle");
  disc.setAttribute("cx", "10");
  disc.setAttribute("cy", "10");
  disc.setAttribute("r", "10");
  disc.setAttribute("fill", TYPE_FILL[kind] || TYPE_FILL.normal);
  svg.append(disc);
  const mark = document.createElementNS(svgNS, "path");
  mark.setAttribute("fill", "#fff");
  if (kind === "dark") {
    mark.setAttribute("d", "M10.6 3.2a6.8 6.8 0 1 0 5.9 10.2 5.4 5.4 0 0 1-5.9-10.2Z");
  } else if (kind === "fairy") {
    mark.setAttribute("d", "M10 2.6c.7 3.5 1.9 5 5.1 5.5-3.3 1-4.5 2.4-5.1 6.6-.6-4.2-1.8-5.6-5.1-6.6 3.2-.5 4.4-2 5.1-5.5ZM14.9 12.2c.3 1.4.8 2 2.1 2.3-1.3.4-1.8 1-2.1 2.6-.3-1.6-.8-2.2-2.1-2.6 1.3-.3 1.8-.9 2.1-2.3Z");
  } else {
    mark.setAttribute("fill-rule", "evenodd");
    mark.setAttribute("d", "M10 3.2a6.8 6.8 0 1 1 0 13.6 6.8 6.8 0 0 1 0-13.6Zm0 3.1a3.7 3.7 0 1 0 0 7.4 3.7 3.7 0 0 0 0-7.4Z");
  }
  svg.append(mark);
  return svg;
}

function typeMark(kind, note) {
  const mark = document.createElement("span");
  mark.className = "type-mark";
  mark.dataset.type = kind;
  mark.style.setProperty("--fill", TYPE_FILL[kind] || TYPE_FILL.normal);
  const label = document.createElement("span");
  label.textContent = note ? `${PAIR_TYPE_LABEL[kind]} · ${PAIR_TYPE_NOTE[kind]}` : PAIR_TYPE_LABEL[kind];
  mark.append(typeIcon(kind), label);
  return mark;
}

function laneOffsets(links) {
  const groups = new Map();
  const put = (key, link, field) => {
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({ link, field });
  };
  for (const link of links) {
    put(`from:${link.from}`, link, "fromLane");
    put(`to:${link.to}`, link, "toLane");
  }
  for (const group of groups.values()) {
    group.forEach((item, index) => {
      item.link[item.field] = index - (group.length - 1) / 2;
    });
  }
}

function curvePoint(t, p0, p1, p2, p3) {
  const u = 1 - t;
  return u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3;
}

let pairLayouts = new Map();
let pairLayoutKey = "";
let pairBase = { w: 80, h: 100 };
const PAIR_CARD_ASPECT = 58 / 72;

function pairSide(id) {
  return (pairData?.men || []).some((person) => person.id === id) ? "men" : "women";
}

function pairNear(id) {
  const near = new Set([id]);
  for (const link of pairData.links) {
    if (link.from === id || link.to === id) {
      near.add(link.from);
      near.add(link.to);
    }
  }
  return near;
}

function boardColumns(width, height) {
  const gutter = Math.max(88, Math.min(width * 0.22, 240));
  const colW = (width - gutter) / 2;
  return {
    men: { x: 0, y: 0, w: colW, h: height },
    women: { x: width - colW, y: 0, w: colW, h: height },
  };
}

function restingBase(width, height) {
  const col = boardColumns(width, height).men;
  const gap = 8;
  let cardH = (height - gap * 5) / 6;
  let cardW = cardH * PAIR_CARD_ASPECT;
  if (cardW > col.w) {
    cardW = col.w;
    cardH = cardW / PAIR_CARD_ASPECT;
  }
  return { w: Math.max(46, cardW), h: Math.max(58, cardH) };
}

function stackBoxes(people, side, bounds, base) {
  const boxes = {};
  const count = people.length;
  if (!count) return boxes;
  const gap = count > 1 ? 8 : 0;
  const aspect = base.w / base.h;
  let cardH = (bounds.h - gap * (count - 1)) / count;
  let cardW = cardH * aspect;
  if (cardW > bounds.w) {
    cardW = bounds.w;
    cardH = cardW / aspect;
  }
  const stackH = cardH * count + gap * (count - 1);
  let y = bounds.y + Math.max(0, (bounds.h - stackH) / 2);
  const scale = cardW / base.w;
  for (const person of people) {
    const x = side === "men" ? bounds.x + bounds.w - cardW : bounds.x;
    boxes[person.id] = { x, y, scale, opacity: 1 };
    y += cardH + gap;
  }
  return boxes;
}

function layoutFor(focusId, width, height, base) {
  const columns = boardColumns(width, height);
  const near = focusId ? pairNear(focusId) : null;
  const rest = {
    ...stackBoxes(pairData.men, "men", columns.men, base),
    ...stackBoxes(pairData.women, "women", columns.women, base),
  };
  if (!focusId) return { boxes: rest };
  const boxes = {};
  for (const [id, box] of Object.entries(rest)) boxes[id] = { ...box, opacity: 0 };
  const men = pairData.men.filter((person) => near.has(person.id));
  const women = pairData.women.filter((person) => near.has(person.id));
  Object.assign(boxes, stackBoxes(men, "men", columns.men, base), stackBoxes(women, "women", columns.women, base));
  return { boxes };
}

function pairCard(person) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "pair-card";
  button.dataset.id = person.id;
  button.style.setProperty("--glow", PAIR_COLORS[person.id] || "#ffd0e0");
  const photo = document.createElement("img");
  photo.src = new URL(person.photo, document.baseURI).href;
  photo.alt = "";
  const name = document.createElement("strong");
  name.textContent = person.name;
  button.append(photo, name);
  button.addEventListener("pointerenter", (event) => {
    if (document.documentElement.classList.contains("mobile")) return;
    if (event.pointerType !== "mouse") return;
    highlightPairLines(person.id);
  });
  button.addEventListener("pointerleave", (event) => {
    if (event.pointerType !== "mouse") return;
    highlightPairLines("");
  });
  button.addEventListener("click", () => pinPair(person.id));
  return button;
}

function pokeCard(person) {
  const types = personTypes(person);
  const root = document.createElement("article");
  root.className = "poke";
  root.dataset.type = types.length > 1 ? "dual" : types[0] || "normal";
  if (types.length > 1) {
    root.style.setProperty("--tone-a", TYPE_FILL[types[0]]);
    root.style.setProperty("--tone-b", TYPE_FILL[types[1]]);
  }
  const head = document.createElement("div");
  head.className = "poke-head";
  const name = document.createElement("strong");
  name.textContent = person.name;
  const hp = document.createElement("span");
  hp.className = "poke-hp";
  const num = document.createElement("b");
  num.textContent = person.year ? String(person.year).slice(2) : "??";
  const unit = document.createElement("small");
  unit.textContent = person.year ? "년생" : "비공개";
  hp.append(num, unit);
  head.append(name, hp);
  const type = document.createElement("p");
  type.className = "poke-type";
  const badges = document.createElement("span");
  badges.className = "poke-badges";
  badges.append(...types.map((kind) => typeMark(kind)));
  const job = document.createElement("span");
  job.className = "poke-job";
  job.textContent = person.job || "직업 비공개";
  type.append(badges, job);
  const frame = document.createElement("div");
  frame.className = "poke-photo";
  const img = document.createElement("img");
  img.src = new URL(person.photo, document.baseURI).href;
  img.alt = "";
  frame.append(img);
  const moves = document.createElement("div");
  moves.className = "poke-moves";
  for (const row of [
    ["나이", person.year ? `${person.year}년생` : ""],
    ["취미", person.hobby || ""],
    ["가족", person.note || ""],
  ]) {
    const move = document.createElement("p");
    move.className = "poke-move";
    const label = document.createElement("b");
    label.textContent = row[0];
    const value = document.createElement("span");
    value.textContent = row[1] || "비공개";
    if (!row[1]) value.className = "pair-secret";
    move.append(label, value);
    moves.append(move);
  }
  const foot = document.createElement("footer");
  foot.className = "poke-foot";
  const set = document.createElement("span");
  set.textContent = "34기";
  const rarity = document.createElement("span");
  rarity.className = "poke-rarity";
  rarity.textContent = "♥";
  foot.append(set, rarity);
  const holo = document.createElement("span");
  holo.className = "poke-holo";
  holo.setAttribute("aria-hidden", "true");
  root.append(head, type, frame, moves, foot, holo);
  return root;
}

function renderPairing(data) {
  pairData = data;
  const label = `${data.label} · ${data.asOf}`;
  document.querySelector("#pair-kicker").textContent = label;
  document.querySelector("#profile-kicker").textContent = label;
  document.querySelector("#pair-men").replaceChildren(...data.men.map(pairCard));
  document.querySelector("#pair-women").replaceChildren(...data.women.map(pairCard));
  document.querySelector("#poke-grid").replaceChildren(...pairPeople().map(pokeCard));
  document.querySelector("#type-legend").replaceChildren(
    ...["dark", "normal", "fairy"].map((kind) => {
      const item = document.createElement("li");
      item.append(typeMark(kind, true));
      return item;
    }),
  );
  pairLayoutKey = "";
  if (!document.querySelector("#pairing").hidden) ensurePairLayouts();
  document.dispatchEvent(new Event("board-ready"));
}

function highlightPairLines(id) {
  const active = pairLines.querySelector("g.on");
  if (!active) return;
  active.classList.toggle("hotting", Boolean(id));
  for (const node of active.querySelectorAll(".pair-link, .pair-heart")) {
    const owners = [node.dataset.from, node.dataset.to, ...(node.dataset.pair || "").split("|")];
    node.classList.toggle("hot", Boolean(id) && owners.includes(id));
  }
}

function edgePoint(box, side) {
  const width = pairBase.w * box.scale;
  const height = pairBase.h * box.scale;
  return {
    x: side === "men" ? box.x + width : box.x,
    y: box.y + height / 2,
  };
}

function paintPairLines(width, height) {
  pairLines.setAttribute("viewBox", `0 0 ${width} ${height}`);
  pairLines.replaceChildren();
  const narrow = width < 700;
  const size = narrow ? 12 : 18;
  const wing = narrow ? 5.4 : 8;
  const heartScale = narrow ? 2.4 : 3.4;
  for (const [key, layout] of pairLayouts) {
    const group = document.createElementNS(svgNS, "g");
    group.dataset.focus = key;
    if (key === (pairPinned || "rest")) group.setAttribute("class", "on");
    const links = pairData.links
      .filter((link) => layout.boxes[link.from]?.opacity && layout.boxes[link.to]?.opacity)
      .map((link) => ({ ...link }));
    laneOffsets(links);
    // A heart only when both sides put each other first (solid line meets solid line).
    const mutual = new Set();
    for (const link of links) {
      if (link.rank !== 1) continue;
      if (links.some((other) => other.rank === 1 && other.from === link.to && other.to === link.from)) {
        mutual.add([link.from, link.to].sort().join("|"));
      }
    }
    const lane = Math.min(16, pairBase.h * 0.24);
    const drawnHearts = new Set();
    for (const link of links) {
      const fromSide = pairSide(link.from);
      const toSide = pairSide(link.to);
      const start = edgePoint(layout.boxes[link.from], fromSide);
      const end = edgePoint(layout.boxes[link.to], toSide);
      const fromLeft = start.x < end.x;
      const y1 = start.y + link.fromLane * lane;
      const y2 = end.y + link.toLane * lane;
      const x1 = fromLeft ? start.x + 2 : start.x - 2;
      const x2 = fromLeft ? end.x - 2 : end.x + 2;
      const c1x = x1 + (x2 - x1) * 0.38;
      const c2x = x1 + (x2 - x1) * 0.62;
      const c1y = y1 + (y2 - y1) * 0.18;
      const c2y = y2 - (y2 - y1) * 0.18;
      const dx = x2 - c2x;
      const dy = y2 - c2y;
      const len = Math.hypot(dx, dy) || 1;
      const ux = dx / len;
      const uy = dy / len;
      const color = PAIR_COLORS[link.from] || "#ffb4c8";
      const solid = link.rank === 1;
      const path = document.createElementNS(svgNS, "path");
      path.setAttribute("d", `M ${x1} ${y1} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${x2 - ux * size} ${y2 - uy * size}`);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", color);
      path.setAttribute("stroke-linecap", "round");
      path.setAttribute("stroke-width", solid ? "1.25" : "1.15");
      if (!solid) path.setAttribute("stroke-dasharray", "0.1 5.2");
      path.dataset.from = link.from;
      path.dataset.to = link.to;
      path.setAttribute("class", "pair-link");
      group.append(path);
      const head = document.createElementNS(svgNS, "polygon");
      head.setAttribute("points", [
        `${x2},${y2}`,
        `${x2 - ux * size - uy * wing},${y2 - uy * size + ux * wing}`,
        `${x2 - ux * size + uy * wing},${y2 - uy * size - ux * wing}`,
      ].join(" "));
      head.setAttribute("fill", color);
      head.dataset.from = link.from;
      head.dataset.to = link.to;
      head.setAttribute("class", "pair-link");
      group.append(head);
      const heartKey = [link.from, link.to].sort().join("|");
      if (mutual.has(heartKey) && !drawnHearts.has(heartKey)) {
        drawnHearts.add(heartKey);
        const mx = curvePoint(0.5, x1, c1x, c2x, x2);
        const my = curvePoint(0.5, y1, c1y, c2y, y2);
        const heart = document.createElementNS(svgNS, "path");
        heart.setAttribute("d", "M0 1.6C0 .4 1.05-.3 2.05.55 2.55-.45 4.05.15 4.05 1.55 4.05 3.15 2.15 4.25 0 5.7-2.15 4.25-4.05 3.15-4.05 1.55-4.05.15-2.55-.45-2.05.55-1.05-.3 0 .4 0 1.6Z");
        heart.setAttribute("transform", `translate(${mx} ${my}) scale(${heartScale}) translate(0 -2.55)`);
        heart.setAttribute("fill", "#ff6d93");
        heart.setAttribute("stroke", "#14080d");
        heart.setAttribute("stroke-width", String(1.1 / heartScale));
        heart.setAttribute("class", "pair-heart");
        heart.dataset.pair = heartKey;
        group.append(heart);
      }
    }
    pairLines.append(group);
  }
}

function applyPairLayout(id, animate) {
  const layout = pairLayouts.get(id || "rest");
  if (!layout) return;
  pairBoard.classList.toggle("anim", Boolean(animate));
  pairBoard.classList.toggle("focusing", Boolean(id));
  pairBoard.dataset.focus = id || "";
  for (const card of pairBoard.querySelectorAll(".pair-card")) {
    const box = layout.boxes[card.dataset.id];
    card.style.transform = `translate3d(${box.x}px, ${box.y}px, 0) scale(${box.scale})`;
    card.style.opacity = String(box.opacity);
    card.style.pointerEvents = box.opacity ? "auto" : "none";
    card.classList.toggle("near", Boolean(id) && box.opacity > 0);
    card.classList.toggle("lit", card.dataset.id === id);
    card.setAttribute("aria-pressed", String(card.dataset.id === id));
  }
  for (const group of pairLines.querySelectorAll("g")) {
    group.classList.toggle("on", group.dataset.focus === (id || "rest"));
  }
}

function ensurePairLayouts() {
  const rect = pairBoard.getBoundingClientRect();
  if (rect.width < 40 || rect.height < 40) return;
  const key = `${Math.round(rect.width)}x${Math.round(rect.height)}`;
  if (key === pairLayoutKey) return;
  pairLayoutKey = key;
  pairBase = restingBase(rect.width, rect.height);
  pairBoard.style.setProperty("--pair-w", `${pairBase.w}px`);
  pairBoard.style.setProperty("--pair-h", `${pairBase.h}px`);
  pairLayouts = new Map([["rest", layoutFor("", rect.width, rect.height, pairBase)]]);
  for (const person of pairPeople()) {
    pairLayouts.set(person.id, layoutFor(person.id, rect.width, rect.height, pairBase));
  }
  paintPairLines(rect.width, rect.height);
  applyPairLayout(pairPinned, false);
}

function focusCaption(id) {
  if (!id) {
    pairFocus.textContent = "";
    return;
  }
  const person = pairPerson(id);
  const outgoing = pairData.links.filter((link) => link.from === id);
  const incoming = pairData.links.filter((link) => link.to === id);
  const phrase = (link, toward) => {
    const other = pairPerson(toward ? link.to : link.from);
    return `${RANK_LABEL[link.rank] || ""} ${other?.name || ""}`.trim();
  };
  const parts = [`${person?.name || ""}`];
  if (outgoing.length) parts.push(outgoing.map((link) => phrase(link, true)).join(" · "));
  if (incoming.length) parts.push(`받은 마음 ${incoming.map((link) => phrase(link, false)).join(" · ")}`);
  pairFocus.textContent = parts.join("  ·  ");
}

function pinPair(id, options = {}) {
  if (options.force) pairPinned = id || "";
  else pairPinned = pairPinned === id ? "" : id;
  focusCaption(pairPinned);
  ensurePairLayouts();
  applyPairLayout(pairPinned, true);
  document.dispatchEvent(new Event("board-chrome"));
}

function setStageView(name) {
  const stage = document.querySelector(".stage");
  stage.classList.toggle("show-pair", name === "pair");
  stage.classList.toggle("show-profile", name === "profile");
  document.querySelector("#tab-feed").setAttribute("aria-selected", String(name === "feed"));
  document.querySelector("#tab-profile").setAttribute("aria-selected", String(name === "profile"));
  document.querySelector("#tab-pair").setAttribute("aria-selected", String(name === "pair"));
  document.querySelector("#pairing").hidden = name !== "pair";
  document.querySelector("#profiles").hidden = name !== "profile";
  const mobile = document.documentElement.classList.contains("mobile");
  const narrow = window.matchMedia("(max-width: 860px)").matches;
  const sideView = name === "pair" || name === "profile";
  if (!mobile && sideView && narrow && !appEl.classList.contains("rail-closed")) {
    pairRestoreRail = true;
    setRailOpen(false);
  } else if (!mobile && !sideView && pairRestoreRail) {
    pairRestoreRail = false;
    setRailOpen(true);
  }
  const hash = name === "pair" ? "#pairing" : name === "profile" ? "#profile" : "";
  const next = `${location.pathname}${location.search}${hash}`;
  if (`${location.pathname}${location.search}${location.hash}` !== next && !mobile) history.replaceState(null, "", next);
  document.dispatchEvent(new Event("board-chrome"));
  if (name === "pair") requestAnimationFrame(() => ensurePairLayouts());
}

document.querySelector("#tab-feed").addEventListener("click", () => setStageView("feed"));
document.querySelector("#tab-profile").addEventListener("click", () => setStageView("profile"));
document.querySelector("#tab-pair").addEventListener("click", () => setStageView("pair"));
new ResizeObserver(() => {
  const pairing = document.querySelector("#pairing");
  if (pairing.hidden) return;
  if (document.documentElement.classList.contains("mobile")) {
    ensurePairLayouts();
    return;
  }
  const narrow = window.matchMedia("(max-width: 860px)").matches;
  if (narrow && !appEl.classList.contains("rail-closed")) {
    pairRestoreRail = true;
    setRailOpen(false);
  }
  ensurePairLayouts();
}).observe(pairBoard);

fetch(new URL("data/pairing.json", document.baseURI))
  .then((response) => response.json())
  .then((data) => {
    renderPairing(data);
    if (location.hash === "#pairing") setStageView("pair");
    else if (location.hash === "#profile") setStageView("profile");
  })
  .catch(() => {});
