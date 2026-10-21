import time
import unittest
from unittest.mock import patch
from urllib.parse import quote

from datetime import datetime, timedelta, timezone

from app.collect import (
    BING_URL,
    COLLECT_GEN,
    COLLECT_SECS,
    DDG_URL,
    FAST_TIMEOUT,
    JINA_TIMEOUT,
    JINA_URL,
    KST,
    SEARCH_TIMEOUT,
    SOCIAL_REPLY_LIMITS,
    SOURCE_SECS,
    collect_budget,
    stale_runner,
    _pick_reply_parents,
    _social_comment_targets,
    _spread_targets,
    assign_blind_times,
    comments_need_backfill,
    empty_board,
    fetch_social,
    fetch_social_replies,
    fill_reply_excerpts,
    merge,
    qoo_label_time,
    social_needs_backfill,
)
from app.parsers import (
    canonicalize_social_url,
    parse_blind,
    parse_blind_comments,
    parse_dc,
    parse_dc_comments,
    parse_facebook_replies,
    parse_instagram_replies,
    parse_social_search,
    parse_theqoo,
    parse_theqoo_comments,
    parse_threads_replies,
    parse_youtube_comments,
    parse_youtube_search,
    parse_youtube_watch_meta,
)

DC_HTML = """
<table>
<tbody>
<tr class="ub-content" data-type="icon_notice">
  <td class="gall_num">공지</td>
  <td class="gall_tit"><a href="/board/view/?id=iamsolo&no=1"><b>공지사항</b></a></td>
</tr>
<tr class="ub-content us-post" data-no="6579809" data-type="icon_pic">
  <td class="gall_num">6579809</td>
  <td class="gall_tit ub-word">
    <a href="/board/view/?id=iamsolo&no=6579809&page=1">33영수 경찰복입고 거리에서 일하는거 찍힘</a>
    <a class="reply_numbox" href="/board/view/?id=iamsolo&no=6579809&t=cv"><span class="reply_num">[2]</span></a>
  </td>
  <td class="gall_writer ub-writer" data-nick="ㅇㅇ" data-uid="" data-ip="211.234">
    <span class="nickname"><em>ㅇㅇ</em></span><span class="ip">(211.234)</span>
  </td>
  <td class="gall_date" title="2026-10-13 12:21:00">12:21</td>
  <td class="gall_count">413</td>
  <td class="gall_recommend">19</td>
</tr>
<tr class="ub-content us-post" data-no="10">
  <td class="gall_tit"><a href="javascript:alert(1)">거절</a></td>
</tr>
</tbody>
</table>
"""

BLIND_HTML = """
<div class="article-list">
  <div class="article-list-pre article-list-ad nth-even"><h3><a href="/kr/post/ad-aaaa">광고</a></h3></div>
  <div class="article-list-pre nth-odd">
    <span class="category"><i class="category-label now">NOW</i></span>
    <div class="tit">
      <h3><a href="/kr/post/34%EC%98%81%EC%B2%A0-dmvylbme">34영철 악플 대박이넼ㅋㅋㅋㅋㅋㅋ</a></h3>
      <p class="pre-txt"><a href="/kr/post/34%EC%98%81%EC%B2%A0-dmvylbme">영철 신입때부터 같은 팀</a></p>
    </div>
    <div class="sub">
      <p class="name"><a href="/kr/post/34%EC%98%81%EC%B2%A0-dmvylbme">공무원 · 로****</a></p>
      <div class="wrap-info">
        <a class="pv"><i class="blind">조회수</i>4,093</a>
        <span class="like"><i class="blind">좋아요</i>13</span>
        <a class="cmt"><i class="blind">댓글</i>44</a>
        <a class="past"><i class="blind">작성시간</i>어제</a>
      </div>
    </div>
  </div>
</div>
"""


QOO_HTML = """
<table>
<tr class="notice">
  <td class="title"><a href="/iamsolo/4277558180">필독 공지</a></td>
  <td class="time">26.07.13</td>
</tr>
<tr>
  <td class="cate"><span>잡담</span></td>
  <td class="title">
    <a href="/iamsolo?group_srl=2944154583" class="preface">ㅇㄴㅅ)</a>
    <a href="/iamsolo/4374217007">돌싱앤모솔 2기 하네 ㅋㅋ</a>
    <a href="/iamsolo/4374217007#4374217007_comment" class="replyNum">3</a>
  </td>
  <td class="time">14:11</td>
  <td class="m_no">131</td>
</tr>
</table>
"""


