import unittest

from datetime import datetime, timedelta, timezone

from app.collect import KST, _spread_targets, assign_blind_times, empty_board, merge, qoo_label_time
from app.parsers import (
    parse_blind,
    parse_blind_comments,
    parse_dc,
    parse_dc_comments,
    parse_theqoo,
    parse_theqoo_comments,
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
            {"url": "https://theqoo.net/iamsolo/4378274172", "external_id": "4378274172"},
        )
        self.assertEqual(len(qoo), 1)
        self.assertEqual(qoo[0]["source"], "qoo")
        self.assertEqual(qoo[0]["title"], "영철 옷 뭐야")
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
            {"url": "https://www.teamblind.com/kr/post/sample", "external_id": "/kr/post/sample"},
        )
        self.assertEqual(len(blind), 1)
        self.assertEqual(blind[0]["source"], "blind")
        self.assertEqual(blind[0]["title"], "영자 얘기가 구라라는 댓글")
        self.assertEqual(blind[0]["company"], "공무원")
        self.assertEqual(blind[0]["author"], "d******")
        self.assertEqual(blind[0]["posted_label"], "2시간")
        self.assertEqual(blind[0]["recommends"], 3)
        self.assertEqual(blind[0]["kind"], "reply")


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


if __name__ == "__main__":
    unittest.main()
