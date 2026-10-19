/* 34기 얼굴·소개는 여기만 고치면 로딩/1위 배경/프로필이 같이 바뀐다. */
(function (root) {
  const FACES = {
    youngsoo: "assets/cast/youngsoo.webp",
    youngho: "assets/cast/youngho.webp",
    youngsik: "assets/cast/youngsik.webp",
    youngchul: "assets/cast/youngchul.webp",
    gwangsoo: "assets/cast/gwangsoo.webp",
    sangchul: "assets/cast/sangchul.webp",
    youngsook: "assets/cast/youngsook.webp",
    jeongsook: "assets/cast/jeongsook.webp",
    soonja: "assets/cast/soonja.webp",
    youngja: "assets/cast/youngja.webp",
    oksoon: "assets/cast/oksoon.webp",
    hyunsook: "assets/cast/hyunsook.webp",
  };

  const PEOPLE = {
    youngsoo: { name: "영수", age: "30대 후반", line: "누나 일곱의 막내, 건축을 설계합니다." },
    youngho: { name: "영호", age: "30대 중반", line: "도쿄에서 증권 시스템을 만듭니다." },
    youngsik: { name: "영식", age: "30대 후반", line: "명상과 템플스테이를 좋아하는 외국계 SCM입니다." },
    youngchul: { name: "영철", age: "30대 중반", line: "책 읽는 논산 공무원입니다." },
    gwangsoo: { name: "광수", age: "30대 중반", line: "방송댄스가 취미인 막내예요." },
    sangchul: { name: "상철", age: "30대 후반", line: "반도체 HBM을 다루는 둘째예요." },
    youngsook: { name: "영숙", age: "", line: "여덟 자매의 막내로 첫 등장했습니다." },
    jeongsook: { name: "정숙", age: "", line: "숫자로 마음을 고르는 회계사예요." },
    soonja: { name: "순자", age: "", line: "네 남매 장녀로 등장했습니다." },
    youngja: { name: "영자", age: "", line: "남동생 둘을 둔 한의사예요." },
    oksoon: { name: "옥순", age: "", line: "세 남매 둘째로 첫 등장했습니다." },
    hyunsook: { name: "현숙", age: "", line: "세 남매 장녀로 등장했습니다." },
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
