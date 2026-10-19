/* 34기 얼굴·소개는 여기만 고치면 로딩/1위 배경/프로필이 같이 바뀐다. */
(function (root) {
  const FACES = {
    youngsoo: "assets/cast/youngsoo.webp?v=2",
    youngho: "assets/cast/youngho.webp?v=2",
    youngsik: "assets/cast/youngsik.webp",
    youngchul: "assets/cast/youngchul.webp",
    gwangsoo: "assets/cast/gwangsoo.webp",
    sangchul: "assets/cast/sangchul.webp",
    youngsook: "assets/cast/youngsook.webp?v=2",
    jeongsook: "assets/cast/jeongsook.webp",
    soonja: "assets/cast/soonja.webp",
    youngja: "assets/cast/youngja.webp",
    oksoon: "assets/cast/oksoon.webp?v=2",
    hyunsook: "assets/cast/hyunsook.webp",
  };

  const PEOPLE = {
    youngsoo: { name: "영수", age: "30대 후반", kicker: "첫 번째 다둥이남", line: "막내라 주방 얼씬도 안할줄 알앗지?" },
    youngho: { name: "영호", age: "30대 중반", kicker: "두 번째 다둥이남", line: "도쿄에서 상한가, 여심도 상한가!" },
    youngsik: { name: "영식", age: "30대 후반", kicker: "세 번째 다둥이남", line: "불심으로 여심을 잡겠다!" },
    youngchul: { name: "영철", age: "30대 중반", kicker: "네 번째 다둥이남", line: "세파에 물들지 않은 남자." },
    gwangsoo: { name: "광수", age: "30대 중반", kicker: "다섯 번째 다둥이남", line: "춤은 방송급, 사랑은 지금부터!" },
    sangchul: { name: "상철", age: "30대 후반", kicker: "여섯 번째 다둥이남", line: "반도체보다 뜨거운 한 방을 들고 왔습니다." },
    youngsook: { name: "영숙", age: "", kicker: "첫 번째 다둥이녀", line: "여덟 자매 막내, 이번엔 내가 주인공이다!" },
    jeongsook: { name: "정숙", age: "", kicker: "두 번째 다둥이녀", line: "숫자는 내가 센다. 마음은 네가 골라!" },
    soonja: { name: "순자", age: "", kicker: "세 번째 다둥이녀", line: "맏이라 참았지, 사랑은 안 참는다!" },
    youngja: { name: "영자", age: "", kicker: "네 번째 다둥이녀", line: "한 방에 처방합니다. 심장부터요." },
    oksoon: { name: "옥순", age: "", kicker: "다섯 번째 다둥이녀", line: "둘째라 주방만 지킬 줄 알았지?" },
    hyunsook: { name: "현숙", age: "", kicker: "여섯 번째 다둥이녀", line: "장녀의 사랑, 이번엔 내가 먼저 간다!" },
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

  root.BoardCast = { FACES, PEOPLE, ORDER, face, person, matchWord, fromRanks };
})(window);
