const CASE = {
  names: {
    narrator: "",
    inner: "고난의 속마음",
    gonan: "고난",
    muhyeong: "무명한",
    baksa: "박사",
    miryeon: "미련",
    judge: "재판장",
    yujoe: "검사 유죄만",
    jeong: "경비 정문수",
    meseu: "감식 메스를",
    jeondoman: "전도만",
    victim: "고인물",
  },
  evidence: {
    badge: {
      name: "어린이 변호인 뱃지",
      desc: "무명한 호주머니에서 ‘빌린’ 뱃지. 고난 가슴에 달면 뱃지가 더 크다.",
    },
    overview: {
      name: "사건 개요",
      desc: "9월 13일 21시 이후, 시립박물관 전시실. 피해자 고인물 관장. 용의자 무명한. 사인은 검찰 주장 ‘둔기 타살’.",
    },
    autopsy: {
      name: "부검 결과",
      desc: "외상 없음. 급성 심장사. 얼굴 근육은 극도의 공포로 경직. 둔기 흔적은 시체에 없다.",
    },
    prints: {
      name: "거꾸로 된 발자국",
      desc: "전시실 먼지 위 운동화 자국. 앞코가 출구가 아니라 천장 쪽을 향한다. 보폭이 손바닥 폭이다.",
    },
    skylight: {
      name: "천장 창틀 흠집",
      desc: "밖에서 안으로 긁힌 자국. 잠금장치는 안에서 열린 게 아니라 손바닥 기름으로 밀려 있다.",
    },
    harness: {
      name: "하네스 버클 조각",
      desc: "화분 흙에서 나온 금속 버클. 행글라이더 하네스 규격. 아직 따뜻할 정도로 마찰열이 남아 있었다… 고난 말로는.",
    },
    camera: {
      name: "CCTV 캡처",
      desc: "정문 카메라는 로비 천장도 살짝 담는다. 21:06, 노란 운동화가 화면 위를 ‘지나갔다’.",
    },
    tranq: {
      name: "강화 마취총",
      desc: "박사의 신형. 무명한 내성 대비 3배. 발사 시각 기록 20:41. 범행 추정 시각보다 빠르다.",
    },
    bump: {
      name: "무명한의 혹",
      desc: "이마 정중앙 혹. 몽둥이 혈흔과 혈액형 일치. 피해자 피가 아니다.",
    },
    club: {
      name: "혈흔 몽둥이",
      desc: "검찰 증거. 무명한 사무소에서 발견. 혈흔은 무명한의 것.",
    },
    invoice: {
      name: "박사의 청구서",
      desc: "마취총 렌탈 88만 원, 연체 이자 포함. 고난의 이름이 채무자에 크게 적혀 있다.",
    },
    visitor: {
      name: "관람객 명단",
      desc: "낮 손님 전도만. 취미란: 물구나무, 행글라이더. 특이사항: ‘천장 창 사진 찍어도 되냐’고 세 번 물음.",
    },
    shoes: {
      name: "초강력 킥운동화",
      desc: "720도 턴 킥용. 이 사건과는 무관하다. 고난은 이거로 다 해결된다고 믿는다.",
    },
    ledger: {
      name: "판매 장부",
      desc: "박사가 전도만에게 중고 행글라이더 키트를 판 기록. 구매일 사건 이틀 전.",
    },
  },
  profiles: {
    gonan: { name: "고난", desc: "명탐정… 자칭. 키가 뱃지보다 조금 크다. 의뢰비, 장비값, 목숨 순으로 소중히 한다." },
    muhyeong: { name: "무명한", desc: "탐정. 추리력은 고난의 열 배. 추리를 시작하는 순간 마취당한다. 이번 피고인." },
    yujoe: { name: "검사 유죄만", desc: "유죄 외에 관심 없는 검사. 고난을 ‘어린이 변론 체험 학습’으로 본다." },
    judge: { name: "재판장", desc: "설명을 두 번은 들어야 한다. 세 번째엔 그냥 넘어간다." },
    jeondoman: { name: "전도만", desc: "낮 관람객. 항상 세상과 각도가 다른 남자." },
    baksa: { name: "박사", desc: "발명가. 장비는 잘 만들어 주고, 돈은 더 잘 받는다." },
    miryeon: { name: "미련", desc: "무명한의 지인. 고난 머리를 때리면 세상이 잠깐 평화로워진다." },
  },
  profileOrder: ["gonan", "muhyeong", "yujoe", "judge", "jeondoman", "baksa", "miryeon"],
  trialReady(state) {
    const need = ["autopsy", "prints", "tranq", "bump"];
    const killer = ["camera", "harness", "ledger"].some((id) => state.evidence.includes(id));
    return need.every((id) => state.evidence.includes(id)) && state.flags.talked_muhyeong && killer;
  },
  locations: {
    office: {
      name: "고난 탐정사무소",
      bg: "office",
      actor: "gonan",
      mood: "smirk",
      hotspots: [
        {
          id: "sofa",
          label: "소파",
          x: 12,
          y: 58,
          w: 22,
          h: 18,
          lines: [
            { who: "gonan", mood: "normal", text: "침 자국이 사람 한 명 분이다. 무명한 거. 마취 잘 들었다는 증거지." },
            { who: "inner", text: "여기서 기절시킨 다음 박물관까지 끌고 갔다. …기록엔 안 적는다." },
          ],
        },
        {
          id: "desk",
          label: "책상",
          x: 42,
          y: 48,
          w: 18,
          h: 16,
          give: "invoice",
          lines: [
            { who: "gonan", mood: "shock", text: "청구서다. 88만 원. 박사 이 새끼, 소수점 위치 잘못 쓴 거 아니야?" },
            { who: "inner", text: "법정에서 이것 좀 보여주면 동정표라도 얻나. 아니 판사는 동정 안 줘." },
          ],
        },
        {
          id: "tranqbox",
          label: "서랍",
          x: 62,
          y: 60,
          w: 14,
          h: 14,
          give: "tranq",
          flag: "got_tranq",
          lines: [
            { who: "gonan", mood: "smirk", text: "강화 마취총. 발사 로그 20:41. 범행 전에 이미 무명한은 잠들어 있었지." },
            { who: "inner", text: "내가 쏜 거지만, 알리바이로는 최고다. 양심은 청구서 다음에 생각하자." },
          ],
        },
        {
          id: "baksa",
          label: "박사",
          x: 76,
          y: 36,
          w: 16,
          h: 40,
          flag: "talked_baksa",
          lines: [
            { who: "baksa", mood: "angry", text: "고난 군! 장비값! 지금! 안 내면 킥운동화 회수다!" },
            { who: "gonan", mood: "sweat", text: "그거 없으면 슬라이딩이 안 되는데. 외상. 법정에서 이기고 줄게." },
            { who: "baksa", text: "너는 맨날 이기고 나서 도망가더라. 참고로 전도만이라는 사람이 행글라이더 사 갔어. 이틀 전." },
            { who: "gonan", mood: "think", text: "전도만… 이름은 이미 거꾸로 시작하네." },
          ],
        },
        {
          id: "miryeon",
          label: "미련",
          x: 28,
          y: 36,
          w: 14,
          h: 36,
          require: ["talked_baksa"],
          lines: [
            { who: "miryeon", mood: "angry", text: "무명한 삼촌 기소된 거 너 때문이잖아. 넌 또 뭐야?" },
            { who: "gonan", mood: "shock", text: "변호인이야. 때리면 무죄가 유죄가 된다고. 손 내려." },
            { who: "miryeon", text: "머리 한 대만." },
            { who: "gonan", mood: "sweat", shake: true, text: "아! 잠깐 천재가 된 것 같— 아니다 그냥 아프다." },
          ],
        },
      ],
      moves: [
        { to: "invest:museum", label: "시립박물관" },
        { to: "invest:cell", label: "구치소" },
        { to: "invest:lab", label: "박사 연구소" },
        { to: "trial_intro", label: "재판정으로", requireTrial: true },
      ],
    },
    museum: {
      name: "시립박물관 전시실",
      bg: "museum",
      actor: "gonan",
      mood: "normal",
      hotspots: [
        {
          id: "body",
          label: "시체 위치",
          x: 44,
          y: 62,
          w: 18,
          h: 14,
          give: "autopsy",
          flag: "examined_body",
          lines: [
            { who: "gonan", mood: "normal", text: "고인물 관장. 이름부터 이미 고인인데 진짜로 고인이 됐네." },
            { who: "gonan", text: "타박상이 없다. 검찰은 둔기라며. 이 얼굴은… 누가 갑자기 거꾸로 나타난 표정이야." },
            { who: "inner", text: "부검 결과 메모가 바닥에 떨어져 있다. 메스를가 놓고 간 듯." },
          ],
        },
        {
          id: "prints",
          label: "이상한 자국",
          x: 22,
          y: 70,
          w: 20,
          h: 12,
          give: "prints",
          flag: "examined_prints",
          lines: [
            { who: "gonan", mood: "shock", text: "발자국이 거꾸로다. 앞코가 천장을 봐. 물구나무로 들어왔다고?" },
            { who: "inner", text: "36화급 개소리인데, 개소리가 맞을 때가 우리 세계관이다." },
          ],
        },
        {
          id: "sky",
          label: "천장 창",
          x: 42,
          y: 8,
          w: 16,
          h: 16,
          give: "skylight",
          lines: [
            { who: "gonan", mood: "think", text: "창틀이 밖에서 긁혔어. 정문이 아니라도 사람은 들어온다. 물구나무면 더 잘 들어오고." },
          ],
        },
        {
          id: "cam",
          label: "카메라",
          x: 78,
          y: 18,
          w: 12,
          h: 14,
          give: "camera",
          lines: [
            { who: "gonan", text: "정문 CCTV. 21:06에 노란 신발이 화면 위로 지나간다. 사람이 천장에 붙었거나, 각도가 미쳤거나." },
          ],
        },
        {
          id: "plant",
          label: "화분",
          x: 8,
          y: 52,
          w: 12,
          h: 18,
          give: "harness",
          lines: [
            { who: "gonan", mood: "smirk", text: "화분에 금속. 하네스 버클이네. 누가 여기서 날아갔다." },
            { who: "inner", text: "내가 슬라이딩하다 박은 자국이랑은 다르다. 내 자국은 저기 콘센트." },
          ],
        },
        {
          id: "desk2",
          label: "안내 데스크",
          x: 60,
          y: 44,
          w: 16,
          h: 14,
          give: "visitor",
          lines: [
            { who: "gonan", text: "관람객 명단. 전도만. 취미: 물구나무, 행글라이더. 천장 창 사진 찍어도 되냐고 세 번이나 물었대." },
            { who: "gonan", mood: "smirk", text: "세 번이면 범인이지. 한 번은 관광, 두 번은 수상, 세 번은 기소." },
          ],
        },
      ],
      moves: [
        { to: "invest:office", label: "탐정사무소" },
        { to: "invest:cell", label: "구치소" },
        { to: "invest:lab", label: "박사 연구소" },
        { to: "trial_intro", label: "재판정으로", requireTrial: true },
      ],
    },
    cell: {
      name: "구치소 접견실",
      bg: "cell",
      actor: "muhyeong",
      mood: "angry",
      extra: "",
      hotspots: [
        {
          id: "mu",
          label: "무명한",
          x: 40,
          y: 30,
          w: 22,
          h: 48,
          flag: "talked_muhyeong",
          give: "bump",
          lines: [
            { who: "muhyeong", mood: "angry", text: "고난. 마취총. 너지." },
            { who: "gonan", mood: "sweat", text: "증거인멸이 아니라 증거보전이야. 네가 추리하면 사건이 해결되잖아. 그러면 내가 할 일이 없어." },
            { who: "muhyeong", text: "제 생각에 범인은… 바로!" },
            { who: "gonan", mood: "smirk", shake: true, text: "쿨럭. 마취. 잘 자. 혹 예쁘다. 몽둥이 혈흔이랑 딱이네." },
            { who: "muhyeong", extra: "sleep", mood: "sleep", text: "큭… 징역 15년은… 이번엔 너다…" },
            { who: "inner", text: "혹을 사진 찍었다. 피해자 피가 아니라는 걸 법정에서 보여 주자." },
          ],
        },
        {
          id: "bars",
          label: "창살",
          x: 70,
          y: 20,
          w: 18,
          h: 50,
          lines: [
            { who: "gonan", text: "창살 간격이 내 머리만 하다. 내가 수감되면 여길 통과해. 그래서 피고는 무명한으로 유지해야 해." },
          ],
        },
      ],
      moves: [
        { to: "invest:office", label: "탐정사무소" },
        { to: "invest:museum", label: "시립박물관" },
        { to: "invest:lab", label: "박사 연구소" },
        { to: "trial_intro", label: "재판정으로", requireTrial: true },
      ],
    },
    lab: {
      name: "박사 연구소",
      bg: "lab",
      actor: "baksa",
      hotspots: [
        {
          id: "shoes",
          label: "킥운동화",
          x: 18,
          y: 58,
          w: 16,
          h: 16,
          give: "shoes",
          lines: [
            { who: "baksa", text: "만지지 마. 회수 예정이니까." },
            { who: "gonan", mood: "smirk", text: "증거로 쓸게. 720도 킥은 법정에서도 통하거든." },
            { who: "inner", text: "통하지 않는다. 그래도 가져간다." },
          ],
        },
        {
          id: "book",
          label: "판매 장부",
          x: 58,
          y: 42,
          w: 18,
          h: 16,
          give: "ledger",
          lines: [
            { who: "baksa", text: "전도만. 중고 행글라이더 키트. 현금. 영수증 거부. 수상한데 돈은 진짜였다." },
            { who: "gonan", mood: "think", text: "범인이 장비값을 내는 사람은 처음 본다. 나랑 반대야." },
          ],
        },
      ],
      moves: [
        { to: "invest:office", label: "탐정사무소" },
        { to: "invest:museum", label: "시립박물관" },
        { to: "invest:cell", label: "구치소" },
        { to: "trial_intro", label: "재판정으로", requireTrial: true },
      ],
    },
  },
  scenes: {
    prologue: {
      type: "talk",
      bg: "night",
      lines: [
        { who: "narrator", text: "2026년 9월 13일. 시립박물관." },
        { who: "narrator", text: "관장 고인물이 전시실에서 숨진 채 발견되었다." },
        { who: "narrator", text: "용의자는 현장의 잠든 탐정, 무명한." },
        { who: "yujoe", mood: "smirk", bg: "court", text: "명백하다. 둔기, 혈흔, 피고. 오늘은 일찍 끝나겠군." },
        { who: "judge", text: "변호인은… 그 어린이는 무엇이오?" },
        { who: "gonan", mood: "smirk", extra: "", text: "명탐정 고난. 오늘은 변호인. 착수금은 무명한이 나중에 냄." },
        { who: "inner", text: "이 새끼 누명은 내가 만든 거에 가깝다. 그래도 진범이 따로 있어. 진범이 없으면 내가 88만 원을 못 벌어." },
        { who: "narrator", text: "재판 전, 현장이 아직 열려 있다. 단서를 모아라. 안 모으면 진짜로 유죄다." },
      ],
      next: "invest:office",
    },
    trial_intro: {
      type: "talk",
      bg: "court",
      lines: [
        { who: "judge", text: "이제 심리를 시작하겠소. 검사, 논고하시오." },
        { who: "yujoe", mood: "smirk", text: "피고 무명한은 폐관 후 박물관에 침입, 고인물 관장을 몽둥이로 살해했다." },
        { who: "yujoe", give: "club", text: "혈흔 몽둥이. 피고 사무소에서 나왔다. 질문은 없다." },
        { who: "gonan", mood: "angry", text: "질문은 있지. 그 몽둥이로 기절한 사람이 어떻게 사람을 쳐." },
        { who: "judge", text: "어린이 변호인, 증인 심문은 가능하오. 단, 장난이면 유죄요." },
        { who: "inner", text: "증언을 하나씩 추궁해. 허점이 보이면 증거를 들이밀어. 틀리면 내가 아니라 무명한이 죽어." },
      ],
      next: "cx1",
    },
    cx1: {
      type: "cross",
      bg: "court",
      witness: "jeong",
      intro: [
        { who: "judge", text: "증인, 경비 정문수. 그날 밤을 증언하시오." },
        { who: "jeong", text: "네. 저는 정직합니다. 이름부터." },
      ],
      statements: [
        {
          text: "폐관은 밤 9시 정각이었습니다. 자물쇠는 제가 잠갔습니다.",
          press: {
            lines: [
              { who: "gonan", mood: "smirk", text: "9시 정각? 시계는 맞냐. 네 시계 배터리 없어 보인다." },
              { who: "jeong", text: "휴대폰 시간입니다. 9시 00분 02초요." },
              { who: "inner", text: "폐관 자체는 맞는 것 같다. 여긴 허점이 약해." },
            ],
          },
        },
        {
          text: "그 이후 정문으로 들어온 사람은 무명한 탐정뿐입니다.",
          press: {
            lines: [
              { who: "gonan", text: "정문만 봤지. 네가 화장실 간 1분은?" },
              { who: "jeong", text: "참았습니다. 프로 경비니까요." },
              { who: "yujoe", mood: "smirk", text: "증인의 방광까지 심문할 셈인가." },
            ],
          },
        },
        {
          text: "카메라는 정문만 찍습니다. 다른 출입구는 존재하지 않습니다.",
          press: {
            lines: [
              { who: "gonan", mood: "angry", text: "천장 창은 장식이야? 하늘에서 유물이 떨어지라고 달아놨어?" },
              { who: "jeong", mood: "sweat", text: "아… 천장 창은 있습니다. 하지만 사람이 들어올 수는 없습니다. 3층 높이니까요." },
            ],
            add: {
              text: "천장 창은 있으나, 사람이 들어올 수는 없습니다. 3층 높이입니다.",
              mood: "sweat",
              present: { skylight: "cx1_break", camera: "cx1_break" },
              press: {
                lines: [
                  { who: "gonan", text: "3층이면 날면 되지. 또는 거꾸로 기어오르거나." },
                  { who: "jeong", text: "그건 영화고요." },
                  { who: "inner", text: "우리 영화는 원래 그 영화다." },
                ],
              },
            },
          },
        },
        {
          text: "전시실 바닥에는 다른 발자국이 전혀 없었습니다. 무명한의 구두 자국뿐입니다.",
          present: { prints: "cx1_break" },
          press: {
            lines: [
              { who: "gonan", mood: "think", text: "전혀? 먼지 위에 이상한 거 못 봤어? 앞코가 하늘 보는 거." },
              { who: "jeong", text: "청소 상태였습니다. 저는 위를 안 봐요. 바닥만 봐요. 경비니까요." },
              { who: "inner", text: "발자국 증거를 들이밀 타이밍이다." },
            ],
          },
        },
      ],
    },
    cx1_break: {
      type: "talk",
      bg: "court",
      lines: [
        { who: "gonan", mood: "angry", text: "발자국은 ‘전혀’가 아니야. 거꾸로 된 운동화 자국이 천장 창 아래까지 이어져." },
        { who: "jeong", mood: "shock", text: "그, 그건 장난 같았어서…" },
        { who: "yujoe", mood: "angry", text: "물구나무 침입자? 유치한 판타지군. 피고가 잠긴 문 안에 있던 사실은 안 바뀐다." },
        { who: "gonan", mood: "smirk", text: "문은 잠겼지. 범인은 문이 필요 없었을 뿐이야." },
        { who: "judge", text: "일단… 출입 경로는 의문이 생겼소. 다음 증인." },
      ],
      next: "cx2",
    },
    cx2: {
      type: "cross",
      bg: "court",
      witness: "meseu",
      intro: [
        { who: "meseu", text: "감식과장 메스를입니다. 사인은 과학이고, 과학은 둔기입니다." },
        { who: "gonan", mood: "normal", text: "과학이 한 단어로 끝나면 박사 청구서가 안 나와." },
      ],
      statements: [
        {
          text: "사인은 둔기에 의한 타살입니다. 그 외의 가능성은 없습니다.",
          present: { autopsy: "cx2_break" },
          press: {
            lines: [
              { who: "gonan", text: "외상 없는 타살? 신종 둔기냐, 투명 방망이냐." },
              { who: "meseu", text: "내상입니다. 심장이 맞았습니다… 감정적으로." },
              { who: "inner", text: "부검 결과랑 정면 충돌이다. 들이밀어." },
            ],
          },
        },
        {
          text: "몽둥이의 혈흔은 범행의 결정적 증거입니다.",
          present: { bump: "cx2_break", tranq: "cx2_break" },
          press: {
            lines: [
              { who: "gonan", text: "누구 피인지 말 안 하네. 과학이 부끄러운가 봐." },
              { who: "meseu", mood: "sweat", text: "혈액형은 일치합니다. 누구와 일치하는지는… 피고와." },
              { who: "gonan", mood: "smirk", text: "피고 피면 자살 미수냐. 이마 혹 보이냐 무명한." },
            ],
          },
        },
        {
          text: "타격 각도로 보아 범인은 키 180센티 전후의 성인 남성입니다.",
          press: {
            lines: [
              { who: "gonan", text: "나라면 각도 안 나와. 내 키로는 무릎을 때리지." },
              { who: "meseu", text: "그래서 변호인은 제외했습니다." },
              { who: "yujoe", mood: "smirk", text: "유일하게 동의하는 부분이다." },
            ],
          },
        },
        {
          text: "피해자는 정면에서 가격당해, 쓰러졌습니다.",
          present: { autopsy: "cx2_break" },
          press: {
            lines: [
              { who: "gonan", mood: "think", text: "정면? 아니면 위에서 아래로, 물구나무 얼굴이 정면으로 들어온 거고." },
              { who: "meseu", text: "그건 보고서 양식에 없는 항목입니다." },
            ],
          },
        },
      ],
    },
    cx2_break: {
      type: "talk",
      bg: "court",
      lines: [
        { who: "gonan", mood: "angry", text: "사인은 둔기가 아니야! 외상 없는 급성 심장사. 몽둥이 피는 무명한 이마에서 나온 거고." },
        { who: "meseu", mood: "shock", text: "부검 메모를… 현장에 두고 왔군요. 과학의 패배입니다." },
        { who: "yujoe", mood: "angry", text: "심장사여도 범인은 있다. 누군가는 관장을 놀라 죽게 만들었다는 뜻이다." },
        { who: "judge", text: "그렇다면 그날 천장 창에 관심이 많던 인물을 부르겠소. 증인, 전도만." },
        { who: "jeondoman", mood: "smirk", text: "저요? 전 그냥 건전한 취미 생활자인데요." },
      ],
      next: "cx3",
    },
    cx3: {
      type: "cross",
      bg: "court",
      witness: "jeondoman",
      intro: [
        { who: "judge", text: "증인, 알리바이를 말하시오." },
        { who: "jeondoman", text: "물론이죠. 전 그날 밤 집에 있었습니다. 세상과 바른 각도로요." },
        { who: "inner", text: "이 새끼 말이 벌써 기울었다. 추궁해서 행글라이더를 꺼내." },
      ],
      statements: [
        {
          text: "저는 그날 밤 집에 있었습니다. 박물관에는 그림자도 안 남겼어요.",
          present: { camera: "cx3_break" },
          press: {
            lines: [
              { who: "gonan", text: "그림자를 천장에 남기면 바닥에 안 남지." },
              { who: "jeondoman", mood: "sweat", text: "상상력이 풍부하시네요, 꼬마 씨." },
            ],
          },
        },
        {
          text: "유튜브로 물구나무 챌린지를 정주행하고 있었습니다.",
          press: {
            lines: [
              { who: "gonan", mood: "smirk", text: "챌린지? 직접 찍은 거 아니야? 행글라이더 썸네일 쓰는 채널 내가 봤거든." },
              { who: "jeondoman", mood: "shock", text: "그건… 촬영용 소품이고, 행글라이더는 그날 창고에 있었어요." },
              { who: "yujoe", mood: "angry", text: "증인, 묻지도 않은 행글라이더를 왜 변명하나." },
            ],
            add: {
              text: "행글라이더는 촬영 소품일 뿐이고, 그날은 창고에 그대로 있었습니다.",
              mood: "sweat",
              present: { harness: "cx3_break", ledger: "cx3_break" },
              press: {
                lines: [
                  { who: "inner", text: "창고? 화분에서 버클이 나왔는데. 들이밀어." },
                ],
              },
            },
          },
        },
        {
          text: "박물관은 낮에 한 번 갔을 뿐입니다. 관람, 끝.",
          present: { visitor: "cx3_nudge" },
          press: {
            lines: [
              { who: "gonan", text: "천장 창 사진 찍어도 되냐고 세 번 물은 관람이 관람이냐." },
              { who: "jeondoman", text: "건축 미학입니다. 창문은 예술이에요." },
            ],
          },
        },
        {
          text: "살인은 관심 없습니다. 취미는 건강한 운동뿐이에요.",
          press: {
            lines: [
              { who: "gonan", text: "건강한 운동으로 사람을 놀라 죽이는 종목은 몇 위에 있냐." },
              { who: "jeondoman", mood: "smirk", text: "그런 종목은 없습니다." },
            ],
          },
        },
      ],
    },
    cx3_nudge: {
      type: "talk",
      checkpoint: false,
      bg: "court",
      lines: [
        { who: "gonan", text: "낮에 ‘끝’이 아니야. 명단에 취미가 적혀 있고, 창문을 세 번이나 물어봤어." },
        { who: "jeondoman", mood: "sweat", text: "그게 살인의 증거가 되나요? 취미 적는 게 유죄면 이 나라 망했어요." },
        { who: "judge", text: "아직 부족하오. 심문을 계속하시오." },
        { who: "inner", text: "방향은 맞다. 알리바이랑 행글라이더를 깨야 해." },
      ],
      next: "RESUME_CROSS",
    },
    cx3_break: {
      type: "talk",
      bg: "court",
      lines: [
        { who: "gonan", mood: "angry", text: "집에? 창고? CCTV엔 노란 신발이 천장으로 지나갔고, 화분에 하네스가 떨어졌어." },
        { who: "jeondoman", mood: "shock", extra: "flip", text: "끄억— 각도가!" },
        { who: "judge", text: "증인이 거꾸로 섰소. 의도인가?" },
        { who: "jeondoman", extra: "flip", text: "습관입니다. 습관!" },
      ],
      next: "finale_q",
    },
    finale_q: {
      type: "talk",
      bg: "court",
      lines: [
        { who: "judge", text: "변호인, 범행 방법을 한 단어로 정리하시오. 못 하면 유죄요." },
        { who: "gonan", mood: "think", text: "드디어… 드디어! 드디어!!" },
      ],
      choice: [
        { label: "무명한이 잠결에 몽둥이로 쳤다", wrong: true },
        { label: "물구나무로 침입 → 놀라서 심장사 → 행글라이더 탈출", next: "finale" },
        { label: "박사가 청구서로 때려죽였다", wrong: true },
      ],
    },
    finale: {
      type: "talk",
      bg: "court",
      lines: [
        {
          who: "gonan",
          mood: "angry",
          splash: "reveal",
          stamp: "범인은 바로 너야!",
          text: "범인은 바로 전도만 이 새끼 당신이야!",
        },
        { who: "gonan", text: "천장 창으로 물구나무 입실. 고인물 관장 눈앞에 거꾸로 된 얼굴. 심장 약한 사람이 그걸 보면 죽지." },
        { who: "gonan", text: "그리고 행글라이더로 지붕 탈출. 예산 깎인 동호회 복수. 장비값은 박사에게 현금으로 완납. 나랑 인간부터가 다름." },
        { who: "jeondoman", mood: "shock", extra: "flip", shake: true, text: "관장이 동호회비를 끊었어! 물구나무는 예술이라고! 예술을 몰라!" },
        { who: "yujoe", mood: "shock", text: "자백이다. …이런 수법이 통할 줄은." },
        { who: "judge", text: "피고 무명한, 무죄. 증인 전도만은 구속. 그리고 변호인, 슬라이딩은 법정에서 금지요." },
        { who: "gonan", mood: "smirk", text: "이미 미끄러졌는데." },
        { who: "muhyeong", mood: "angry", text: "제 생각에 이번 일의 공범은 고난이고—" },
        { who: "gonan", shake: true, text: "마취. 잘 자. 승소 성공 보수는 내 통장으로." },
        { who: "baksa", mood: "angry", text: "고난 군——! 88만 원!" },
        { who: "miryeon", mood: "angry", text: "넌 또 뭐야." },
        { who: "gonan", mood: "sweat", text: "명탐정. 그리고 도망." },
      ],
      next: "ending",
    },
    ending: {
      type: "ending",
      checkpoint: false,
      bg: "ending",
      lines: [
        { who: "narrator", text: "제1화 두 얼굴의 누명 — 클리어." },
        { who: "narrator", text: "무명한은 풀려났고, 고난은 청구서를 들고 슬라이딩했다." },
        { who: "inner", text: "다음 화: 검은 조직인 줄 알았는데 암살할아버지였다. 착수금 선불." },
        { who: "narrator", text: "원본이 노잼이었던 이유: 클릭만 하면 끝나는 추리. 이번엔 네가 모순을 깨야 뒤집힌다." },
      ],
    },
    gameover: {
      type: "talk",
      checkpoint: false,
      bg: "court",
      lines: [
        { who: "judge", splash: "guilty", text: "이 재판은 이것으로 끝이오. 무명한, 유죄. 징역 15년." },
        { who: "muhyeong", mood: "sleep", extra: "sleep", text: "중요 단서는… 고난 가방 속에…" },
        { who: "gonan", mood: "sweat", text: "항소하면 착수금부터 다시야. 일단 체크포인트." },
      ],
      choice: [
        { label: "체크포인트에서 다시 뒤집기", next: "RETRY" },
      ],
    },
  },
};
