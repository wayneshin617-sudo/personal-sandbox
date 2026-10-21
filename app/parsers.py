"""디시인사이드·블라인드·더쿠·쓰레드·인스타·페북 공개 글과 댓글을 읽는다."""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from bs4 import BeautifulSoup

DC_BASE = "https://gall.dcinside.com"
BLIND_BASE = "https://www.teamblind.com"
QOO_BASE = "https://theqoo.net"
_QOO_POST = re.compile(r"/iamsolo/(\d+)$")

_WS = re.compile(r"\s+")
_REPLY = re.compile(r"\[([\d,]+)\]")
_DC_CMT_TIME = re.compile(r"^(\d{2})\.(\d{2})\s+(\d{2}):(\d{2}):(\d{2})$")
_DC_REPLY_MENTION = re.compile(r"^@\S+(?:\([^)]*\))?\s*")
_QOO_CMT_TIME = re.compile(r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})$")
_DELETED_COMMENT = ("삭제된 댓글", "이 댓글은 삭제", "해당 댓글은 삭제", "댓글이 삭제")
KST = timezone(timedelta(hours=9))


def clean(value: str | None) -> str:
    if not value:
        return ""
    text = value.replace("\xa0", " ").replace("\u200b", "").replace("\ufeff", "")
    return _WS.sub(" ", text).strip()


def plain(value: str | None) -> str:
    """댓글 HTML에서 보이는 문장만 남긴다."""
    if not value:
        return ""
    if "<" in value and ">" in value:
        value = _soup(value).get_text(" ", strip=True)
    return clean(value)


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    digits = clean(value).replace(",", "")
    if not digits.isdigit():
        return None
    return int(digits)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _safe_https(url: str, hosts: set[str]) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts:
        return None
    return url


def _metric_text(el) -> str:
    if el is None:
        return ""
    parts: list[str] = []
    for child in el.children:
        name = getattr(child, "name", None)
        if name == "i":
            continue
        if name:
            parts.append(child.get_text(" ", strip=True))
        else:
            parts.append(str(child))
    return clean("".join(parts))


def parse_dc(html: str) -> list[dict]:
    """최신순으로 일반 글만 돌려준다. 공지·광고·설문은 제외한다."""
    posts: list[dict] = []
    for tr in _soup(html).select("tr.us-post"):
        external_id = clean(tr.get("data-no"))
        if not external_id.isdigit():
            continue
        link = None
        for cand in tr.select("td.gall_tit a"):
            if "reply_numbox" in (cand.get("class") or []):
                continue
            href = cand.get("href") or ""
            if "board/view" not in href:
                continue
            link = cand
            break
        if link is None:
            continue
        title = clean(link.get_text(" ", strip=True))[:300]
        url = _safe_https(urljoin(DC_BASE, link.get("href")), {"gall.dcinside.com"})
        if not title or not url:
            continue
        writer = tr.select_one("td.gall_writer")
        author = clean(writer.get("data-nick")) if writer is not None else ""
        ip = clean(writer.get("data-ip")) if writer is not None else ""
        if not author and writer is not None:
            em = writer.select_one(".nickname em")
            author = clean(em.get_text()) if em is not None else ""
        date_el = tr.select_one("td.gall_date")
        posted_label = clean(date_el.get_text()) if date_el is not None else ""
        posted_at = clean(date_el.get("title")) if date_el is not None else ""
        if posted_at:
            posted_at = posted_at.replace(" ", "T")
        comments = None
        reply_el = tr.select_one("span.reply_num")
        if reply_el is not None:
            matched = _REPLY.search(reply_el.get_text(" ", strip=True))
            if matched:
                comments = parse_int(matched.group(1))
        count_el = tr.select_one("td.gall_count")
        reco_el = tr.select_one("td.gall_recommend")
        posts.append(
            {
                "source": "dc",
                "external_id": external_id,
                "title": title,
                "excerpt": "",
                "author": author or "익명",
                "company": "",
                "ip": ip,
                "badge": "",
                "url": url,
                "posted_label": posted_label,
                "posted_at": posted_at,
                "views": parse_int(count_el.get_text()) if count_el is not None else None,
                "recommends": parse_int(reco_el.get_text()) if reco_el is not None else None,
                "comments": comments,
            }
        )
    return posts


