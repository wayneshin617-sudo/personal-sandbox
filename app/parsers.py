"""디시인사이드·블라인드 공개 목록 페이지에서 글 제목을 읽는다."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

DC_BASE = "https://gall.dcinside.com"
BLIND_BASE = "https://www.teamblind.com"
QOO_BASE = "https://theqoo.net"
_QOO_POST = re.compile(r"/iamsolo/(\d+)$")

_WS = re.compile(r"\s+")
_REPLY = re.compile(r"\[([\d,]+)\]")


def clean(value: str | None) -> str:
    if not value:
        return ""
    text = value.replace("\xa0", " ").replace("\u200b", "").replace("\ufeff", "")
    return _WS.sub(" ", text).strip()


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
