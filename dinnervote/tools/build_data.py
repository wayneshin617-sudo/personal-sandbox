"""네이버 플레이스에서 후보 정보를 받아 index.html 안의 데이터 블록을 갱신한다.

    python3 dinnervote/tools/build_data.py

표준 라이브러리만 쓴다. 네이버가 짧은 간격의 요청을 막기 때문에 매장마다 몇 초씩 쉰다.
"""

import datetime as dt
import json
import pathlib
import re
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CANDIDATES = ROOT / "tools" / "candidates.json"
INDEX = ROOT / "index.html"
SNAPSHOT = ROOT / "tools" / "places.json"

UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
PHOTO_TARGET = 10
START, END = "/*PLACES_START*/", "/*PLACES_END*/"


def fetch_state(place_id):
    url = f"https://m.place.naver.com/restaurant/{place_id}/home"
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR"})
            with urllib.request.urlopen(req, timeout=20) as r:
                html = r.read().decode("utf-8", "replace")
            m = re.search(r"window\.__APOLLO_STATE__\s*=\s*(\{.*?\});\s*window\.", html, re.S)
            if m:
                return json.loads(m.group(1))
        except Exception as e:  # noqa: BLE001
            print(f"  {place_id}: {e}", file=sys.stderr)
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"플레이스 {place_id} 정보를 받지 못했습니다")


def resolve(state, value):
    if isinstance(value, dict) and "__ref" in value:
        return state.get(value["__ref"], {})
    return value


def items(state, prefix):
    return [v for k, v in state.items() if k.startswith(prefix + ":")]


def place_detail(state):
    root = state["ROOT_QUERY"]
    return next(v for k, v in root.items() if k.startswith("placeDetail("))


def field(detail, name):
    for k, v in detail.items():
        if k == name or k.startswith(name + "("):
            return v
    return None


def area_of(jibun):
    parts = (jibun or "").split()
    for p in parts[2:]:
        if p.endswith(("동", "읍", "면")):
            return p
    return ""


def hours_of(detail):
    groups = field(detail, "newBusinessHours") or []
    rows = []
    for g in groups:
        for h in g.get("businessHours") or []:
            bh = h.get("businessHours") or {}
            text = f"{bh.get('start')}~{bh.get('end')}" if bh.get("start") else (h.get("description") or "휴무")
            breaks = [f"{b.get('start')}~{b.get('end')}" for b in h.get("breakHours") or []]
            if breaks:
                text += " (브레이크 " + ", ".join(breaks) + ")"
            last = h.get("lastOrderTimes") or []
            if last:
                text += " · 라스트오더 " + ", ".join(x.get("time", "") for x in last if x.get("time"))
            rows.append({"day": h.get("day"), "text": text})
    return rows


def photos_of(state, place_id, detail):
    place_url = f"https://m.place.naver.com/restaurant/{place_id}/photo"
    out, seen = [], set()

    def add(url, caption, kind, author="", date="", link=""):
        if not url or url in seen or len(out) >= PHOTO_TARGET:
            return
        seen.add(url)
        out.append({"url": url, "caption": caption, "kind": kind, "author": author, "date": date or "", "link": link or place_url})

    for p in items(state, "PlaceDetailTopPhotoItem"):
        if p.get("video") or not p.get("originalUrl"):
            continue
        author = resolve(state, p.get("author")) or {}
        is_business = "_business_" in p.get("id", "")
        add(
            p["originalUrl"],
            p.get("title") or "",
            "업체 등록" if is_business else "방문자",
            "" if is_business else (author.get("nickname") or ""),
            p.get("date"),
            p.get("linkUrl"),
        )
    for m in items(state, "PlaceMenuItem"):
        for img in m.get("images") or []:
            add(img.get("url"), m.get("name") or "메뉴", "업체 등록 메뉴")
    for img in field(detail, "menuImages") or []:
        add(img.get("imageUrl"), "메뉴판", "업체 등록 메뉴판")
    return out


def build_one(cand, fetched):
    pid = cand["placeId"]
    state = fetch_state(pid)
    detail = place_detail(state)
    base = next(iter(items(state, "PlaceDetailBase")))
    stats = next(iter(items(state, "VisitorReviewStatsResult")), {})
    voted = ((stats.get("analysis") or {}).get("votedKeyword") or {}).get("details") or []
    info = field(detail, "informationTab") or {}
    parking = (info.get("parkingInfo") or {}).get("description") or ""
    booking = field(detail, "naverBooking") or {}

    menus = []
    for m in items(state, "PlaceMenuItem"):
        price = (m.get("price") or {}).get("displayText") or m.get("price") or ""
        if isinstance(price, dict):
            price = ""
        menus.append({"name": m.get("name") or "", "price": price, "recommend": bool(m.get("recommend"))})

    photos = photos_of(state, pid, detail)
    coord = base.get("coordinate") or {}
    return {
        "id": pid,
        "name": cand.get("displayName") or base["name"],
        "naverName": base["name"],
        "givenName": cand["givenName"],
        "group": cand["group"],
        "category": base.get("category") or "",
        "area": area_of(base.get("address")),
        "roadAddress": base.get("roadAddress") or "",
        "jibunAddress": base.get("address") or "",
        "lat": float(coord["y"]),
        "lng": float(coord["x"]),
        "phone": base.get("virtualPhone") or base.get("phone") or "",
        "conveniences": base.get("conveniences") or [],
        "seats": [
            {"name": s.get("name"), "desc": s.get("description") or ""}
            for s in items(state, "RestaurantSeatItems")
        ],
        "parking": parking.strip(),
        "hours": hours_of(detail),
        "intro": (base.get("microReviews") or [""])[0],
        "menus": menus[:8],
        "rating": {
            "platform": "네이버 방문자 별점",
            "score": base.get("visitorReviewsScore"),
            "visitorReviews": base.get("visitorReviewsTotal"),
            "blogReviews": base.get("cafeBlogReviewsTotal"),
            "checkedAt": fetched,
        },
        "keywords": [{"text": k.get("displayName"), "count": k.get("count")} for k in voted[:5]],
        "bookingUrl": booking.get("naverBookingUrl") or "",
        "placeUrl": f"https://map.naver.com/p/entry/place/{pid}",
        "sources": cand["sources"],
        "matchNote": cand["matchNote"],
        "photos": photos,
    }


def main():
    candidates = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    fetched = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d")
    places = []
    for i, cand in enumerate(candidates):
        if i:
            time.sleep(6)
        place = build_one(cand, fetched)
        print(f"{place['name']}: 별점 {place['rating']['score']} · 사진 {len(place['photos'])}장")
        places.append(place)

    payload = json.dumps(places, ensure_ascii=False, indent=1)
    SNAPSHOT.write_text(payload + "\n", encoding="utf-8")
    html = INDEX.read_text(encoding="utf-8")
    a, b = html.index(START) + len(START), html.index(END)
    INDEX.write_text(html[:a] + payload.replace("</", "<\\/") + html[b:], encoding="utf-8")


if __name__ == "__main__":
    main()
