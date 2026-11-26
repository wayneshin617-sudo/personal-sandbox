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
    youngsoo: { name: "영수", age: "30대 후반", kicker: "첫 번째 다둥이남", line: "나 선택을 못 받았어. 한 번도." },
    youngho: { name: "영호", age: "30대 중반", kicker: "두 번째 다둥이남", line: "순자와 현숙, 지금은 5대5." },
    youngsik: { name: "영식", age: "30대 후반", kicker: "세 번째 다둥이남", line: "올인하면 이 사람도 답변을 주는구나." },
    youngchul: { name: "영철", age: "30대 중반", kicker: "네 번째 다둥이남", line: "마음은 감사한데, 스파크는 아직." },
    gwangsoo: { name: "광수", age: "30대 중반", kicker: "다섯 번째 다둥이남", line: "정숙 님과 맞춰 가는 중입니다." },
    sangchul: { name: "상철", age: "30대 후반", kicker: "여섯 번째 다둥이남", line: "순자와 옥순, 아직 치열하게 고민 중." },
    youngsook: { name: "영숙", age: "30대 후반", kicker: "첫 번째 다둥이녀", line: "영식 님, 슈데권 저도 쓰겠다." },
    jeongsook: { name: "정숙", age: "30대 초반", kicker: "두 번째 다둥이녀", line: "광수 님이랑 잘 어울려." },
    soonja: { name: "순자", age: "30대 중반", kicker: "세 번째 다둥이녀", line: "이제 에너지가 제로." },
    youngja: { name: "영자", age: "30대 초반", kicker: "네 번째 다둥이녀", line: "밀당 하기 싫다. 영철 님으로 정했다." },
    oksoon: { name: "옥순", age: "30대 초반", kicker: "다섯 번째 다둥이녀", line: "저도 내일 말씀드리겠다." },
    hyunsook: { name: "현숙", age: "30대 중반", kicker: "여섯 번째 다둥이녀", line: "슈퍼데이트권, 영호 님에게 씁니다." },
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
