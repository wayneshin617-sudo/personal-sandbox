"""34기 본방 글만 남기고 나솔사계·정치·성적 글을 걸러 낸다.

수집(merge)과 화면(docs/assets/filters.js)이 같은 규칙을 쓴다.
패턴을 더 넣을 때는 아래 상수 리스트만 늘리면 된다.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

CURRENT_SEASON = 34

# 이번 기수 본방을 가리키는 말. 사계 고유 키워드가 같이 있으면 통과시키지 않는다.
CURRENT_MARKERS = (
    "34기",
    "34기수",
    "이번기수",
    "현기수",
    "현재기수",
    "이번회차",
)

CURRENT_CAST = (
    "영수", "영호", "영식", "영철", "광수", "상철",
    "영숙", "정숙", "순자", "영자", "옥순", "현숙",
)

# 사계 프로그램 자체·민박 특집. 34기가 같이 있어도 제외.
SAGYE_SHOW = (
    "나솔사계",
    "솔로민박",
    "사계민박",
    "그후사랑은계속된다",
    "사랑은계속된다",
    "사계데이트권",
    "슈퍼데이트권",
    "나는solo그후",
    "나는솔로그후",
)

# 유튜브 제목·설명에 있으면 댓글을 모으지 않는다. 본방 글은 34기가 있으면 남긴다.
OTHER_SEASON_MARKS = (
    "다른기수",
    "타기수",
    "이전기수",
    "과거기수",
)

# 꽃 이름 특집(사계 출연진 별명). 배반의장미는 본방 브금이라 넣지 않는다.
SAGYE_FLOWERS = ("국화", "튤립", "용담", "백합", "수선화", "라벤더", "프리지아")

# 미스터 + 성씨. 실제 출연 별명 + 흔한 성씨를 넉넉히 넣는다.
MISTER_SURNAMES = (
    "김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신",
    "권", "황", "안", "송", "류", "유", "홍", "전", "고", "문", "손", "양", "배", "백",
    "허", "남", "심", "노", "하", "곽", "성", "차", "주", "우", "구", "민", "진", "나",
    "지", "엄", "채", "원", "천", "방", "공", "현", "함", "변", "염", "여", "추", "도",
    "석", "선", "설", "마", "길", "연", "표", "명", "기", "반", "왕", "금", "옥", "육",
    "인", "맹", "제갈", "사공", "선우", "남궁", "독고", "황보",
)

# 미서·미조처럼 줄여 부르는 별명. 미지/미나는 이미지·취미나와 겹치지 않게 따로 본다.
MISTER_SHORT = (
    "미서", "미조", "미최", "미강", "미윤", "미김", "미한", "미권", "미차", "미공",
    "미제갈", "미오", "미박", "미이", "미정", "미임", "미장", "미신", "미홍",
)

MISTER_NICKS = ("미조햄", "미서햄", "미지햄", "미공햄", "미차햄", "미최햄")

# 1·2·3순은 순위 표현이 많아서 빼고, 사계에서 실제로 불리는 기수만 넣는다.
SAGYE_OK_SEASONS = frozenset(
    {4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
     21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 35, 36, 37, 38}
)

CAST_NAMES = CURRENT_CAST

# 제목에 출연진을 나열하고 #나는솔로 를 도배한 폭로·스포 영상.
BLOCKED_YT_IDS = frozenset(
    {
        "qpUKcCsjHSI",
        "UT5GGHnjccE",
        "1vmMzTbRgHg",
        "Ny9RNTVLIk4",
        "RFTVQWZ0W4Y",
        "MEMWkVB_fJM",
    }
)
BLOCKED_YT_TITLE_MARKS = (
    "직장동료 지인 등판",
    "사내 빌런 폭로",
    "지인폭로",
    "직장 동료 학창시절",
)
_HASHTAG_SOLO_RE = re.compile(r"#\s*나는솔로", re.IGNORECASE)
_YT_ID_RE = re.compile(r"[?&]v=([\w-]+)")

POLITICAL = (
    "정치", "대통령", "민주당", "국민의힘", "국힘", "윤석열", "이재명", "문재인", "박근혜",
    "이명박", "한동훈", "조국", "이준석", "홍준표", "탄핵", "좌파", "우파", "여당", "야당",
    "국회", "김정은", "극우", "극좌", "친윤", "친문", "개딸", "보수", "선거",
)

SEXUAL = (
    "가슴", "엉덩이", "슴가", "유방", "젖꼭지", "유두", "섹스", "몰카", "도촬", "불법촬영",
    "성희롱", "성추행", "성폭행", "성폭력", "성매매", "강간", "음란", "팬티", "속옷", "보빨",
    "호빠", "꼴리", "변태", "자위", "섹드립",
)

# 메이플 채팅 금칙처럼, 글자 사이 공백·기호·숫자만 무시하고 앞뒤 한글은 삼킨다.
# 그래서 은꼴·은 꼴은 걸리고 닮은꼴·인성교육·딸딸아들은 남는다.
_SEXUAL_LOOSE = (
    "은꼴", "자꼴", "등꼴", "꼴림", "꼴려", "꼴렸", "꼴린", "꼴릴",
    "야설", "야짤", "야캠", "포르노", "폰허브", "pornhub", "porno",
    "딸딸이", "사까시", "빠구리", "질싸", "입싸", "애무", "콘돔",
    "섹파", "귀두", "불알", "부랄", "빨통", "떡치기", "번섹", "폰섹",
    "질내사정", "오르가즘", "펠라치오", "똥꼬", "애액", "성노예",
    "대딸", "즐딸", "조건만남", "색스", "쎅스", "쌕스", "섹쓰", "색쓰",
    "잠지", "보짓", "꼬추", "꼬츄", "성교", "발기", "후장",
    "개자지", "개보지", "애미보지", "로리타", "sex",
)
_SEXUAL_PARTICLE = (
    r"(?:이네|인데|이다|이더라|임|네|다|이|가|은|는|을|를|도|요|야|나|죠|의|에|와|과|좀|각|질|함|남|녀)?"
)
_SEXUAL_SEP = r"[^가-힣A-Za-z]{0,2}"
_SEXUAL_LOOSE_RE = [
    (
        term,
        re.compile(
            rf"(?<![가-힣A-Za-z]){_SEXUAL_SEP.join(re.escape(ch) for ch in term)}{_SEXUAL_PARTICLE}(?![가-힣A-Za-z])",
            re.IGNORECASE,
        ),
    )
    for term in _SEXUAL_LOOSE
]

# 단어 구름에서 빼는 욕. 본문 피드까지 지우지는 않는다.
SWEARS = (
    "존나", "졸라", "존내", "좆나", "씨발", "시발", "씨팔", "시팔", "씨벌", "시벌",
    "병신", "븅신", "병쉰", "지랄", "지럴", "좆", "좇", "새끼", "개새끼", "미친",
    "꺼져", "닥쳐", "씹", "보지", "자지", "걸레", "창녀", "창년", "썅", "니미",
    "애미", "등신", "호로", "또라이", "싸가지", "개소리", "좆밥", "느금", "느금마",
    "염병", "엠창", "개년", "개놈", "개새", "쉬발", "쉬벌", "스발", "슈발",
)

SWEAR_JAMO = ("ㅅㅂ", "ㅆㅂ", "ㅅㅍ", "ㅂㅅ", "ㅈㄹ")

# 정규화 때 지울 문자: 공백, 구두점, 숫자 사이 장식, 제로폭.
_KEEP_RE = re.compile(r"[^\w가-힣ㄱ-ㅎㅏ-ㅣ\u1100-\u11ff0-9]+", re.UNICODE)
_DIGIT_RE = re.compile(r"\d+")
_JAMO_RE = re.compile(r"[ㄱ-ㅎㅏ-ㅣ\u1100-\u11ff]")
_INSERTED_JAMO_RE = re.compile(r"(?<=[가-힣])[ㄱ-ㅎㅏ-ㅣ\u1100-\u11ff]+(?=[가-힣])")
_CHOSEONG_COMPAT = str.maketrans({
    "ᄀ": "ㄱ", "ᄁ": "ㄲ", "ᄂ": "ㄴ", "ᄃ": "ㄷ", "ᄄ": "ㄸ", "ᄅ": "ㄹ", "ᄆ": "ㅁ",
    "ᄇ": "ㅂ", "ᄈ": "ㅃ", "ᄉ": "ㅅ", "ᄊ": "ㅆ", "ᄋ": "ㅇ", "ᄌ": "ㅈ", "ᄍ": "ㅉ",
    "ᄎ": "ㅊ", "ᄏ": "ㅋ", "ᄐ": "ㅌ", "ᄑ": "ㅍ", "ᄒ": "ㅎ",
})
_CURRENT_CAST_RE = re.compile(rf"34(?:기)?(?:{'|'.join(CURRENT_CAST)})")
_OLD_CAST_RE = re.compile(
    rf"(?<![0-9])((?:1[0-9]|2[0-9]|3[0-3]|3[5-8]))(?:기)?(?:{'|'.join(CAST_NAMES)})"
)
_OLD_CAST_KI_RE = re.compile(rf"(?<![0-9가-힣])([4-9])기(?:{'|'.join(CAST_NAMES)})")
_OLD_SEASON_RE = re.compile(r"(?<![0-9])((?:[1-9]|1[0-9]|2[0-9]|3[0-3]|3[5-8])기)")
_OK_RE = re.compile(rf"({'|'.join(str(n) for n in sorted(SAGYE_OK_SEASONS))})기?옥순?")
_SOON_RE = re.compile(rf"({'|'.join(str(n) for n in sorted(SAGYE_OK_SEASONS))})기?순자?")
_MISTER_SURNAME_RE = re.compile("미스터(?:" + "|".join(sorted(MISTER_SURNAMES, key=len, reverse=True)) + ")")

# 고정 익명. ㅇ을 늘리거나 띄어 쓰거나, 나갤러/너갤러/나갤루에 숫자를 붙여도 같은 도배다.
_GALLERY_SPAM_RE = re.compile(
    r"^(?:ㅇ(?:\s*ㅇ)*|나갤러\d*|너갤러\d*|나갤루\d*)(?:\([^)]*\))?$"
)

# 영상 제목·본문에 이 말이 있으면 나솔 글로 본다.
SHOW_MARKS = ("나솔", "나는솔로", "나는solo", "iamsolo", "34기")

# 로그인 벽·버튼 문구. 댓글이 아니다.
LOGIN_WALL = (
    "forgotpassword",
    "createnewaccount",
    "emailorphone",
    "phonenumberpassword",
    "orcreatenewaccount",
    "logintofacebook",
    "logintoinstagram",
    "seemoreonfacebook",
    "continuewithfacebook",
    "continuewithgoogle",
    "continuewithapple",
    "비밀번호를잊으",
    "새계정만들",
    "이메일또는전화",
)

_LOGIN_IMAGE_RE = re.compile(r"^image\s*\d+$", re.I)
_LOGIN_TIME_RE = re.compile(r"^\d+[smhd]$", re.I)
_LOGIN_PUNCT_RE = re.compile(r"^[!?.·•\s]+$")

# 제목에만 있고 나솔 표지가 없으면 다른 프로그램이다.
OTHER_SHOWS = (
    "계약결혼", "환승연애", "돌싱글즈", "솔로지옥", "하트시그널", "결혼작사", "이혼작곡",
)

# 웃기려는 ㅋㅋ·ㅎㅎ 없이 붙는 원색 비난. 강조 욕(씨발, 존나)은 여기 넣지 않는다.
ATTACKS = (
    "죽어", "꺼져", "디져", "뒤져", "뒤질",
    "못생겼", "존못", "개못생",
    "추하네", "추하다", "추해", "징그럽", "역겹", "꼴불견",
    "인간쓰레기", "인간말종", "음식물쓰레기",
    "살빼", "빼고나와",
    "돼지", "찐따",
    "한남", "한녀", "틀딱", "맘충", "김치녀",
    "병신", "븅신", "ㅂㅅ",
    "쓰레기",
)


def normalize(text: str) -> str:
    """공백·특수문자를 빼고 소문자로 붙인다. 숫자는 미1스터조 같은 우회를 위해 남긴다."""
    raw = unicodedata.normalize("NFKC", text or "")
    raw = raw.lower()
    raw = raw.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    raw = _KEEP_RE.sub("", raw)
    return raw.translate(_CHOSEONG_COMPAT)


def fold(text: str) -> str:
    """숫자까지 뺀 형태. 미1스터조 → 미스터조, 시1발 → 시발."""
    return _DIGIT_RE.sub("", normalize(text))


def _plain(text: str) -> str:
    """자모 장식까지 뺀 형태. 미스ㅣ터서 → 미스터서."""
    return _JAMO_RE.sub("", fold(text))


def youtube_id(post: dict[str, Any] | str | None) -> str:
    if isinstance(post, str) or not post:
        return ""
    if post.get("video_id"):
        return str(post.get("video_id") or "")
    hit = _YT_ID_RE.search(str(post.get("url") or ""))
    return hit.group(1) if hit else ""


def skip_youtube_title(title: str) -> bool:
    """태그 도배·사계·다른기수 제목은 댓글을 모으지 않는다."""
    text = title or ""
    if len(_HASHTAG_SOLO_RE.findall(text)) >= 3:
        return True
    compact = re.sub(r"\s+", "", text)
    if any(mark.replace(" ", "") in compact for mark in BLOCKED_YT_TITLE_MARKS):
        return True
    if is_sagye(text):
        return True
    folded = _plain(text)
    if any(mark in folded for mark in OTHER_SEASON_MARKS):
        return True
    if _OLD_SEASON_RE.search(normalize(text)):
        return True
    return False


def skip_youtube_video(video: dict[str, Any] | None) -> bool:
    if not video:
        return False
    if (video.get("video_id") or youtube_id(video)) in BLOCKED_YT_IDS:
        return True
    blob = " ".join(
        part
        for part in (
            video.get("title") or "",
            video.get("description") or "",
            video.get("excerpt") or "",
        )
        if part
    )
    return skip_youtube_title(blob)


def is_blocked_youtube(post: dict[str, Any] | str | None) -> bool:
    if isinstance(post, str) or not post:
        return False
    source = post.get("source") or ""
    if post.get("video_id"):
        return skip_youtube_video(post)
    if source != "yt":
        return False
    if youtube_id(post) in BLOCKED_YT_IDS:
        return True
    return skip_youtube_title(post.get("excerpt") or "")


def post_text(post: dict[str, Any] | None) -> str:
    if not post:
        return ""
    title = post.get("title") or ""
    # 유튜브는 댓글만 본다. 제목·태그·설명에 넣은 이름은 본방 여부와 집계에 쓰지 않는다.
    if (post.get("source") or "") == "yt":
        return title
    return f"{title} {post.get('excerpt') or ''}"


def _has_current_season(compact: str) -> bool:
    if any(marker in compact for marker in CURRENT_MARKERS):
        return True
    return bool(_CURRENT_CAST_RE.search(compact))


def _mister_short_hit(plain: str) -> str | None:
    cleaned = plain.replace("이미지", "")
    for nick in MISTER_NICKS:
        if nick in cleaned:
            return nick
    for short in MISTER_SHORT:
        if short in cleaned:
            return short
    # 미지: 이미지에 들어 있는 미지는 무시
    if re.search(r"(?<![가-힣])미지", cleaned):
        return "미지"
    # 미나: 취미나·재미나·의미나와 겹치면 무시
    probe = cleaned.replace("취미나", "").replace("재미나", "").replace("의미나", "")
    if "미나" in probe:
        return "미나"
    return None


def sagye_reason(text: str) -> str | None:
    """사계 글이면 걸린 패턴 이름을 돌려 준다."""
    compact = normalize(text)
    plain = _plain(text)
    if not compact:
        return None

    for kw in SAGYE_SHOW:
        if kw in plain:
            return kw
    if "사계" in plain:
        return "사계"
    for mark in OTHER_SEASON_MARKS:
        if mark in plain:
            return mark

    for flower in SAGYE_FLOWERS:
        if flower in plain:
            return flower

    if "미스터리" not in plain and "미스터" in plain:
        return "미스터"
    if "미터지" in plain or "미터리" in plain:
        return "미스터"
    mister = _MISTER_SURNAME_RE.search(plain)
    if mister:
        return mister.group(0)
    short = _mister_short_hit(plain)
    if short:
        return short

    ok = _OK_RE.search(compact)
    if ok:
        return f"{ok.group(1)}옥"
    soon = _SOON_RE.search(compact)
    if soon and "순위" not in compact[soon.start(): soon.start() + 8]:
        return f"{soon.group(1)}순"

    old = _OLD_CAST_RE.search(compact) or _OLD_CAST_KI_RE.search(compact)
    if old:
        return old.group(0)
    old_season = _OLD_SEASON_RE.search(compact)
    if old_season:
        return old_season.group(1)

    return None


def is_sagye(text: str) -> bool:
    compact = normalize(text)
    reason = sagye_reason(text)
    if not reason:
        return False
    # 34기·이번기수가 있으면 원칙적으로 본방으로 본다.
    # 다만 나솔사계·솔로민박처럼 프로그램 자체가 사계면 그대로 제외.
    if reason in SAGYE_SHOW or reason == "사계":
        return True
    if _has_current_season(compact):
        return False
    return True


def political_reason(text: str) -> str | None:
    plain = _plain(text)
    if "북한" in plain and "거북한" not in plain:
        return "북한"
    if "진보" in plain and "사진" not in plain:
        return "진보"
    for part in POLITICAL:
        if part in plain:
            return part
    return None


def sexual_reason(text: str) -> str | None:
    """공백·기호를 무시한 금칙어. 앞뒤가 다른 한글 단어면 삼키지 않는다."""
    if not isinstance(text, str) or not text:
        return None
    plain = _plain(text)
    if "야동" in plain and "야동생" not in plain:
        return "야동"
    for part in SEXUAL:
        if part in plain:
            if part == "자위" and ("자위대" in plain or "자위권" in plain):
                continue
            return part
    raw = unicodedata.normalize("NFKC", text).lower()
    for term, cre in _SEXUAL_LOOSE_RE:
        if not cre.search(raw):
            continue
        if term == "자위" and re.search(r"자위(?:대|권)", raw):
            continue
        return term
    return None


def _strip_inserted_jamo(text: str) -> str:
    return _INSERTED_JAMO_RE.sub("", text)


def swear_reason(text: str) -> str | None:
    """단어 구름용. 시1발, ㅅ1ㅂ, 시 ㅂ 발처럼 끼워 넣은 글자도 잡는다."""
    compact = normalize(text)
    folded = _strip_inserted_jamo(fold(text))
    jamo_only = re.sub(r"[^ㄱ-ㅎ]", "", compact)
    for part in SWEAR_JAMO:
        if part in folded or part in jamo_only:
            return part
    for part in SWEARS:
        if part in folded:
            return part
    return None


def login_wall_reason(post: dict[str, Any] | str | None) -> str | None:
    """페북·인스타 로그인 화면 문구는 댓글로 보지 않는다."""
    if isinstance(post, str) or not post:
        return None
    title = (post.get("title") or "").strip()
    author = (post.get("author") or "").strip()
    blob = _plain(f"{title} {author}").lower()
    for mark in LOGIN_WALL:
        if mark in blob:
            return mark
    if _LOGIN_IMAGE_RE.fullmatch(title) or _LOGIN_IMAGE_RE.fullmatch(author):
        return "image"
    if _LOGIN_PUNCT_RE.fullmatch(title):
        return "empty"
    if _LOGIN_TIME_RE.fullmatch(author):
        return "time"
    return None


def gallery_spam_reason(post: dict[str, Any] | str | None) -> str | None:
    """ㅇ만 반복된 닉과 나갤러·너갤러·나갤루는 출처와 상관없이 모으지 않는다."""
    if isinstance(post, str) or not post:
        return None
    author = (post.get("author") or "").strip()
    if not _GALLERY_SPAM_RE.match(author):
        return None
    if author.startswith("나갤"):
        return "나갤러"
    if author.startswith("너갤"):
        return "너갤러"
    return "ㅇㅇ"


def unrelated_reason(post: dict[str, Any] | str | None) -> str | None:
    """제목(유튜브는 영상 제목)을 보고 나솔이 아닌 글을 가른다."""
    if isinstance(post, str) or not post:
        return None
    source = post.get("source") or ""
    if source == "yt":
        folded = _plain(post.get("excerpt") or "")
        if any(mark in folded for mark in SHOW_MARKS):
            return None
        return "유튜브"
    if source in {"threads", "ig", "fb"}:
        folded = _plain(f"{post.get('title') or ''} {post.get('excerpt') or ''}")
        if any(mark in folded for mark in SHOW_MARKS):
            return None
        return {"threads": "쓰레드", "ig": "인스타", "fb": "페북"}[source]
    folded = _plain(f"{post.get('title') or ''} {post.get('excerpt') or ''}")
    if any(mark in folded for mark in SHOW_MARKS):
        return None
    for mark in OTHER_SHOWS:
        if mark in folded:
            return mark
    return None


def attack_reason(post: dict[str, Any] | str | None) -> str | None:
    """ㅋㅋ·ㅎㅎ가 없는 원색 비난만 버린다. 웃기려는 문장은 남긴다."""
    if isinstance(post, str) or not post:
        return None
    text = post_text(post)
    if "ㅋ" in text or "ㅎ" in text:
        return None
    folded = _strip_inserted_jamo(fold(text))
    for part in ATTACKS:
        if part in folded:
            return part
    return None


def drop_reason(post: dict[str, Any] | str | None, *, swears: bool = False) -> str | None:
    """걸러야 하면 이유 문자열, 남겨도 되면 None."""
    if not isinstance(post, str) and post and (post.get("source") or "") == "fb":
        return "페북"
    if is_blocked_youtube(post):
        return "유튜브:차단"
    spam = gallery_spam_reason(post)
    if spam:
        return f"도배:{spam}"
    wall = login_wall_reason(post)
    if wall:
        return f"로그인:{wall}"
    text = post if isinstance(post, str) else post_text(post)
    hit = sagye_reason(text)
    if hit and (hit in SAGYE_SHOW or hit == "사계" or not _has_current_season(normalize(text))):
        return f"사계:{hit}"
    hit = political_reason(text)
    if hit:
        return f"정치:{hit}"
    hit = sexual_reason(text)
    if hit:
        return f"성적:{hit}"
    unrelated = unrelated_reason(post)
    if unrelated:
        return f"무관:{unrelated}"
    attack = attack_reason(post)
    if attack:
        return f"비난:{attack}"
    if swears:
        hit = swear_reason(text)
        if hit:
            return f"욕설:{hit}"
    return None


def should_keep(post: dict[str, Any] | str | None, *, swears: bool = False) -> bool:
    return drop_reason(post, swears=swears) is None


def is_sagye_post(post: dict[str, Any] | str | None) -> bool:
    text = post if isinstance(post, str) else post_text(post)
    return is_sagye(text)
