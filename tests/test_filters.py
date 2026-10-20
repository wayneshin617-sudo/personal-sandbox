import unittest

from app.filters import (
    drop_reason,
    fold,
    is_sagye,
    normalize,
    should_keep,
    skip_youtube_video,
    swear_reason,
)


class NormalizeTest(unittest.TestCase):
    def test_strips_spaces_and_digits_for_mister(self):
        self.assertEqual(normalize("미 스 터 서"), "미스터서")
        self.assertEqual(fold("미1스터조"), "미스터조")
        self.assertEqual(normalize("7 옥"), "7옥")

    def test_swear_obfuscation(self):
        self.assertEqual(swear_reason("시1발"), "시발")
        self.assertEqual(swear_reason("씨 1 발"), "씨발")
        self.assertEqual(swear_reason("ㅅ1ㅂ"), "ㅅㅂ")
        self.assertEqual(swear_reason("시 ㅂ 발"), "시발")


class SagyeTest(unittest.TestCase):
    def test_mister_variants(self):
        for title in ("미스터서 왜 저래", "미스터 조 인기", "미서 오늘", "미조햄", "미1스터최"):
            self.assertTrue(is_sagye(title), title)
            self.assertFalse(should_keep({"title": title, "excerpt": ""}), title)

    def test_oksoon_shortcuts(self):
        for title in ("7옥 미스터서 선택해라", "14옥순 아님?", "23기옥순", "7 옥", "24순자"):
            self.assertTrue(is_sagye(title), title)

    def test_show_keywords(self):
        for title in ("나솔사계 최종커플", "솔로민박 예고", "그 후, 사랑은 계속된다 186화", "사계 오늘은 미서"):
            self.assertTrue(is_sagye(title), title)

    def test_current_season_keeps_main_show(self):
        for title in (
            "34기 영철 자신감",
            "34옥순 몰표각이다",
            "이번 기수 순자 어때",
            "현 기수 영호 1순위",
            "34기 여출 보니 7옥순이 대단",
        ):
            self.assertTrue(should_keep({"title": title, "excerpt": ""}), title)

    def test_sagye_show_drops_even_with_current_marker(self):
        self.assertFalse(should_keep({"title": "나솔사계 이번 기수 대천", "excerpt": ""}))

    def test_image_is_not_mister_ji(self):
        self.assertTrue(should_keep({"title": "영철은 나솔 보고 이미지메이킹", "excerpt": ""}))
        self.assertTrue(should_keep({"title": "반장은 폐미지", "excerpt": ""}))

    def test_rose_bgm_is_kept(self):
        self.assertTrue(should_keep({"title": "엔딩 배반의 장미 뭐냐", "excerpt": ""}))

    def test_gukhwa_is_sagye(self):
        self.assertFalse(should_keep({"title": "국화 갈수록 인물이 무너진다", "excerpt": ""}))

    def test_old_season_cast(self):
        self.assertFalse(should_keep({"title": "14영자 알아봐라", "excerpt": ""}))
        self.assertFalse(should_keep({"title": "32영수랑 잘될리가", "excerpt": ""}))

    def test_ranking_is_not_oksoon(self):
        self.assertTrue(should_keep({"title": "영자 짜장 1순위 유력", "excerpt": ""}))
        self.assertTrue(should_keep({"title": "현숙 4 영숙 1 옥순 1 예상", "excerpt": ""}))

    def test_political_and_sexual(self):
        self.assertTrue(drop_reason({"title": "이재명 얘기 그만", "excerpt": ""}).startswith("정치"))
        self.assertTrue(drop_reason({"title": "몰카 의심", "excerpt": ""}).startswith("성적"))

    def test_swears_optional_for_feed(self):
        post = {"title": "씨발 영철 뭐함", "excerpt": ""}
        self.assertTrue(should_keep(post))
        self.assertFalse(should_keep(post, swears=True))

    def test_youtube_comment_drops_when_video_title_is_sagye(self):
        post = {
            "source": "yt",
            "title": "영숙 선택 잘했다",
            "excerpt": "나솔사계 미스터서 하이라이트 #나는솔로",
            "url": "https://www.youtube.com/watch?v=abc123&lc=cid1",
        }
        self.assertFalse(should_keep(post))
        self.assertTrue(drop_reason(post).startswith("유튜브"))

    def test_youtube_skips_sagye_and_old_season_titles(self):
        self.assertTrue(
            skip_youtube_video({"video_id": "sagye", "title": "[나솔사계 LIVE] 현커는 과연 몇 커플?"})
        )
        self.assertTrue(skip_youtube_video({"video_id": "old", "title": "나는솔로 31기 하이라이트"}))
        self.assertTrue(
            skip_youtube_video(
                {
                    "video_id": "desc",
                    "title": "나는솔로 34기 다시보기",
                    "description": "사계 민박에서 찍은 후기",
                }
            )
        )
        self.assertTrue(skip_youtube_video({"video_id": "other", "title": "다른기수랑 비교하는 34기"}))
        self.assertFalse(skip_youtube_video({"video_id": "okvid", "title": "나는솔로 34기 9회"}))

    def test_old_season_token_without_cast_name(self):
        self.assertTrue(is_sagye("31기 하이라이트"))
        self.assertFalse(should_keep({"title": "31기 하이라이트", "excerpt": ""}))
        self.assertTrue(should_keep({"title": "34기 보니까 31기보다 낫다", "excerpt": ""}))

    def test_blocked_clickbait_youtube(self):
        post = {
            "source": "yt",
            "title": "HBM=High Bandwidth Memory",
            "excerpt": "[나는솔로] 34기 상철 광수 영식 직장동료 지인 등판 충격 폭로! 술 제어 사내 빌런 폭로! #나는솔로#나는솔로#나는솔로#나는솔로",
            "url": "https://www.youtube.com/watch?v=qpUKcCsjHSI&lc=UgwBL7vT4g47ku3ZHWB4AaABAg",
        }
        self.assertFalse(should_keep(post))
        self.assertTrue(drop_reason(post).startswith("유튜브"))

    def test_hashtag_spam_video_is_skipped(self):
        self.assertTrue(
            skip_youtube_video(
                {
                    "video_id": "newspam",
                    "title": "34기 스포 #나는솔로#나는솔로#나는솔로#나는솔로",
                }
            )
        )
        self.assertFalse(skip_youtube_video({"video_id": "okvid", "title": "나는솔로 34기 9회"}))


if __name__ == "__main__":
    unittest.main()
