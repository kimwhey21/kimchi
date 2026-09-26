"""네이버 주소표 만들기 (2026-09-26) — 종목 페이지가 한국어 글을 네이버 주소로 잇는 데 쓴다."""
import unittest

from scripts import naver_map_sync


class BuildTest(unittest.TestCase):
    def test_keeps_fermata_posts_and_drops_the_magazine(self) -> None:
        posted = {
            "/Users/mac/Downloads/market-brief/editorial/kr_2026-09-10.json": {"logNo": "224407511737"},
            "/Users/mac/Downloads/market-brief/editorial/guides/ko_x.json": {"logNo": "5", "blog": "fermata49"},
            "/Users/mac/Downloads/market-brief/editorial/magazine/2026-09-14_salt.json": {"logNo": "7", "blog": "puplesum_"},
            "/Users/mac/Downloads/market-brief/editorial/features/kr_y.json": {"title": "번호 없음"},
        }
        self.assertEqual(naver_map_sync.build(posted), {
            "editorial/guides/ko_x.json": "https://blog.naver.com/fermata49/5",
            "editorial/kr_2026-09-10.json": "https://blog.naver.com/fermata49/224407511737",
        })


if __name__ == "__main__":
    unittest.main()
