# 나는솔로 댓글 몰아보기

디시인사이드 [나는 솔로 갤러리](https://gall.dcinside.com/board/lists/?id=iamsolo)와 블라인드 [I'm솔로](https://www.teamblind.com/kr/topics/Im%EC%86%94%EB%A1%9C)에 올라오는 글 제목을 모아, 숲 방송 댓글처럼 보여주는 웹사이트입니다. 설치해서 실행하는 앱이 아닙니다. 주소만 열면 되고, 그 주소를 그대로 공유하면 다른 사람도 같은 목록을 봅니다.

글은 `docs/data/posts.json`에 쌓입니다. 화면은 그 파일을 2초마다 다시 읽습니다. 새 글을 더하는 일은 GitHub Actions가 약 5분마다 합니다. GitHub 웹사이트는 상시 서버를 띄울 수 없어서, 2초마다 게시판을 직접 긁는 구조는 쓰지 않습니다. 8000 포트도 쓰지 않습니다.

각 글 앞에는 디시·블라인드 로고가 채팅 프로필처럼 붙습니다. 아래 검색창의 키워드는 주소에 남아, 그 링크를 보내면 같은 검색 결과를 같이 볼 수 있습니다.

공개 주소는 저장소를 공개하고 GitHub Pages를 켠 뒤 생깁니다.

`https://wayneshin617-sudo.github.io/personal-sandbox/`

Settings → Pages → Build and deployment → Source를 **GitHub Actions**로 두면 위 주소로 열립니다. 저장소가 비공개이면 다른 사람은 이 주소를 열 수 없습니다.

## 테스트

```bash
python -m unittest tests.test_board
```
