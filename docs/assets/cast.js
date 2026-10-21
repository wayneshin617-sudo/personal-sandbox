/* 34기 얼굴·소개는 여기만 고치면 로딩/1위 배경/프로필이 같이 바뀐다. */
(function (root) {
  const FACES = {
    youngsoo: "assets/cast/youngsoo.webp?v=4",
    youngho: "assets/cast/youngho.webp?v=4",
    youngsik: "assets/cast/youngsik.webp?v=4",
    youngchul: "assets/cast/youngchul.webp?v=7",
    gwangsoo: "assets/cast/gwangsoo.webp?v=6",
    sangchul: "assets/cast/sangchul.webp?v=4",
    youngsook: "assets/cast/youngsook.webp?v=4",
    jeongsook: "assets/cast/jeongsook.webp?v=4",
    soonja: "assets/cast/soonja.webp?v=4",
    youngja: "assets/cast/youngja.webp?v=4",
    oksoon: "assets/cast/oksoon.webp?v=4",
    hyunsook: "assets/cast/hyunsook.webp?v=4",
  };

  const PEOPLE = {
    youngsoo: { name: "영수", age: "30대 후반", kicker: "첫 번째 다둥이남", line: "막내라 주방 얼씬도 안할줄 알앗지?" },
    youngho: { name: "영호", age: "30대 중반", kicker: "두 번째 다둥이남", line: "도쿄에서 상한가, 여심도 상한가!" },
    youngsik: { name: "영식", age: "30대 후반", kicker: "세 번째 다둥이남", line: "불심으로 여심을 잡겠다!" },
    youngchul: { name: "영철", age: "30대 중반", kicker: "네 번째 다둥이남", line: "육아는 제가 보겠습니다." },
    gwangsoo: { name: "광수", age: "30대 중반", kicker: "다섯 번째 다둥이남", line: "춤은 방송급, 사랑은 지금부터!" },
    sangchul: { name: "상철", age: "30대 후반", kicker: "여섯 번째 다둥이남", line: "반도체보다 뜨거운 한 방을 들고 왔습니다." },
    youngsook: { name: "영숙", age: "30대 후반", kicker: "첫 번째 다둥이녀", line: "언니 일곱에 조카 열여섯, 이번엔 내가 주인공이다!" },
    jeongsook: { name: "정숙", age: "", kicker: "두 번째 다둥이녀", line: "스무 살부터 왁킹. 숫자는 내가 센다!" },
    soonja: { name: "순자", age: "30대 중반", kicker: "세 번째 다둥이녀", line: "남사친은 0명. 회사 아니면 집이다!" },
    youngja: { name: "영자", age: "", kicker: "네 번째 다둥이녀", line: "꼬시는 건 내가 먼저!" },
    oksoon: { name: "옥순", age: "", kicker: "다섯 번째 다둥이녀", line: "10년차 성실파. 외동은 패스!" },
    hyunsook: { name: "현숙", age: "30대 중반", kicker: "여섯 번째 다둥이녀", line: "자기개발 자기계발, 갓생 끝판왕." },
  };

  const ORDER = Object.keys(PEOPLE);

  function face(id) {
    return FACES[id] || FACES.soonja;
  }

  function person(id) {
    const info = PEOPLE[id];
    if (!info) return null;
    return { id, photo: face(id), ...info };
  }

  function matchWord(word) {
    const text = String(word || "").replace(/\s+/g, "");
    if (!text) return null;
    let found = null;
    for (const id of ORDER) {
      const name = PEOPLE[id].name;
      if (text.includes(name) && (!found || name.length > PEOPLE[found].name.length)) found = id;
    }
    return found ? person(found) : null;
  }

  function fromRanks(ranks) {
    for (const item of ranks || []) {
      const hit = matchWord(item.word || item);
      if (hit) return hit;
    }
    return person("soonja");
  }

  /* 로딩 화면 주인공. 정각마다 한 명씩 넘어가고, 12시간이면 34기를 한 바퀴 돈다. */
  function hourly(now = Date.now()) {
    const hour = Math.floor(Number(now) / 3600000);
    const index = ((hour % ORDER.length) + ORDER.length) % ORDER.length;
    return person(ORDER[index]);
  }

  root.BoardCast = { FACES, PEOPLE, ORDER, face, person, matchWord, fromRanks, hourly };
})(window);
