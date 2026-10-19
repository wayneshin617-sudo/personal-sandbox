/* 34기 본방만 남기고 나솔사계·정치·성적 글을 걸러 낸다. app/filters.py 와 같은 규칙. */
(function (root) {
  const CURRENT_SEASON = 34;
  const CURRENT_MARKERS = ["34기", "34기수", "이번기수", "현기수", "현재기수", "이번회차"];
  const CURRENT_CAST = ["영수", "영호", "영식", "영철", "광수", "상철", "영숙", "정숙", "순자", "영자", "옥순", "현숙"];
  const SAGYE_SHOW = [
    "나솔사계", "솔로민박", "사계민박", "그후사랑은계속된다", "사랑은계속된다",
    "사계데이트권", "슈퍼데이트권", "나는solo그후", "나는솔로그후",
  ];
  const SAGYE_FLOWERS = ["국화", "튤립", "용담", "백합", "수선화", "라벤더", "프리지아"];
  const MISTER_SURNAMES = [
    "김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신",
    "권", "황", "안", "송", "류", "유", "홍", "전", "고", "문", "손", "양", "배", "백",
    "허", "남", "심", "노", "하", "곽", "성", "차", "주", "우", "구", "민", "진", "나",
    "지", "엄", "채", "원", "천", "방", "공", "현", "함", "변", "염", "여", "추", "도",
    "석", "선", "설", "마", "길", "연", "표", "명", "기", "반", "왕", "금", "옥", "육",
    "인", "맹", "제갈", "사공", "선우", "남궁", "독고", "황보",
  ];
  const MISTER_SHORT = [
    "미서", "미조", "미최", "미강", "미윤", "미김", "미한", "미권", "미차", "미공",
    "미제갈", "미오", "미박", "미이", "미정", "미임", "미장", "미신", "미홍",
  ];
  const MISTER_NICKS = ["미조햄", "미서햄", "미지햄", "미공햄", "미차햄", "미최햄"];
  const SAGYE_OK_SEASONS = [
    4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
    21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 35, 36, 37, 38,
  ];
  const POLITICAL = [
    "정치", "대통령", "민주당", "국민의힘", "국힘", "윤석열", "이재명", "문재인", "박근혜",
    "이명박", "한동훈", "조국", "이준석", "홍준표", "탄핵", "좌파", "우파", "여당", "야당",
    "국회", "김정은", "극우", "극좌", "친윤", "친문", "개딸", "보수", "선거",
  ];
  const SEXUAL = [
    "가슴", "엉덩이", "슴가", "유방", "젖꼭지", "유두", "섹스", "몰카", "도촬", "불법촬영",
    "성희롱", "성추행", "성폭행", "성폭력", "성매매", "강간", "음란", "팬티", "속옷", "보빨",
    "호빠", "꼴리", "변태", "자위", "섹드립",
  ];
  const SWEARS = [
    "존나", "졸라", "존내", "좆나", "씨발", "시발", "씨팔", "시팔", "씨벌", "시벌",
    "병신", "븅신", "병쉰", "지랄", "지럴", "좆", "좇", "새끼", "개새끼", "미친",
    "꺼져", "닥쳐", "씹", "보지", "자지", "걸레", "창녀", "창년", "썅", "니미",
    "애미", "등신", "호로", "또라이", "싸가지", "개소리", "좆밥", "느금", "느금마",
    "염병", "엠창", "개년", "개놈", "개새", "쉬발", "쉬벌", "스발", "슈발",
  ];
  const SWEAR_JAMO = ["ㅅㅂ", "ㅆㅂ", "ㅅㅍ", "ㅂㅅ", "ㅈㄹ"];

  const KEEP_RE = /[^\w가-힣ㄱ-ㅎㅏ-ㅣ\u1100-\u11ff0-9]+/g;
  const CHOSEONG = {
    "ᄀ": "ㄱ", "ᄁ": "ㄲ", "ᄂ": "ㄴ", "ᄃ": "ㄷ", "ᄄ": "ㄸ", "ᄅ": "ㄹ", "ᄆ": "ㅁ",
    "ᄇ": "ㅂ", "ᄈ": "ㅃ", "ᄉ": "ㅅ", "ᄊ": "ㅆ", "ᄋ": "ㅇ", "ᄌ": "ㅈ", "ᄍ": "ㅉ",
    "ᄎ": "ㅊ", "ᄏ": "ㅋ", "ᄐ": "ㅌ", "ᄑ": "ㅍ", "ᄒ": "ㅎ",
  };
  const BLOCKED_YT_IDS = [
    "qpUKcCsjHSI", "UT5GGHnjccE", "1vmMzTbRgHg", "Ny9RNTVLIk4", "RFTVQWZ0W4Y", "MEMWkVB_fJM",
  ];
  const BLOCKED_YT_TITLE_MARKS = ["직장동료 지인 등판", "사내 빌런 폭로", "지인폭로", "직장 동료 학창시절"];
  const YT_ID_RE = /[?&]v=([\w-]+)/;

  const CAST_ALT = CURRENT_CAST.join("|");
  const OK_ALT = SAGYE_OK_SEASONS.join("|");
  const SUR_ALT = MISTER_SURNAMES.slice().sort((a, b) => b.length - a.length).join("|");
  const CURRENT_CAST_RE = new RegExp(`34(?:기)?(?:${CAST_ALT})`);
  const OLD_CAST_RE = new RegExp(`(?<![0-9])((?:1[0-9]|2[0-9]|3[0-3]|3[5-8]))(?:기)?(?:${CAST_ALT})`);
  const OLD_CAST_KI_RE = new RegExp(`(?<![0-9가-힣])([4-9])기(?:${CAST_ALT})`);
  const OK_RE = new RegExp(`(${OK_ALT})기?옥순?`);
  const SOON_RE = new RegExp(`(${OK_ALT})기?순자?`);
  const MISTER_SURNAME_RE = new RegExp(`미스터(?:${SUR_ALT})`);

  function normalize(text) {
    return String(text || "")
      .normalize("NFKC")
      .toLowerCase()
      .replace(/[\u200b\u200c\u200d]/g, "")
      .replace(KEEP_RE, "")
      .replace(/[\u1100-\u1112]/g, (ch) => CHOSEONG[ch] || ch);
  }

  function fold(text) {
    return normalize(text).replace(/\d+/g, "");
  }

  function plain(text) {
    return fold(text).replace(/[ㄱ-ㅎㅏ-ㅣ]/g, "");
  }

  function youtubeId(post) {
    if (!post || typeof post === "string") return "";
    if (post.video_id) return String(post.video_id);
    const hit = String(post.url || "").match(YT_ID_RE);
    return hit ? hit[1] : "";
  }

  function skipYoutubeTitle(title) {
    const text = String(title || "");
    const tags = text.match(/#\s*나는솔로/gi) || [];
    if (tags.length >= 3) return true;
    const compact = text.replace(/\s+/g, "");
    return BLOCKED_YT_TITLE_MARKS.some((mark) => compact.includes(mark.replace(/\s+/g, "")));
  }

  function skipYoutubeVideo(video) {
    if (!video) return false;
    if (BLOCKED_YT_IDS.includes(video.video_id || youtubeId(video))) return true;
    return skipYoutubeTitle(video.title || video.excerpt || "");
  }

  function isBlockedYoutube(post) {
    if (!post || typeof post === "string") return false;
    if (post.video_id) return skipYoutubeVideo(post);
    if ((post.source || "") !== "yt") return false;
    if (BLOCKED_YT_IDS.includes(youtubeId(post))) return true;
    return skipYoutubeTitle(post.excerpt || "");
  }

  function postText(post) {
    if (!post) return "";
    if (typeof post === "string") return post;
    const title = post.title || "";
    if ((post.source || "") === "yt") return title;
    return `${title} ${post.excerpt || ""}`;
  }

  function hasCurrentSeason(compact) {
    if (CURRENT_MARKERS.some((marker) => compact.includes(marker))) return true;
    return CURRENT_CAST_RE.test(compact);
  }

  function misterShortHit(value) {
    const cleaned = value.replaceAll("이미지", "");
    for (const nick of MISTER_NICKS) {
      if (cleaned.includes(nick)) return nick;
    }
    for (const short of MISTER_SHORT) {
      if (cleaned.includes(short)) return short;
    }
    if (/(?<![가-힣])미지/.test(cleaned)) return "미지";
    const probe = cleaned.replaceAll("취미나", "").replaceAll("재미나", "").replaceAll("의미나", "");
    if (probe.includes("미나")) return "미나";
    return "";
  }

  function sagyeReason(text) {
    const compact = normalize(text);
    const folded = plain(text);
    if (!compact) return "";
    for (const kw of SAGYE_SHOW) {
      if (folded.includes(kw)) return kw;
    }
    if (folded.includes("사계")) return "사계";
    for (const flower of SAGYE_FLOWERS) {
      if (folded.includes(flower)) return flower;
    }
    if (!folded.includes("미스터리") && folded.includes("미스터")) return "미스터";
    if (folded.includes("미터지") || folded.includes("미터리")) return "미스터";
    const mister = folded.match(MISTER_SURNAME_RE);
    if (mister) return mister[0];
    const short = misterShortHit(folded);
    if (short) return short;
    const ok = compact.match(OK_RE);
    if (ok) return `${ok[1]}옥`;
    const soon = compact.match(SOON_RE);
    if (soon && !compact.slice(soon.index, soon.index + 8).includes("순위")) return `${soon[1]}순`;
    const old = compact.match(OLD_CAST_RE) || compact.match(OLD_CAST_KI_RE);
    if (old) return old[0];
    return "";
  }

  function isSagye(text) {
    const reason = sagyeReason(text);
    if (!reason) return false;
    if (SAGYE_SHOW.includes(reason) || reason === "사계") return true;
    if (hasCurrentSeason(normalize(text))) return false;
    return true;
  }

  function politicalReason(text) {
    const folded = plain(text);
    if (folded.includes("북한") && !folded.includes("거북한")) return "북한";
    if (folded.includes("진보") && !folded.includes("사진")) return "진보";
    return POLITICAL.find((part) => folded.includes(part)) || "";
  }

  function sexualReason(text) {
    const folded = plain(text);
    if (folded.includes("야동") && !folded.includes("야동생")) return "야동";
    return SEXUAL.find((part) => folded.includes(part)) || "";
  }

  function stripInsertedJamo(text) {
    return text.replace(/([가-힣])[ㄱ-ㅎㅏ-ㅣ\u1100-\u11ff]+(?=[가-힣])/g, "$1");
  }

  function swearReason(text) {
    const compact = normalize(text);
    const folded = stripInsertedJamo(fold(text));
    const jamoOnly = compact.replace(/[^ㄱ-ㅎ]/g, "");
    for (const part of SWEAR_JAMO) {
      if (folded.includes(part) || jamoOnly.includes(part)) return part;
    }
    return SWEARS.find((part) => folded.includes(part)) || "";
  }

  function dropReason(post, options = {}) {
    if (isBlockedYoutube(post)) return "유튜브:차단";
    const text = postText(post);
    if (isSagye(text)) return `사계:${sagyeReason(text)}`;
    const politics = politicalReason(text);
    if (politics) return `정치:${politics}`;
    const sexual = sexualReason(text);
    if (sexual) return `성적:${sexual}`;
    if (options.swears) {
      const swear = swearReason(text);
      if (swear) return `욕설:${swear}`;
    }
    return "";
  }

  function shouldKeep(post, options = {}) {
    return !dropReason(post, options);
  }

  root.BoardFilter = {
    CURRENT_SEASON,
    CURRENT_CAST,
    POLITICAL,
    SEXUAL,
    SWEARS,
    BLOCKED_YT_IDS,
    normalize,
    fold,
    isSagye,
    sagyeReason,
    dropReason,
    shouldKeep,
    swearReason,
    postText,
    youtubeId,
    skipYoutubeTitle,
    skipYoutubeVideo,
    isBlockedYoutube,
  };
})(window);