def parse_blind(html: str) -> list[dict]:
    """최신순으로 I'm솔로 글만 돌려준다. 광고·외부 링크는 제외한다."""
    posts: list[dict] = []
    for node in _soup(html).select("div.article-list-pre"):
        classes = set(node.get("class") or [])
        if "article-list-ad" in classes or "article-list-link" in classes:
            continue
        link = node.select_one("h3 a")
        if link is None:
            continue
        href = link.get("href") or ""
        if "/post/" not in href:
            continue
        title = clean(link.get_text(" ", strip=True))[:300]
        url = _safe_https(
            urljoin(BLIND_BASE, href),
            {"www.teamblind.com", "teamblind.com"},
        )
        if not title or not url:
            continue
        excerpt_el = node.select_one("p.pre-txt")
        excerpt = clean(excerpt_el.get_text(" ", strip=True)) if excerpt_el is not None else ""
        if excerpt == title:
            excerpt = ""
        name_el = node.select_one("p.name")
        name = clean(name_el.get_text(" ", strip=True)) if name_el is not None else ""
        company, author = "", name
        if "·" in name:
            company, author = [clean(part) for part in name.split("·", 1)]
        badge_el = node.select_one("i.category-label")
        badge = clean(badge_el.get_text()) if badge_el is not None else ""
        posts.append(
            {
                "source": "blind",
                "external_id": href.split("?")[0],
                "title": title,
                "excerpt": excerpt[:500],
                "author": author or "익명",
                "company": company,
                "ip": "",
                "badge": badge,
                "url": url,
                "posted_label": _metric_text(node.select_one("a.past")),
                "posted_at": "",
                "views": parse_int(_metric_text(node.select_one("a.pv"))),
                "recommends": parse_int(_metric_text(node.select_one("span.like"))),
                "comments": parse_int(_metric_text(node.select_one("a.cmt"))),
            }
        )
    return posts


def parse_theqoo(html: str) -> list[dict]:
    """더쿠 나는 SOLO 목록을 최신순으로 돌려준다. 공지는 제외한다."""
    posts: list[dict] = []
    for tr in _soup(html).select("tr"):
        if "notice" in (tr.get("class") or []):
            continue
        link = None
        external_id = ""
        for cand in tr.select("td.title a"):
            classes = cand.get("class") or []
            if "replyNum" in classes or "preface" in classes:
                continue
            href = (cand.get("href") or "").split("?")[0]
            matched = _QOO_POST.search(href)
            if not matched:
                continue
            link = cand
            external_id = matched.group(1)
            break
        if link is None:
            continue
        title = clean(link.get_text(" ", strip=True))[:300]
        url = _safe_https(urljoin(QOO_BASE, f"/iamsolo/{external_id}"), {"theqoo.net"})
        if not title or not url:
            continue
        cate = tr.select_one("td.cate")
        badge = clean(cate.get_text(" ", strip=True)) if cate is not None else ""
        time_el = tr.select_one("td.time")
        reply = tr.select_one("a.replyNum")
        views_el = tr.select_one("td.m_no")
        posts.append(
            {
                "source": "qoo",
                "external_id": external_id,
                "title": title,
                "excerpt": "",
                "author": "무명의 더쿠",
                "company": "",
                "ip": "",
                "badge": badge,
                "url": url,
                "posted_label": clean(time_el.get_text()) if time_el is not None else "",
                "posted_at": "",
                "views": parse_int(views_el.get_text()) if views_el is not None else None,
                "recommends": None,
                "comments": parse_int(reply.get_text()) if reply is not None else None,
            }
        )
    return posts


