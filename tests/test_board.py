import unittest

from datetime import datetime, timedelta, timezone

from app.collect import assign_blind_times, empty_board, merge
from app.parsers import parse_blind, parse_dc

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


def sample(external_id, title, posted_at="2026-10-13T12:00:00+09:00"):
    return {
        "source": "dc",
        "external_id": external_id,
        "title": title,
        "excerpt": "",
        "author": "나갤러",
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


if __name__ == "__main__":
    unittest.main()