class ParserTest(unittest.TestCase):
    def test_dc_skips_notice_and_unsafe_link(self):
        posts = parse_dc(DC_HTML)
        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertEqual(post["external_id"], "6579809")
        self.assertEqual(post["title"], "33영수 경찰복입고 거리에서 일하는거 찍힘")
        self.assertEqual(post["author"], "ㅇㅇ")
        self.assertEqual(post["ip"], "211.234")
        self.assertEqual(post["comments"], 2)
        self.assertEqual(post["recommends"], 19)
        self.assertEqual(post["views"], 413)
        self.assertTrue(post["url"].startswith("https://gall.dcinside.com/board/view/"))

    def test_blind_skips_ad_and_splits_name(self):
        posts = parse_blind(BLIND_HTML)
        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertEqual(post["title"], "34영철 악플 대박이넼ㅋㅋㅋㅋㅋㅋ")
        self.assertEqual(post["company"], "공무원")
        self.assertEqual(post["author"], "로****")
        self.assertEqual(post["excerpt"], "영철 신입때부터 같은 팀")
        self.assertEqual(post["views"], 4093)
        self.assertEqual(post["recommends"], 13)
        self.assertEqual(post["comments"], 44)
        self.assertEqual(post["posted_label"], "어제")
        self.assertEqual(post["badge"], "NOW")
        self.assertTrue(post["url"].startswith("https://www.teamblind.com/kr/post/"))

    def test_theqoo_skips_notice_and_preface(self):
        posts = parse_theqoo(QOO_HTML)
        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertEqual(post["external_id"], "4374217007")
        self.assertEqual(post["title"], "돌싱앤모솔 2기 하네 ㅋㅋ")
        self.assertEqual(post["author"], "무명의 더쿠")
        self.assertEqual(post["badge"], "잡담")
        self.assertEqual(post["posted_label"], "14:11")
        self.assertEqual(post["views"], 131)
        self.assertEqual(post["comments"], 3)
        self.assertEqual(post["url"], "https://theqoo.net/iamsolo/4374217007")

    def test_social_search_keeps_posts_and_skips_profiles(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        html = """
        <div class="result">
          <h2 class="result__title">
            <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.threads.com%2F%40masion.marim%2Fpost%2FDeOmNhbmP0l">나는 솔로 34기 다둥이 특집 현숙 • Threads, Say more</a>
          </h2>
          <a class="result__snippet">Marim (@masion.marim). 77 Replies. '나는 솔로' 34기 다둥이 특집 현숙</a>
        </div>
        <div class="result">
          <h2 class="result__title">
            <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.threads.com%2F%40seolleimparty">설레임파티 (@seolleimparty) • Threads, Say more</a>
          </h2>
          <a class="result__snippet">840 Followers</a>
        </div>
        """
        posts = parse_social_search(html, "threads", now)
        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertEqual(post["source"], "threads")
        self.assertEqual(post["external_id"], "DeOmNhbmP0l")
        self.assertEqual(post["author"], "@masion.marim")
        self.assertTrue(post["title"].startswith("나는 솔로 34기"))
        self.assertTrue(post["url"].startswith("https://www.threads.com/@masion.marim/post/DeOmNhbmP0l"))
        self.assertTrue(post["posted_at"].startswith("2026-10-08"))
        ig_html = """
        <div class="result">
          <h2 class="result__title">
            <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.instagram.com%2Fp%2FDepKS-IHSxr%2F">실시간검색이슈 | 나는솔로 34기 영호 | Instagram</a>
          </h2>
          <a class="result__snippet">나는솔로 34기 영호 전직장 동료</a>
        </div>
        """
        ig = parse_social_search(ig_html, "ig", now)[0]
        self.assertEqual(ig["external_id"], "DepKS-IHSxr")
        self.assertEqual(ig["author"], "실시간검색이슈")
        self.assertEqual(ig["url"], "https://www.instagram.com/p/DepKS-IHSxr/")
        fb_html = """
        <div class="result">
          <h2 class="result__title">
            <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.facebook.com%2FLov2Diary%2Fposts%2F%25EB%2582%2598%25EB%258A%2594%25EC%2586%2594%25EB%25A1%259C-34%25EA%25B8%25B0%2F1610763734181972%2F">연애일기 - 나는솔로 34기 영숙 폭로글 | Facebook</a>
          </h2>
          <a class="result__snippet">나는솔로 34기 영숙 폭로글 ㄷㄷ 24m</a>
        </div>
        """
        fb = parse_social_search(fb_html, "fb", now)[0]
        self.assertEqual(fb["external_id"], "1610763734181972")
        self.assertEqual(fb["url"], "https://www.facebook.com/Lov2Diary/posts/1610763734181972")
        self.assertEqual(fb["posted_at"], "2026-10-21T11:36:00+09:00")
        self.assertIsNone(canonicalize_social_url("https://www.instagram.com/popular/나솔-34기/"))
        self.assertIsNone(canonicalize_social_url("https://www.threads.com/@masion.marim"))
        bing = canonicalize_social_url(
            "https://www.bing.com/ck/a?!&&p=x&u=a1aHR0cHM6Ly93d3cuZmFjZWJvb2suY29tL0xvdjJEaWFyeS9wb3N0cy8xNjEwNzYzNzM0MTgxOTcyLw"
        )
        self.assertEqual(bing[0], "fb")
        self.assertEqual(bing[1], "1610763734181972")
        fb_oct_html = """
        <li class="b_algo">
          <h2><a href="https://www.facebook.com/HR5MM/posts/1188713067151398">나는솔로 34기 순자 폭로글</a></h2>
          <div class="b_caption">나는솔로 34기 간호사 순자</div>
          <cite>facebook.com</cite>
          <span class="news_dt">2026년 10월 8일</span>
        </li>
        """
        fb_oct = parse_social_search(fb_oct_html, "fb", now)[0]
        self.assertEqual(fb_oct["external_id"], "1188713067151398")
        self.assertTrue(fb_oct["posted_at"].startswith("2026-10-08"))

    def test_youtube_search_and_top_level_comments(self):
        videos, _token = parse_youtube_search(
            {
                "videoRenderer": {
                    "videoId": "abc123",
                    "title": {"simpleText": "34기 예고"},
                    "ownerText": {"runs": [{"text": "촌장"}]},
                    "publishedTimeText": {"simpleText": "5일 전"},
                }
            }
        )
        self.assertEqual(videos[0]["video_id"], "abc123")
        self.assertEqual(videos[0]["published_label"], "5일 전")
        self.assertEqual(videos[0]["description"], "")
        meta = parse_youtube_watch_meta(
            'var ytInitialPlayerResponse = {"videoDetails":{"title":"나솔사계 LIVE","shortDescription":"사계 본방 다시보기"}};'
        )
        self.assertEqual(meta["title"], "나솔사계 LIVE")
        self.assertIn("사계", meta["description"])
        comments, _next = parse_youtube_comments(
            {
                "a": {
                    "commentEntityPayload": {
                        "properties": {
                            "commentId": "cid1",
                            "replyLevel": 0,
                            "content": {"content": "영숙 미쳤다"},
                            "publishedTime": "2시간 전",
                        },
                        "author": {"displayName": "@viewer"},
                    }
                },
                "b": {
                    "commentEntityPayload": {
                        "properties": {
                            "commentId": "cid2",
                            "replyLevel": 1,
                            "content": {"content": "답글"},
                            "publishedTime": "1시간 전",
                        },
                        "author": {"displayName": "@reply"},
                    }
                },
            },
            videos[0],
        )
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["title"], "영숙 미쳤다")
        self.assertEqual(comments[0]["source"], "yt")
        self.assertIn("v=abc123", comments[0]["url"])

    def test_dc_qoo_blind_comments_become_replies(self):
        parent = {
            "url": "https://gall.dcinside.com/board/view/?id=iamsolo&no=6599419",
            "external_id": "6599419",
            "title": "영숙은 조용히 살더라 원글",
        }
        now = datetime(2026, 10, 20, 10, 0, tzinfo=timezone(timedelta(hours=9)))
        dc = parse_dc_comments(
            {
                "comments": [
                    {
                        "no": "10960004",
                        "name": "나갤러1",
                        "ip": "119.202",
                        "reg_date": "10.20 09:56:00",
                        "del_yn": "N",
                        "is_delete": "0",
                        "memo": "영숙은 조용히 살더라",
                        "rcnt": "0",
                    },
                    {
                        "no": "10960010",
                        "name": "ㅇㅇ",
                        "ip": "1.1",
                        "reg_date": "10.20 09:57:00",
                        "del_yn": "Y",
                        "is_delete": "1",
                        "memo": "지운 댓글",
                    },
                ]
            },
            parent,
            now=now,
        )
        self.assertEqual(len(dc), 1)
        self.assertEqual(dc[0]["external_id"], "cmt-10960004")
        self.assertEqual(dc[0]["kind"], "reply")
        self.assertEqual(dc[0]["title"], "영숙은 조용히 살더라")
        self.assertEqual(dc[0]["excerpt"], "영숙은 조용히 살더라 원글")
        mentioned = parse_dc_comments(
            {
                "comments": [
                    {
                        "no": "5",
                        "name": "ㅇㅇ",
                        "reg_date": "10.20 09:20:00",
                        "del_yn": "N",
                        "is_delete": "0",
                        "memo": "@나갤러1(106.101) 영숙 옷이 이상함",
                    }
                ]
            },
            parent,
            now=now,
        )
        self.assertEqual(mentioned[0]["title"], "영숙 옷이 이상함")
        self.assertEqual(dc[0]["author"], "나갤러1")
        self.assertEqual(dc[0]["posted_at"], "2026-10-20T09:56:00+09:00")
        self.assertTrue(dc[0]["url"].endswith("#cmt_10960004"))

        qoo = parse_theqoo_comments(
            {
                "comment_list": [
                    {"srl": 4378285239, "ct": "영철 옷 뭐야", "rd": "20261017141952"},
                    {
                        "srl": 1,
                        "ct": '<span class="commentWarningMessage">비회원은 작성한 지 1시간 이내의 댓글은 읽을 수 없습니다.</span>',
                        "rd": "20261020093522",
                    },
                ]
            },
            {"url": "https://theqoo.net/iamsolo/4378274172", "external_id": "4378274172", "title": "더쿠 원글"},
        )
        self.assertEqual(len(qoo), 1)
        self.assertEqual(qoo[0]["source"], "qoo")
        self.assertEqual(qoo[0]["title"], "영철 옷 뭐야")
        self.assertEqual(qoo[0]["excerpt"], "더쿠 원글")
        self.assertEqual(qoo[0]["posted_at"], "2026-10-17T14:19:52+09:00")
        self.assertEqual(qoo[0]["kind"], "reply")

        blind = parse_blind_comments(
            """
            <div class="wrap-comment" id="457350870">
              <p class="name"><span class="cp">공무원</span> · d******</p>
              <p class="cmt-txt"><span>영자 얘기가 구라라는 댓글</span></p>
              <div class="wrap-info"><span class="date"><i class="blind">작성일</i>2시간</span>
              <span class="like"><i class="blind">좋아요수</i>3</span></div>
            </div>
            <div class="wrap-comment" id="9">
              <p class="cmt-txt delete"><span>삭제된 댓글입니다</span></p>
            </div>
            """,
            {"url": "https://www.teamblind.com/kr/post/sample", "external_id": "/kr/post/sample", "title": "블라인드 원글"},
        )
        self.assertEqual(len(blind), 1)
        self.assertEqual(blind[0]["source"], "blind")
        self.assertEqual(blind[0]["title"], "영자 얘기가 구라라는 댓글")
        self.assertEqual(blind[0]["excerpt"], "블라인드 원글")
        self.assertEqual(blind[0]["company"], "공무원")
        self.assertEqual(blind[0]["author"], "d******")
        self.assertEqual(blind[0]["posted_label"], "2시간")
        self.assertEqual(blind[0]["recommends"], 3)
        self.assertEqual(blind[0]["kind"], "reply")


