import unittest

from app.filters import drop_reason, fold, is_sagye, normalize, should_keep, swear_reason


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


if __name__ == "__main__":
    unittest.main()