def _json_after_marker(html: str, marker: str) -> dict:
    pos = html.find(marker)
    if pos < 0:
        return {}
    start = html.find("{", pos)
    if start < 0:
        return {}
    depth = 0
    for index in range(start, len(html)):
        char = html[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : index + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


def load_youtube_data(html: str) -> dict:
    return _json_after_marker(html, "ytInitialData")


def parse_youtube_watch_meta(html: str) -> dict:
    """시청 페이지에서 제목·설명을 읽는다. 사계 영상은 댓글 전에 걸러 낸다."""
    data = _json_after_marker(html, "ytInitialPlayerResponse")
    details = data.get("videoDetails") if isinstance(data, dict) else None
    if not isinstance(details, dict):
        return {}
    return {
        "title": clean(details.get("title") or "")[:180],
        "description": clean(details.get("shortDescription") or "")[:800],
    }


def _yt_text(node: dict | None) -> str:
    if not isinstance(node, dict):
        return ""
    if node.get("simpleText"):
        return clean(node["simpleText"])
    return clean("".join(run.get("text", "") for run in node.get("runs") or []))


def _walk(node, visit, depth: int = 0) -> None:
    if depth > 24:
        return
    if isinstance(node, dict):
        visit(node)
        for value in node.values():
            _walk(value, visit, depth + 1)
    elif isinstance(node, list):
        for value in node:
            _walk(value, visit, depth + 1)


def parse_youtube_search(data: dict) -> tuple[list[dict], str]:
    """업로드순 검색 결과에서 영상과 다음 페이지 토큰을 읽는다."""
    videos: list[dict] = []
    seen: set[str] = set()

    def visit(node: dict) -> None:
        renderer = node.get("videoRenderer")
        if not isinstance(renderer, dict):
            return
        video_id = clean(renderer.get("videoId"))
        title = _yt_text(renderer.get("title"))
        if not video_id or not title or video_id in seen:
            return
        seen.add(video_id)
        videos.append(
            {
                "video_id": video_id,
                "title": title[:180],
                "description": _yt_text(renderer.get("descriptionSnippet"))[:400],
                "author": _yt_text(renderer.get("ownerText")) or "유튜브",
                "published_label": _yt_text(renderer.get("publishedTimeText")),
            }
        )

    _walk(data, visit)
    return videos, _youtube_continuation(data)


def parse_youtube_comments(data: dict, video: dict) -> tuple[list[dict], str]:
    """최신순 댓글 응답에서 원댓글만 읽는다."""
    comments: list[dict] = []
    seen: set[str] = set()
    video_id = video["video_id"]
    video_title = video.get("title") or ""

    def visit(node: dict) -> None:
        payload = node.get("commentEntityPayload")
        if not isinstance(payload, dict):
            return
        props = payload.get("properties") or {}
        if props.get("replyLevel") not in (0, None):
            return
        comment_id = clean(props.get("commentId"))
        content = clean((props.get("content") or {}).get("content"))
        if not comment_id or not content or comment_id in seen:
            return
        seen.add(comment_id)
        author = clean((payload.get("author") or {}).get("displayName")) or "유튜브"
        comments.append(
            {
                "source": "yt",
                "external_id": comment_id,
                "title": content[:300],
                "excerpt": video_title[:120],
                "author": author[:80],
                "company": "",
                "ip": "",
                "badge": "",
                "url": f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
                "posted_label": clean(props.get("publishedTime")) or "방금",
                "posted_at": "",
                "views": None,
                "recommends": None,
                "comments": None,
                "video_id": video_id,
            }
        )

    _walk(data, visit)
    return comments, _youtube_continuation(data)


def youtube_newest_token(data: dict) -> str:
    found = ""

    def visit(node: dict) -> None:
        nonlocal found
        header = node.get("engagementPanelTitleHeaderRenderer")
        if not isinstance(header, dict):
            return
        items = ((header.get("menu") or {}).get("sortFilterSubMenuRenderer") or {}).get("subMenuItems") or []
        for item in items:
            if item.get("title") == "최신순":
                found = ((item.get("serviceEndpoint") or {}).get("continuationCommand") or {}).get("token") or found

    _walk(data, visit)
    return found


def _reply(
    *,
    source: str,
    external_id: str,
    title: str,
    url: str,
    author: str,
    posted_at: str = "",
    posted_label: str = "",
    ip: str = "",
    company: str = "",
    recommends: int | None = None,
) -> dict:
    return {
        "source": source,
        "external_id": external_id,
        "title": title[:300],
        "excerpt": "",
        "author": author or "익명",
        "company": company,
        "ip": ip,
        "badge": "",
        "url": url,
        "posted_label": posted_label,
        "posted_at": posted_at,
        "views": None,
        "recommends": recommends,
        "comments": None,
        "kind": "reply",
    }


def _deleted_comment(text: str) -> bool:
    return any(text.startswith(mark) for mark in _DELETED_COMMENT)


def _dc_comment_time(value: str, now: datetime) -> str:
    matched = _DC_CMT_TIME.match(clean(value))
    if not matched:
        return ""
    month, day, hour, minute, second = (int(part) for part in matched.groups())
    current = now.astimezone(KST)
    try:
        stamp = datetime(current.year, month, day, hour, minute, second, tzinfo=KST)
    except ValueError:
        return ""
    if stamp - current > timedelta(days=2):
        stamp = stamp.replace(year=current.year - 1)
    return stamp.replace(microsecond=0).isoformat()


def parse_dc_comments(payload: dict, parent: dict, *, now: datetime | None = None) -> list[dict]:
    """디시 댓글 JSON에서 지워지지 않은 댓글을 읽는다."""
    if not isinstance(payload, dict):
        return []
    current = now or datetime.now(KST)
    parent_url = parent.get("url") or ""
    posts: list[dict] = []
    seen: set[str] = set()
    for item in payload.get("comments") or []:
        if not isinstance(item, dict):
            continue
        if item.get("del_yn") == "Y" or str(item.get("is_delete") or "0") not in {"0", "N"}:
            continue
        number = clean(str(item.get("no") or ""))
        memo = plain(item.get("memo"))
        memo = _DC_REPLY_MENTION.sub("", memo).strip()
        if not number.isdigit() or not memo or _deleted_comment(memo) or number in seen:
            continue
        seen.add(number)
        posts.append(
            _reply(
                source="dc",
                external_id=f"cmt-{number}",
                title=memo,
                url=f"{parent_url}#cmt_{number}" if parent_url else "",
                author=clean(item.get("name")) or "ㅇㅇ",
                posted_at=_dc_comment_time(str(item.get("reg_date") or ""), current),
                posted_label=clean(str(item.get("reg_date") or "")),
                ip=clean(item.get("ip")),
                recommends=parse_int(str(item.get("rcnt"))) if item.get("rcnt") not in (None, "") else None,
            )
        )
    return posts


def parse_theqoo_comments(payload: dict, parent: dict) -> list[dict]:
    """더쿠 댓글 JSON을 읽는다. 비회원에게 가린 한 시간 안 댓글은 건너뛴다."""
    if not isinstance(payload, dict):
        return []
    parent_url = parent.get("url") or ""
    posts: list[dict] = []
    seen: set[str] = set()
    for item in payload.get("comment_list") or []:
        if not isinstance(item, dict):
            continue
        raw = item.get("ct") or ""
        if "commentWarningMessage" in raw or "비회원은 작성한" in raw:
            continue
        memo = plain(raw)
        number = clean(str(item.get("srl") or ""))
        if not number.isdigit() or not memo or _deleted_comment(memo) or number in seen:
            continue
        seen.add(number)
        posted_at = ""
        matched = _QOO_CMT_TIME.match(clean(str(item.get("rd") or "")))
        if matched:
            year, month, day, hour, minute, second = matched.groups()
            posted_at = f"{year}-{month}-{day}T{hour}:{minute}:{second}+09:00"
        posts.append(
            _reply(
                source="qoo",
                external_id=f"cmt-{number}",
                title=memo,
                url=f"{parent_url}#{number}" if parent_url else "",
                author="무명의 더쿠",
                posted_at=posted_at,
            )
        )
    return posts


def parse_blind_comments(html: str, parent: dict) -> list[dict]:
    """블라인드 글 페이지에 보이는 댓글을 읽는다."""
    parent_url = parent.get("url") or ""
    posts: list[dict] = []
    seen: set[str] = set()
    for node in _soup(html).select("div.wrap-comment"):
        number = clean(node.get("id"))
        text_el = node.select_one("p.cmt-txt")
        if text_el is None or "delete" in (text_el.get("class") or []):
            continue
        memo = clean(text_el.get_text(" ", strip=True))
        if not number.isdigit() or not memo or _deleted_comment(memo) or number in seen:
            continue
        seen.add(number)
        name_el = node.select_one("p.name")
        company, author = "", ""
        if name_el is not None:
            name = clean(name_el.get_text(" ", strip=True))
            if "·" in name:
                company, author = [clean(part) for part in name.split("·", 1)]
            else:
                author = name
        date_el = node.select_one("span.date")
        like_el = node.select_one("span.like")
        posts.append(
            _reply(
                source="blind",
                external_id=f"cmt-{number}",
                title=memo,
                url=f"{parent_url}#{number}" if parent_url else "",
                author=author or "익명",
                company=company,
                posted_label=_metric_text(date_el),
                recommends=parse_int(_metric_text(like_el)),
            )
        )
    return posts


def _youtube_continuation(data: dict) -> str:
    found = ""

    def visit(node: dict) -> None:
        nonlocal found
        renderer = node.get("continuationItemRenderer")
        if not isinstance(renderer, dict):
            return
        token = ((renderer.get("continuationEndpoint") or {}).get("continuationCommand") or {}).get("token") or ""
        if token:
            found = token

    _walk(data, visit)
    return found


_DDG_UDDG = re.compile(r"[?&]uddg=([^&]+)")
_THREADS_POST = re.compile(r"https://www\.threads\.(?:com|net)/@([^/?#]+)/post/([A-Za-z0-9_-]+)")
_IG_POST = re.compile(r"https://www\.instagram\.com/(p|reel|tv)/([A-Za-z0-9_-]+)")
_FB_NUM = re.compile(r"/(?:posts|videos|permalink(?:\.php)?)(?:/[^/?#]+)*/(\d{8,})(?:/|$|\?)")
_FB_STORY = re.compile(r"(?:story_fbid|fbid)=(\d{8,})")
_FB_PAGE = re.compile(r"https://(?:www|m|mbasic)\.facebook\.com/([^/?#]+)/")
_SHORT_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
_IG_EPOCH_MS = 1_314_220_021_721
_KDATE = re.compile(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")
_SNIP_AGE = re.compile(
    r"(?:^|\s)(\d+)\s*(초|분|시간|일|주|minutes?|hours?|days?|weeks?|months?|s|m|h|d|w)\s*(?:ago|전)?\s*$",
    re.IGNORECASE,
)


def decode_ddg_url(href: str) -> str:
    raw = (href or "").strip()
    if raw.startswith("//"):
        raw = "https:" + raw
    matched = _DDG_UDDG.search(raw)
    if matched:
        raw = unquote(unquote(matched.group(1)))
    parsed = urlparse(raw)
    query = parse_qs(parsed.query)
    if "uddg" in query:
        raw = unquote(query["uddg"][0])
    encoded = query.get("u", [""])[0]
    if encoded.startswith("a1"):
        blob = encoded[2:] + "=" * ((4 - len(encoded[2:]) % 4) % 4)
        try:
            raw = unquote(base64.urlsafe_b64decode(blob).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            pass
    return raw.split("#")[0]


def _shortcode_time(code: str) -> datetime | None:
    if not code:
        return None
    value = 0
    try:
        for ch in code:
            value = value * 64 + _SHORT_ALPHABET.index(ch)
    except ValueError:
        return None
    if value <= 0:
        return None
    millis = (value >> 23) + _IG_EPOCH_MS
    if millis < 1_600_000_000_000 or millis > 2_200_000_000_000:
        return None
    return datetime.fromtimestamp(millis / 1000, tz=KST)


def _snippet_age(text: str, now: datetime) -> datetime | None:
    blob = clean(text)
    dated = _KDATE.search(blob)
    if dated:
        try:
            return datetime(int(dated.group(1)), int(dated.group(2)), int(dated.group(3)), 12, 0, tzinfo=KST)
        except ValueError:
            pass
    if "어제" in blob:
        return now - timedelta(days=1)
    matched = _SNIP_AGE.search(blob)
    if not matched:
        return None
    amount = int(matched.group(1))
    unit = matched.group(2).lower()
    if unit in ("초", "s"):
        return now - timedelta(seconds=amount)
    if unit in ("분", "m", "minute", "minutes"):
        return now - timedelta(minutes=amount)
    if unit in ("시간", "h", "hour", "hours"):
        return now - timedelta(hours=amount)
    if unit in ("일", "d", "day", "days"):
        return now - timedelta(days=amount)
    if unit in ("주", "w", "week", "weeks"):
        return now - timedelta(weeks=amount)
    if unit in ("month", "months"):
        return now - timedelta(days=30 * amount)
    return None


def _social_title(text: str) -> str:
    title = clean(text)
    for junk in (" | Instagram", " | Facebook", " • Threads, Say more", " | Threads"):
        if title.endswith(junk):
            title = title[: -len(junk)].strip()
    return title[:300]


def _social_author(source: str, title: str, url: str) -> str:
    named = re.search(r"\((@[^)]+)\)", title)
    if named:
        return named.group(1)
    if source == "threads":
        matched = _THREADS_POST.search(url)
        if matched:
            return f"@{matched.group(1)}"
    if source == "ig":
        head = title.split("|", 1)[0].strip()
        if head and head != title and len(head) <= 40:
            return head
    if source == "fb":
        matched = _FB_PAGE.search(url)
        if matched and matched.group(1) not in {"posts", "watch", "photo", "permalink.php", "story.php"}:
            return matched.group(1)
        if " | " in title:
            return title.rsplit(" | ", 1)[-1].strip()[:40]
    return "익명"


def canonicalize_social_url(url: str) -> tuple[str, str, str] | None:
    """(source, external_id, url) 또는 프로필·검색 주소는 None."""
    raw = decode_ddg_url(url)
    if raw.startswith("http://"):
        raw = "https://" + raw[len("http://"):]
    threads = _THREADS_POST.search(raw)
    if threads:
        user, code = threads.group(1), threads.group(2)
        href = _safe_https(f"https://www.threads.com/@{user}/post/{code}", {"www.threads.com", "threads.com"})
        return ("threads", code, href) if href else None
    insta = _IG_POST.search(raw)
    if insta:
        kind, code = insta.group(1), insta.group(2)
        href = _safe_https(f"https://www.instagram.com/{kind}/{code}/", {"www.instagram.com", "instagram.com"})
        return ("ig", code, href) if href else None
    if "facebook.com" not in raw:
        return None
    story = _FB_STORY.search(raw)
    number = story.group(1) if story else None
    if number is None:
        numbered = _FB_NUM.search(raw)
        number = numbered.group(1) if numbered else None
    page = _FB_PAGE.search(raw)
    name = page.group(1) if page else ""
    if not number:
        return None
    if name and name not in {"posts", "watch", "photo", "permalink.php", "story.php", "groups"}:
        href = _safe_https(f"https://www.facebook.com/{name}/posts/{number}", {"www.facebook.com", "facebook.com"})
    else:
        href = _safe_https(f"https://www.facebook.com/posts/{number}", {"www.facebook.com", "facebook.com"})
    return ("fb", number, href) if href else None


def parse_social_search(html: str, source: str, now: datetime) -> list[dict]:
    """공개 검색 목록에서 쓰레드·인스타·페북 글만 남긴다. 프로필·탐색 주소는 뺀다."""
    posts: list[dict] = []
    seen: set[str] = set()
    for node in _soup(html).select(".result, .web-result, .results_links, li.b_algo"):
        link = node.select_one("a.result__a") or node.select_one("h2 a")
        if link is None:
            continue
        parsed = canonicalize_social_url(link.get("href") or "")
        if not parsed or parsed[0] != source:
            continue
        kind, external_id, url = parsed
        if external_id in seen:
            continue
        seen.add(external_id)
        snippet_el = node.select_one(".result__snippet, .b_caption")
        date_el = node.select_one(".news_dt")
        snippet = clean(snippet_el.get_text(" ", strip=True)) if snippet_el is not None else ""
        dated = clean(date_el.get_text(" ", strip=True)) if date_el is not None else ""
        title = _social_title(link.get_text(" ", strip=True))
        if not title:
            title = snippet[:300]
        if not title:
            continue
        excerpt = snippet[:500]
        if excerpt == title:
            excerpt = ""
        stamp = _shortcode_time(external_id) if kind in {"threads", "ig"} else None
        if stamp is None:
            stamp = _snippet_age(f"{dated} {title} {snippet}", now)
        posted_label = ""
        posted_at = ""
        if stamp is not None:
            posted_at = stamp.astimezone(KST).replace(microsecond=0).isoformat()
            posted_label = posted_at[11:16]
        posts.append(
            {
                "source": kind,
                "external_id": external_id,
                "title": title,
                "excerpt": excerpt,
                "author": _social_author(kind, title, url),
                "company": "",
                "ip": "",
                "badge": "",
                "url": url,
                "posted_label": posted_label,
                "posted_at": posted_at,
                "views": None,
                "recommends": None,
                "comments": None,
            }
        )
    return posts