def _ddg_hit(url: str, title: str, snippet: str) -> str:
    return (
        '<div class="result"><h2 class="result__title">'
        f'<a class="result__a" href="//duckduckgo.com/l/?uddg={quote(url, safe="")}">{title}</a>'
        f'</h2><a class="result__snippet">{snippet}</a></div>'
    )


def _bing_hit(url: str, title: str, snippet: str, dated: str = "") -> str:
    stamp = f'<span class="news_dt">{dated}</span>' if dated else ""
    return (
        f'<li class="b_algo"><h2><a href="{url}">{title}</a></h2>'
        f'<div class="b_caption">{stamp}{snippet}</div></li>'
    )


class _FakeSearch:
    def __init__(self, table: dict[tuple[str, str, str], tuple[str, int]]):
        self.table = table
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, url, params=None, headers=None):
        params = dict(params or {})
        self.calls.append((url, params))
        offset = params.get("first") or "1" if url == BING_URL else params.get("s") or "0"
        key = (url, params.get("q", ""), offset)
        html, status = self.table.get(key, ("", 200))

        class _Resp:
            def __init__(self, text: str, status_code: int):
                self.text = text
                self.status_code = status_code

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError(self.status_code)

        return _Resp(html, status)


class SocialCollectTest(unittest.TestCase):
    def test_sparse_social_source_needs_two_week_pages(self):
        board = empty_board()
        self.assertTrue(social_needs_backfill(board, "ig"))
        board["socialCrawl"] = {"ig": {"done": True, "pages": {}, "doneQueries": []}}
        self.assertFalse(social_needs_backfill(board, "ig"))
        board["socialCrawl"] = {"ig": {"done": False, "pages": {"site:instagram.com 나는솔로": 3}}}
        self.assertTrue(social_needs_backfill(board, "ig"))
        board["socialCrawl"] = {"fb": {"done": False}}
        self.assertTrue(social_needs_backfill(board, "fb"))

    @patch("app.collect.time.sleep", lambda *_a, **_k: None)
    def test_social_backfill_turns_search_pages(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        q = "site:instagram.com 나는솔로"
        pages = {
            (DDG_URL, q, "0"): (
                _ddg_hit(
                    "https://www.instagram.com/p/DepKS-IHSxr/",
                    "나는솔로 34기 영호",
                    "나는솔로 34기 영호 전직장 동료",
                ),
                200,
            ),
            (DDG_URL, q, "10"): (
                _ddg_hit(
                    "https://www.instagram.com/p/DeMqPBnDz77/",
                    "나는솔로 34기 인터뷰",
                    "SBS Plus 나는솔로 34기",
                ),
                200,
            ),
            (BING_URL, q, "1"): (
                _bing_hit(
                    "https://www.instagram.com/p/DefnuQ0CU8O/",
                    "나는솔로 34기 다둥이",
                    "나는솔로 34기 다둥이 특집",
                ),
                200,
            ),
            (BING_URL, q, "11"): (
                _bing_hit(
                    "https://www.instagram.com/reel/DeMqs5hiDLP/",
                    "나는솔로 주말",
                    "나는솔로 34기 주말",
                ),
                200,
            ),
        }
        client = _FakeSearch(pages)
        posts = fetch_social(client, "ig", now, backfill=True)
        ids = {item["external_id"] for item in posts}
        self.assertEqual(ids, {"DepKS-IHSxr", "DeMqPBnDz77", "DefnuQ0CU8O", "DeMqs5hiDLP"})
        ddg_offsets = [params.get("s", "0") for url, params in client.calls if url == DDG_URL and params.get("q") == q]
        bing_firsts = [params.get("first", "1") for url, params in client.calls if url == BING_URL and params.get("q") == q]
        self.assertIn("10", ddg_offsets)
        self.assertIn("11", bing_firsts)
        extra = [params.get("q") for _, params in client.calls if "10월" in params.get("q", "")]
        self.assertTrue(extra)

    @patch("app.collect.time.sleep", lambda *_a, **_k: None)
    def test_social_backfill_resumes_after_seen_pages(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        q = "site:instagram.com 나는솔로"
        crawl = {"pages": {q: 1}, "doneQueries": [], "done": False}
        client = _FakeSearch(
            {
                (DDG_URL, q, "0"): (
                    _ddg_hit(
                        "https://www.instagram.com/p/DepKS-IHSxr/",
                        "나는솔로 34기 영호",
                        "나는솔로 34기",
                    ),
                    200,
                ),
                (DDG_URL, q, "10"): (
                    _ddg_hit(
                        "https://www.instagram.com/p/DeMqPBnDz77/",
                        "나는솔로 34기 인터뷰",
                        "나는솔로 34기",
                    ),
                    200,
                ),
            }
        )
        posts = fetch_social(client, "ig", now, backfill=True, crawl=crawl)
        ids = {item["external_id"] for item in posts}
        self.assertIn("DeMqPBnDz77", ids)
        self.assertNotIn("DepKS-IHSxr", ids)
        ddg_offsets = [params.get("s") for url, params in client.calls if url == DDG_URL and params.get("q") == q]
        self.assertNotIn(None, ddg_offsets)
        self.assertIn("10", ddg_offsets)

    @patch("app.collect.time.sleep", lambda *_a, **_k: None)
    def test_finished_query_is_not_opened_again(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        q = "site:instagram.com 나는솔로"
        crawl = {"pages": {q: 8}, "doneQueries": [q], "done": False}
        client = _FakeSearch({})
        posts = fetch_social(client, "ig", now, backfill=True, crawl=crawl)
        self.assertEqual(posts, [])
        self.assertFalse(any(params.get("q") == q for _, params in client.calls))

    @patch("app.collect.time.sleep", lambda *_a, **_k: None)
    def test_social_deadline_skips_search(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        client = _FakeSearch(
            {
                (DDG_URL, "site:instagram.com 나는솔로", "0"): (
                    _ddg_hit(
                        "https://www.instagram.com/p/DepKS-IHSxr/",
                        "나는솔로 34기 영호",
                        "나는솔로 34기",
                    ),
                    200,
                ),
            }
        )
        posts = fetch_social(client, "ig", now, backfill=True, deadline=time.monotonic() - 1)
        self.assertEqual(posts, [])
        self.assertEqual(client.calls, [])

    @patch("app.collect.time.sleep", lambda *_a, **_k: None)
    def test_ddg_challenge_skips_later_queries(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        q = "site:instagram.com 나는솔로"
        client = _FakeSearch(
            {
                (DDG_URL, q, "0"): ('<div class="anomaly-modal">If this persists</div>', 202),
                (BING_URL, q, "1"): (
                    _bing_hit(
                        "https://www.instagram.com/p/DepKS-IHSxr/",
                        "나는솔로 34기 영호",
                        "나는솔로 34기",
                    ),
                    200,
                ),
            }
        )
        posts = fetch_social(client, "ig", now, backfill=True)
        self.assertEqual([item["external_id"] for item in posts], ["DepKS-IHSxr"])
        ddg_queries = [params.get("q") for url, params in client.calls if url == DDG_URL]
        self.assertEqual(ddg_queries, [q, q])

    @patch("app.collect.time.sleep", lambda *_a, **_k: None)
    def test_live_social_stays_on_first_page(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        hit = _ddg_hit(
            "https://www.instagram.com/p/DepKS-IHSxr/",
            "나는솔로 34기 영호",
            "나는솔로 34기",
        )
        client = _FakeSearch(
            {
                (DDG_URL, "site:instagram.com 나는솔로", "0"): (hit, 200),
                (DDG_URL, "site:instagram.com 나솔 34기", "0"): (hit, 200),
                (DDG_URL, "site:instagram.com 나는solo", "0"): (hit, 200),
                (DDG_URL, "site:instagram.com 나는솔로", "10"): (
                    _ddg_hit(
                        "https://www.instagram.com/p/DeMqPBnDz77/",
                        "나는솔로 34기 인터뷰",
                        "나는솔로 34기",
                    ),
                    200,
                ),
            }
        )
        posts = fetch_social(client, "ig", now, backfill=False)
        self.assertEqual([item["external_id"] for item in posts], ["DepKS-IHSxr"])
        ddg_offsets = [params.get("s") for url, params in client.calls if url == DDG_URL]
        self.assertEqual(ddg_offsets, [None, None, None])
        self.assertFalse(any("10월" in params.get("q", "") for _, params in client.calls))
        self.assertFalse(
            any(params.get("first") for url, params in client.calls if url == BING_URL)
        )


def sample(external_id, title, posted_at="2026-10-13T12:00:00+09:00"):
    return {
        "source": "dc",
        "external_id": external_id,
        "title": title,
        "excerpt": "",
        "author": "이봐",
        "company": "",
        "ip": "1.1",
        "badge": "",
        "url": f"https://gall.dcinside.com/board/view/?id=iamsolo&no={external_id}",
        "posted_label": "12:00",
        "posted_at": posted_at,
        "views": 1,
        "recommends": 0,
        "comments": 0,
    }


class MergeTest(unittest.TestCase):
    def test_appends_only_new_posts_in_time_order(self):
        board = empty_board()
        added = merge(
            board,
            {"dc": [sample("2", "영호는 조용", "2026-10-13T12:05:00+09:00"), sample("1", "영숙 첫 글", "2026-10-13T12:00:00+09:00")]},
            now="2026-10-13T03:00:00+00:00",
        )
        self.assertEqual(added, 2)
        self.assertEqual(board["startedAt"], "2026-10-07T22:30:00+09:00")
        self.assertEqual([post["externalId"] for post in board["posts"]], ["1", "2"])
        added = merge(
            board,
            {"dc": [sample("3", "새 글", "2026-10-13T12:10:00+09:00"), sample("2", "영호는 조용", "2026-10-13T12:05:00+09:00")]},
            now="2026-10-13T03:05:00+00:00",
        )
        self.assertEqual(added, 1)
        self.assertEqual(board["posts"][-1]["title"], "새 글")
        self.assertEqual(len(board["posts"]), 3)

    def test_drops_posts_before_cutoff(self):
        board = empty_board()
        added = merge(
            board,
            {
                "dc": [
                    sample("3", "이후", "2026-10-07T22:30:00+09:00"),
                    sample("2", "이전", "2026-10-07T22:29:00+09:00"),
                ]
            },
        )
        self.assertEqual(added, 1)
        self.assertEqual(board["posts"][0]["title"], "이후")

    def test_blind_relative_times_keep_recent_posts_ahead_of_yesterday(self):
        now = datetime(2026, 10, 13, 15, 0, tzinfo=timezone(timedelta(hours=9)))
        items = [
            {"posted_label": "어제"},
            {"posted_label": "28분"},
            {"posted_label": "어제"},
        ]
        assign_blind_times(items, now)
        self.assertGreater(items[1]["posted_at"], items[0]["posted_at"])
        self.assertGreater(items[0]["posted_at"], items[2]["posted_at"])

    def test_drops_sagye_youtube_comments(self):
        board = empty_board()
        item = sample("cid-sagye", "영숙 선택 잘했다")
        item["source"] = "yt"
        item["excerpt"] = "[나솔사계 LIVE] 현커는 과연 몇 커플?"
        item["url"] = "https://www.youtube.com/watch?v=dhcjtjrgc-f4z2v&lc=cid-sagye"
        added = merge(board, {"yt": [item]})
        self.assertEqual(added, 0)
        self.assertEqual(board["posts"], [])

    def test_drops_blocked_youtube_comments(self):
        board = empty_board()
        item = sample("cid", "HBM 반도체")
        item["source"] = "yt"
        item["excerpt"] = "[나는솔로] 34기 상철 광수 영식 직장동료 지인 등판 충격 폭로! #나는솔로#나는솔로#나는솔로#나는솔로"
        item["url"] = "https://www.youtube.com/watch?v=qpUKcCsjHSI&lc=cid"
        added = merge(board, {"yt": [item]})
        self.assertEqual(added, 0)
        self.assertEqual(board["posts"], [])

    def test_purges_blocked_youtube_already_stored(self):
        board = empty_board()
        board["posts"] = [
            {
                "id": 1,
                "source": "yt",
                "externalId": "cid",
                "title": "HBM",
                "excerpt": "[나는솔로] 34기 상철 광수 영식 직장동료 지인 등판",
                "author": "@x",
                "company": "",
                "ip": "",
                "badge": "",
                "url": "https://www.youtube.com/watch?v=qpUKcCsjHSI&lc=cid",
                "postedLabel": "방금",
                "postedAt": "2026-10-13T12:00:00+09:00",
                "views": None,
                "recommends": None,
                "comments": None,
                "firstSeenAt": "2026-10-13T03:00:00+00:00",
                "isSeed": False,
            }
        ]
        added = merge(board, {"yt": []})
        self.assertEqual(added, 0)
        self.assertEqual(board["posts"], [])

    def test_theqoo_date_keeps_cutoff_day_and_drops_the_day_before(self):
        now = datetime(2026, 10, 13, 15, 0, tzinfo=timezone(timedelta(hours=9)))
        board = empty_board()
        kept = sample("7", "7일", qoo_label_time("10.07", now).isoformat())
        dropped = sample("6", "6일", qoo_label_time("10.06", now).isoformat())
        kept["source"] = "qoo"
        dropped["source"] = "qoo"
        added = merge(board, {"qoo": [kept, dropped]})
        self.assertEqual(added, 1)
        self.assertEqual(board["posts"][0]["title"], "7일")

    def test_reply_targets_are_spread_across_hours(self):
        now = datetime(2026, 10, 20, 10, 0, tzinfo=KST)
        posts = []
        for hour in range(6):
            for step in range(3):
                posts.append(
                    {
                        "external_id": f"{hour}-{step}",
                        "comments": 2,
                        "posted_at": (now - timedelta(hours=hour, minutes=step)).isoformat(),
                    }
                )
        picked = _spread_targets(posts, 6, now)
        self.assertEqual([item["external_id"] for item in picked], ["0-0", "1-0", "2-0", "3-0", "4-0", "5-0"])

    def test_reply_keeps_kind_and_comment_id(self):
        board = empty_board()
        item = sample("cmt-10960004", "영숙은 조용히 살더라", "2026-10-20T09:56:00+09:00")
        item["kind"] = "reply"
        item["author"] = "이봐"
        added = merge(board, {"dc": [item]}, now="2026-10-20T01:00:00+00:00")
        self.assertEqual(added, 1)
        self.assertEqual(board["posts"][0]["kind"], "reply")
        self.assertEqual(board["posts"][0]["externalId"], "cmt-10960004")

    def test_fill_reply_excerpts_copies_parent_title(self):
        board = empty_board()
        board["posts"] = [
            {
                "id": 1,
                "source": "dc",
                "externalId": "6599082",
                "title": "원글 제목",
                "excerpt": "",
                "url": "https://gall.dcinside.com/board/view/?id=iamsolo&no=6599082",
            },
            {
                "id": 2,
                "source": "dc",
                "externalId": "cmt-1",
                "title": "댓글 본문",
                "excerpt": "",
                "url": "https://gall.dcinside.com/board/view/?id=iamsolo&no=6599082#cmt_1",
                "kind": "reply",
            },
        ]
        filled = fill_reply_excerpts(board)
        self.assertEqual(filled, 1)
        self.assertEqual(board["posts"][1]["excerpt"], "원글 제목")


THREADS_REPLY_MD = """
# [Thread](https://www.threads.com/@masion.marim/post/DeOmNhbmP0l)

[masion.marim](https://www.threads.com/@masion.marim)

[10/08/26](https://www.threads.com/@masion.marim/post/DeOmNhbmP0l)

‘나는 솔로’ 34기 다둥이 특집 현숙

사실상 압도적이다.

[happytree1303](https://www.threads.com/@happytree1303)

[10/08/26](https://www.threads.com/@happytree1303/post/DeOpJlmEg-H)

맞지. 옥순이도 상대가 안됨. 딴건 모르겠고 영숙이는 참 많이 모나보이고

137

2

[goat.8403753](https://www.threads.com/@goat.8403753)

[10/08/26](https://www.threads.com/@goat.8403753/post/DeO1xqvGfON)

기운이 밝아

37

[masion.marim](https://www.threads.com/@masion.marim)

[10/08/26](https://www.threads.com/@masion.marim/post/DeO5ZKzGNSK)

·Author

👍

[gibuni_11](https://www.threads.com/@gibuni_11)

[10/08/26](https://www.threads.com/@gibuni_11/post/DeO7Rh_FPuq)

22옥순닮은듯

Related threads

[glob_alspoon](https://www.threads.com/@glob_alspoon)

[10/06/26](https://www.threads.com/@glob_alspoon/post/DeK7zQSklwg)

나는 솔로 33기 광수
"""

IG_REPLY_MD = """
SBS Plus | #나는솔로 진지한 인터뷰

[sbsplus](https://www.instagram.com/sbsplus/)

# Comments

[nami_fan](https://www.instagram.com/nami_fan/)
영철 인터뷰 실화냐
2 likes
[Reply](https://www.instagram.com/p/DeMqPBnDz77/)
"""

FB_REPLY_MD = """
나는솔로 34기 간호사 순자

# Comments

[하루5분](https://www.facebook.com/HR5MM)
순자 직장 얘기 봤음
Like · Reply · 2h
"""


class _FakeJina:
    def __init__(self, pages: dict[str, tuple[object, int]]):
        self.pages = pages
        self.calls: list[str] = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        payload, status = self.pages.get(url, ("", 200))

        class _Resp:
            def __init__(self, body, status_code: int):
                self.status_code = status_code
                self._body = body
                if isinstance(body, str):
                    self.text = body
                else:
                    self.text = __import__("json").dumps(body)

            def json(self):
                if isinstance(self._body, dict):
                    return self._body
                return __import__("json").loads(self.text)

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError(self.status_code)

        return _Resp(payload, status)


class SocialReplyTest(unittest.TestCase):
    def setUp(self):
        self.parent = {
            "source": "threads",
            "external_id": "DeOmNhbmP0l",
            "title": "나는솔로 34기 다둥이 특집 현숙",
            "url": "https://www.threads.com/@masion.marim/post/DeOmNhbmP0l",
            "posted_at": "2026-10-08T18:19:47+09:00",
        }

    def test_threads_replies_skip_parent_and_related(self):
        posts = parse_threads_replies(THREADS_REPLY_MD, self.parent)
        ids = [item["external_id"] for item in posts]
        self.assertEqual(ids, ["cmt-DeOpJlmEg-H", "cmt-DeO1xqvGfON", "cmt-DeO5ZKzGNSK", "cmt-DeO7Rh_FPuq"])
        self.assertEqual(posts[0]["title"], "맞지. 옥순이도 상대가 안됨. 딴건 모르겠고 영숙이는 참 많이 모나보이고")
        self.assertEqual(posts[1]["title"], "기운이 밝아")
        self.assertEqual(posts[2]["title"], "👍")
        self.assertEqual(posts[0]["kind"], "reply")
        self.assertEqual(posts[0]["excerpt"], self.parent["title"])
        self.assertEqual(posts[0]["author"], "@happytree1303")
        self.assertTrue(all(item["excerpt"] == self.parent["title"] for item in posts))
        self.assertNotIn("cmt-DeK7zQSklwg", ids)
        self.assertNotIn("cmt-DeOmNhbmP0l", ids)

    def test_instagram_and_facebook_comment_markdown(self):
        ig_parent = {
            "source": "ig",
            "external_id": "DeMqPBnDz77",
            "title": "SBS Plus | #나는솔로 진지한 인터뷰",
            "url": "https://www.instagram.com/reel/DeMqPBnDz77/",
        }
        ig = parse_instagram_replies(IG_REPLY_MD, ig_parent)
        self.assertEqual(len(ig), 1)
        self.assertEqual(ig[0]["title"], "영철 인터뷰 실화냐")
        self.assertEqual(ig[0]["kind"], "reply")
        self.assertEqual(ig[0]["excerpt"], ig_parent["title"])
        fb_parent = {
            "source": "fb",
            "external_id": "1188713067151398",
            "title": "나는솔로 34기 간호사 순자",
            "url": "https://www.facebook.com/HR5MM/posts/1188713067151398",
        }
        fb = parse_facebook_replies(FB_REPLY_MD, fb_parent)
        self.assertEqual(len(fb), 1)
        self.assertEqual(fb[0]["title"], "순자 직장 얘기 봤음")
        self.assertEqual(fb[0]["source"], "fb")

    def test_comments_need_backfill_includes_new_social_and_counted_posts(self):
        posts = [
            {"source": "threads", "externalId": "DeOmNhbmP0l", "url": "https://www.threads.com/@a/post/DeOmNhbmP0l"},
            {"source": "dc", "externalId": "1", "comments": 3, "url": "https://gall.dcinside.com/board/view/?id=iamsolo&no=1"},
            {"source": "dc", "externalId": "2", "comments": 0, "url": "https://gall.dcinside.com/board/view/?id=iamsolo&no=2"},
            {"source": "blind", "externalId": "b1", "comments": None, "url": "https://www.teamblind.com/kr/post/b1"},
        ]
        self.assertTrue(comments_need_backfill(posts, {}))
        self.assertTrue(comments_need_backfill(posts, {"threads": {"doneIds": ["DeOmNhbmP0l"]}}))
        self.assertTrue(
            comments_need_backfill(
                posts,
                {"threads": {"doneIds": ["DeOmNhbmP0l"]}, "dc": {"doneIds": ["1"]}},
            )
        )
        self.assertFalse(
            comments_need_backfill(
                posts,
                {
                    "threads": {"doneIds": ["DeOmNhbmP0l"]},
                    "dc": {"doneIds": ["1"]},
                    "blind": {"doneIds": ["b1"]},
                },
            )
        )

    def test_stored_board_comments_are_queued_with_live_posts(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        found = [
            {
                "external_id": "live",
                "comments": 2,
                "posted_at": now.isoformat(),
                "url": "https://gall.dcinside.com/board/view/?id=iamsolo&no=live",
            }
        ]
        stored = [
            {
                "external_id": "old",
                "comments": 4,
                "posted_at": "2026-10-08T12:00:00+09:00",
                "url": "https://gall.dcinside.com/board/view/?id=iamsolo&no=old",
            }
        ]
        picked = _pick_reply_parents(
            found,
            stored,
            {},
            now,
            source="dc",
            live_limit=8,
            stored_limit=10,
            require_count=True,
        )
        ids = [item["external_id"] for item in picked]
        self.assertEqual(ids, ["live", "old"])

    def test_unread_social_parents_are_oldest_first(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        posts = [
            {
                "source": "threads",
                "external_id": "new1",
                "url": "https://www.threads.com/@a/post/new1",
                "posted_at": "2026-10-20T12:00:00+09:00",
            },
            {
                "source": "threads",
                "external_id": "old1",
                "url": "https://www.threads.com/@a/post/old1",
                "posted_at": "2026-10-08T12:00:00+09:00",
            },
            {
                "source": "threads",
                "external_id": "done1",
                "url": "https://www.threads.com/@a/post/done1",
                "posted_at": "2026-10-21T10:00:00+09:00",
            },
        ]
        picked = _social_comment_targets(
            posts,
            {"doneIds": ["done1"]},
            now,
            limit=8,
            source="threads",
            fresh_ids={"new1"},
        )
        self.assertEqual([item["external_id"] for item in picked], ["new1", "old1", "done1"])

    def test_finished_old_instagram_is_not_reopened(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        posts = [
            {
                "source": "ig",
                "external_id": "oldig",
                "url": "https://www.instagram.com/p/oldig/",
                "posted_at": "2026-10-21T10:00:00+09:00",
            }
        ]
        picked = _social_comment_targets(
            posts,
            {"doneIds": ["oldig"]},
            now,
            limit=8,
            source="ig",
        )
        self.assertEqual(picked, [])

    @patch("app.collect.time.sleep", lambda *_a, **_k: None)
    def test_fetch_social_replies_reads_jina_and_marks_done(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        parent = dict(self.parent)
        client = _FakeJina(
            {
                JINA_URL + parent["url"]: (
                    {"code": 200, "data": {"content": THREADS_REPLY_MD}},
                    200,
                )
            }
        )
        crawl = {}
        posts = fetch_social_replies(client, [parent], now, crawl=crawl)
        self.assertEqual(len(posts), 4)
        self.assertEqual(posts[0]["kind"], "reply")
        self.assertIn("DeOmNhbmP0l", crawl["threads"]["doneIds"])
        self.assertEqual(client.calls, [JINA_URL + parent["url"]])

    @patch("app.collect.time.sleep", lambda *_a, **_k: None)
    def test_empty_instagram_page_is_retried_later(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        parent = {
            "source": "ig",
            "external_id": "DeMqPBnDz77",
            "title": "SBS Plus | #나는솔로 진지한 인터뷰",
            "url": "https://www.instagram.com/reel/DeMqPBnDz77/",
        }
        client = _FakeJina(
            {
                JINA_URL + parent["url"]: (
                    {"code": 200, "data": {"content": "Log in to Instagram\nSee photos"}},
                    200,
                )
            }
        )
        crawl = {}
        posts = fetch_social_replies(client, [parent], now, crawl=crawl)
        self.assertEqual(posts, [])
        self.assertEqual(client.calls, [JINA_URL + parent["url"], JINA_URL + parent["url"]])
        self.assertNotIn("DeMqPBnDz77", crawl.get("ig", {}).get("doneIds", []))

    @patch("app.collect.time.sleep", lambda *_a, **_k: None)
    def test_blocked_jina_is_retried_later(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        parent = {
            "source": "ig",
            "external_id": "DeMqPBnDz77",
            "title": "SBS Plus | #나는솔로 진지한 인터뷰",
            "url": "https://www.instagram.com/reel/DeMqPBnDz77/",
        }
        client = _FakeJina(
            {
                JINA_URL + parent["url"]: (
                    {"code": 403, "name": "AbuseAlleviationError", "data": None},
                    403,
                )
            }
        )
        crawl = {}
        posts = fetch_social_replies(client, [parent], now, crawl=crawl)
        self.assertEqual(posts, [])
        self.assertEqual(client.calls, [JINA_URL + parent["url"], JINA_URL + parent["url"]])
        self.assertNotIn("DeMqPBnDz77", crawl.get("ig", {}).get("doneIds", []))

    @patch("app.collect.time.sleep", lambda *_a, **_k: None)
    def test_social_reply_deadline_skips_jina(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        client = _FakeJina({})
        posts = fetch_social_replies(
            client,
            [self.parent],
            now,
            deadline=time.monotonic() - 1,
            crawl={},
        )
        self.assertEqual(posts, [])
        self.assertEqual(client.calls, [])

    def test_source_clocks_cover_every_board(self):
        self.assertEqual(tuple(SOURCE_SECS), ("dc", "blind", "qoo", "threads", "ig", "fb"))
        self.assertEqual(COLLECT_SECS, sum(SOURCE_SECS.values()))
        self.assertLess(SOURCE_SECS["dc"], SOURCE_SECS["ig"])
        self.assertLess(SOURCE_SECS["blind"], SOURCE_SECS["fb"])
        self.assertLess(SOURCE_SECS["qoo"], SOURCE_SECS["threads"])
        self.assertLess(FAST_TIMEOUT.read, SEARCH_TIMEOUT.read)
        self.assertLess(SEARCH_TIMEOUT.read, JINA_TIMEOUT.read)
        self.assertGreaterEqual(SOURCE_SECS["ig"], 150)
        self.assertGreaterEqual(SOURCE_SECS["fb"], 150)
        self.assertGreaterEqual(SOURCE_SECS["threads"], 150)
        self.assertGreaterEqual(JINA_TIMEOUT.read, 150)
        self.assertEqual(SOCIAL_REPLY_LIMITS, {"threads": 3, "ig": 1, "fb": 1})

    def test_stale_github_runner_hands_off(self):
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}, clear=True):
            self.assertTrue(stale_runner())
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "COLLECT_GEN": COLLECT_GEN}, clear=True):
            self.assertFalse(stale_runner())
        with patch.dict("os.environ", {"COLLECT_GEN": COLLECT_GEN, "COLLECT_DEADLINE": "70"}, clear=True):
            self.assertFalse(stale_runner())
            self.assertEqual(collect_budget(), 70)

    @patch("app.collect.time.sleep", lambda *_a, **_k: None)
    def test_empty_instagram_does_not_block_facebook(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        ig_parents = [
            {
                "source": "ig",
                "external_id": f"ig{i}",
                "title": "나는솔로 34기",
                "url": f"https://www.instagram.com/p/ig{i}/",
            }
            for i in range(4)
        ]
        fb_parent = {
            "source": "fb",
            "external_id": "1188713067151398",
            "title": "나는솔로 34기 간호사 순자",
            "url": "https://www.facebook.com/HR5MM/posts/1188713067151398",
        }
        pages = {
            JINA_URL + parent["url"]: (
                {"code": 200, "data": {"content": "Log in to Instagram\nSee photos"}},
                200,
            )
            for parent in ig_parents
        }
        pages[JINA_URL + fb_parent["url"]] = (
            {"code": 200, "data": {"content": FB_REPLY_MD}},
            200,
        )
        client = _FakeJina(pages)
        posts = fetch_social_replies(client, ig_parents + [fb_parent], now, crawl={})
        ig_calls = [url for url in client.calls if "instagram.com" in url]
        fb_calls = [url for url in client.calls if "facebook.com" in url]
        self.assertEqual(len(ig_calls), 2)
        self.assertEqual(len(fb_calls), 1)
        self.assertEqual([item["source"] for item in posts], ["fb"])

    @patch("app.collect.time.sleep", lambda *_a, **_k: None)
    def test_social_replies_can_run_one_source_clock(self):
        now = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
        ig = {
            "source": "ig",
            "external_id": "DeMqPBnDz77",
            "title": "SBS Plus | #나는솔로 진지한 인터뷰",
            "url": "https://www.instagram.com/reel/DeMqPBnDz77/",
        }
        client = _FakeJina(
            {
                JINA_URL + self.parent["url"]: (
                    {"code": 200, "data": {"content": THREADS_REPLY_MD}},
                    200,
                ),
                JINA_URL + ig["url"]: (
                    {"code": 200, "data": {"content": IG_REPLY_MD}},
                    200,
                ),
            }
        )
        posts = fetch_social_replies(
            client,
            [self.parent, ig],
            now,
            crawl={},
            sources=("ig",),
        )
        self.assertEqual([item["source"] for item in posts], ["ig"])
        self.assertEqual(client.calls, [JINA_URL + ig["url"]])

    def test_merge_keeps_threads_reply_with_parent_excerpt(self):
        board = empty_board()
        item = sample("cmt-DeOpJlmEg-H", "기운이 밝아", "2026-10-08T18:30:00+09:00")
        item["source"] = "threads"
        item["kind"] = "reply"
        item["excerpt"] = "나는솔로 34기 다둥이 특집 현숙"
        item["url"] = "https://www.threads.com/@goat.8403753/post/DeO1xqvGfON"
        added = merge(board, {"threads": [item]})
        self.assertEqual(added, 1)
        self.assertEqual(board["posts"][0]["kind"], "reply")
        self.assertEqual(board["posts"][0]["excerpt"], "나는솔로 34기 다둥이 특집 현숙")


if __name__ == "__main__":
    unittest.main()
