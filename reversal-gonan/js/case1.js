const CASE = {
  names: {
    narrator: "",
    inner: "헬멧 속",
    gonan: "고난 성",
    muhyeong: "무명한",
    baksa: "박사",
    miryeon: "미련",
    judge: "메구리만 경부",
    yujoe: "유죄만 형사",
    jeong: "경비 정문수",
    meseu: "감식 메스를",
    jeondoman: "전도만",
    victim: "고인물",
  },
  evidence: {
    badge: {
      name: "세계귀족 훈장",
      desc: "평민 호주머니에서 ‘회수’한 뱃지. 방울 헬멧 밑에 달면 숨이 트인다고 고난 성은 믿는다.",
    },
    overview: {
      name: "사건 개요",
      desc: "9월 13일 21시 전후, 시립미술관 야간 전시실. 피해자 고인물 관장. 밀실. 벽에 혈흔 글씨 「무명한」. 경찰은 무명한을 범인으로 본다.",
    },
    dying_msg: {
      name: "혈흔 글씨 「무명한」",
      desc: "전시실 벽. 피해자 피로 쓴 듯한 다잉메시지. 획이 흔들리고, 마지막 ‘한’ 자는 거의 눕다시피 했다.",
    },
    autopsy: {
      name: "부검 메모",
      desc: "사인은 흉기 자상. 사망 추정 20:50. 벽 글씨 혈흔은 시체 혈흔보다 늦게 말랐다. 즉, 글씨는 죽은 뒤에 써졌다.",
    },
    lock: {
      name: "안에서 잠긴 빗장",
      desc: "문은 안쪽 빗장이 걸려 있다. 열쇠는 피해자 속주머니. 빗장 고리에 가는 마찰 자국이 한 줄 있다.",
    },
    line: {
      name: "낚시줄",
      desc: "문 밑 틈과 창고에서 나온 투명 낚시줄. 끝에 고리가 있고, 빗장 고리 자국이랑 굵기가 같다.",
    },
    card: {
      name: "무명한의 명함",
      desc: "관장 책상 위. 오후 방문 때 두고 간 명함. ‘위작 감정 의뢰’라고 뒷면에 갈겨져 있다.",
    },
    visitor: {
      name: "출입 명단",
      desc: "낮 손님 전도만. 특이사항: 전시실 자물쇠·빗장 구조 사진을 찍어도 되냐고 두 번 물음. 야간 출입도 기록됨.",
    },
    camera: {
      name: "CCTV 캡처",
      desc: "20:30, 전도만이 정문으로 나간다. 20:51, 같은 문 틈으로 가느다란 줄이 빨려 들어가는 게 한 프레임 찍혔다.",
    },
    tranq: {
      name: "마취 권총",
      desc: "고난 성의 금장 권총. 실탄 대신 마취침. 발사 기록 20:41. 그 시각 무명한은 이미 별장 소파에서 기절.",
    },
    bump: {
      name: "무명한의 혹",
      desc: "이마 정중앙. 마취 맞고 소파에서 구른 자국. 범행 흉기와는 무관하다.",
    },
    invoice: {
      name: "박사의 청구서",
      desc: "마취침 렌탈 88만 원, 연체 이자 포함. 채무자 란에 고난 성이 크게 적혀 있다.",
    },
    shoes: {
      name: "초강력 킥운동화",
      desc: "720도 턴 킥용. 이 사건과는 무관하다. 고난은 이거로 다 해결된다고 믿는다.",
    },
    ledger: {
      name: "위작 거래 장부",
      desc: "전도만이 관장에게 「진품」을 판 기록. 사건 당일 오후, 관장이 박사에게 안료 감정을 맡겼다. 결과는 가짜.",
    },
  },
  profiles: {
    gonan: {
      name: "고난 성",
      desc: "세계귀족. 평민 공기를 직접 마시면 피부가 벗겨진다고 믿어 방울 헬멧을 쓴다. 탐정은 취미. 무명한이 입을 열면 마취 권총을 쏜다.",
    },
    muhyeong: {
      name: "무명한",
      desc: "평민 탐정. 추리력은 고난 성의 열 배. 입을 여는 순간 헬멧 너머로 마취당한다. 이번 누명 주인공.",
    },
    yujoe: {
      name: "유죄만 형사",
      desc: "유죄 외에 관심 없는 형사. 다잉메시지만 보면 수사는 끝났다고 본다.",
    },
    judge: {
      name: "메구리만 경부",
      desc: "설명을 두 번은 들어야 한다. 세 번째엔 그냥 연행한다.",
    },
    jeondoman: { name: "전도만", desc: "수집가. 진품만 취급한다고 입버릇처럼 말한다." },
    baksa: { name: "박사", desc: "발명가. 장비는 잘 만들어 주고, 돈은 더 잘 받는다. 안료 감정도 한다." },
    miryeon: { name: "미련", desc: "무명한의 지인. 고난 머리를 때리면 세상이 잠깐 평화로워진다." },
    jeong: { name: "경비 정문수", desc: "이름처럼 정직한 경비. 빗장 소리와 사람 구분을 잘 못한다." },
    meseu: { name: "감식 메스를", desc: "과학은 맞는데, 결론을 먼저 정하고 과학을 끼워 맞춘다." },
  },
  profileOrder: ["gonan", "muhyeong", "yujoe", "judge", "jeondoman", "baksa", "miryeon"],
  trialReady(state) {
    const need = ["autopsy", "dying_msg", "lock", "line", "tranq"];
    const extra = ["camera", "ledger", "visitor"].some((id) => state.evidence.includes(id));
    return need.every((id) => state.evidence.includes(id)) && state.flags.talked_muhyeong && extra;
  },
  locations: {
    museum: {
      name: "시립미술관 전시실",
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
          give: "dying_msg",
          flag: "examined_body",
          lines: [
            { who: "gonan", mood: "normal", text: "고인물 관장. 이름부터 이미 고인인데 진짜로 고인이 됐네." },
            { who: "gonan", text: "벽에 「무명한」. 경찰은 다잉메시지라며. 획이 너무 반듯하다. 죽어가면서 저렇게 쓰냐." },
            { who: "inner", text: "평민 탐정 이름을 남기면 진범은 편하지. 누가 제일 편하냐." },
          ],
        },
        {
          id: "door",
          label: "잠긴 문",
          x: 78,
          y: 38,
          w: 14,
          h: 28,
          give: "lock",
          lines: [
            { who: "gonan", mood: "think", text: "빗장이 안에서 걸려 있어. 열쇠는 시체 속주머니. 전형적인 밀실이지." },
            { who: "gonan", text: "근데 빗장 고리에 줄 자국이 있어. 열쇠로 잠근 자국이 아니야." },
            { who: "inner", text: "밀실을 밖에서 만드는 방법. 코난… 아니 이 몸이 제일 좋아하는 패턴이다." },
          ],
        },
        {
          id: "gap",
          label: "문틈",
          x: 72,
          y: 70,
          w: 16,
          h: 12,
          give: "line",
          lines: [
            { who: "gonan", mood: "smirk", text: "문 밑에 투명 줄이 한 가닥. 낚시줄이네. 고리까지 달려 있어." },
            { who: "inner", text: "빗장에 걸고 문틈으로 당기면, 안에서 잠근 것처럼 보인다. 평민 트릭치곤 나쁘지 않은데." },
          ],
        },
        {
          id: "desk2",
          label: "관장 책상",
          x: 18,
          y: 48,
          w: 18,
          h: 16,
          give: "card",
          lines: [
            { who: "gonan", text: "무명한 명함. 뒷면: 위작 감정 의뢰. 오후 방문이네. 밤에는 이 몸 소파에서 코 골고 있었고." },
            { who: "inner", text: "관장이 무명한을 부른 이유. 진범은 그 통화를 듣기만 하면 된다." },
          ],
        },
        {
          id: "list",
          label: "출입 명단",
          x: 60,
          y: 44,
          w: 16,
          h: 14,
          give: "visitor",
          lines: [
            { who: "gonan", text: "전도만. 자물쇠 사진 찍어도 되냐고 두 번이나 물었대. 한 번은 관광, 두 번은 범행 예행연습." },
            { who: "gonan", mood: "smirk", text: "야간 출입도 있다. 낮에 ‘끝’이 아닌 평민이지." },
          ],
        },
        {
          id: "cam",
          label: "카메라",
          x: 8,
          y: 18,
          w: 12,
          h: 14,
          give: "camera",
          lines: [
            { who: "gonan", text: "20:30에 전도만이 나간다. 20:51에 문틈으로 줄이 빨려 들어가. 사람이 없어도 문은 잠길 수 있지." },
          ],
        },
        {
          id: "notes",
          label: "감식 메모",
          x: 32,
          y: 28,
          w: 14,
          h: 12,
          give: "autopsy",
          lines: [
            { who: "gonan", mood: "normal", text: "메스를가 놓고 간 부검 메모. 자상, 20:50. 글씨 혈흔은 사후에 마름." },
            { who: "inner", text: "다잉메시지가 아니다. 시체 손가락을 잡고 쓴 거다. 과학이 한 번은 맞네." },
          ],
        },
      ],
      moves: [
        { to: "invest:office", label: "고난 성 별장" },
        { to: "invest:lab", label: "박사 연구소" },
        { to: "gather_intro", label: "전원 집합", requireTrial: true },
      ],
    },
    office: {
      name: "고난 성 별장",
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
          give: "bump",
          flag: "talked_muhyeong",
          lines: [
            { who: "muhyeong", extra: "sleep", mood: "sleep", text: "큭… 범인은… 정문수… 열쇠는… 그뿐…" },
            { who: "gonan", mood: "smirk", text: "20:41에 마취. 이마 혹 예쁘다. 이 평민은 범행 시각에 코 골고 있었어." },
            { who: "inner", text: "알리바이다. 다잉메시지랑 정면 충돌. 전원 집합 때 들이밀자." },
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
            { who: "gonan", mood: "shock", text: "청구서다. 88만 원. 평민이 세계귀족에게 돈을 달라고? 노예 등록부터 하지." },
            { who: "inner", text: "진범한테 받아내면 된다. 진범이 있어야 청구서가 움직인다." },
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
            { who: "gonan", mood: "smirk", text: "마취 권총. 발사 20:41. 저 평민은 범행 전에 이미 잠들었다." },
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
            { who: "gonan", mood: "sweat", text: "그거 없으면 헬멧이 굴러가질 않는데. 외상. 진범한테 받아낼게." },
            { who: "baksa", text: "참고로 관장이 오늘 오후에 안료 감정을 맡겼다. 전도만이라는 사람이 판 그림. 가짜더라." },
            { who: "gonan", mood: "think", text: "위작을 들킨 평민이 관장을 부르기 전에 입을 막은 거네." },
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
            { who: "miryeon", mood: "angry", text: "무명한 삼촌 누명인 거 너 때문이잖아. 넌 또 뭐야?" },
            { who: "gonan", mood: "shock", text: "명탐정이야. 때리면 진실이 거짓이 된다고. 손 내려." },
            { who: "miryeon", text: "머리 한 대만." },
            { who: "gonan", mood: "sweat", shake: true, text: "아! 잠깐 천재가 된 것 같— 아니다 그냥 아프다." },
          ],
        },
      ],
      moves: [
        { to: "invest:museum", label: "시립미술관" },
        { to: "invest:lab", label: "박사 연구소" },
        { to: "gather_intro", label: "전원 집합", requireTrial: true },
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
            { who: "gonan", mood: "smirk", text: "증거로 쓸게. 720도 킥은 추궁 현장에서도 통하거든." },
            { who: "inner", text: "통하지 않는다. 그래도 가져간다." },
          ],
        },
        {
          id: "book",
          label: "감정 장부",
          x: 58,
          y: 42,
          w: 18,
          h: 16,
          give: "ledger",
          lines: [
            { who: "baksa", text: "전도만. 「진품」 판매. 관장이 의뢰한 안료 감정은 가짜. 결과 통보 전에 관장이 죽었다." },
            { who: "gonan", mood: "think", text: "범인이 장비값까지 내는 사람은 처음 본다. 나랑 인간부터가 다름." },
          ],
        },
      ],
      moves: [
        { to: "invest:office", label: "고난 성 별장" },
        { to: "invest:museum", label: "시립미술관" },
        { to: "gather_intro", label: "전원 집합", requireTrial: true },
      ],
    },
  },
  scenes: {
    prologue: {
      type: "talk",
      bg: "night",
      lines: [
        { who: "narrator", text: "2026년 9월 13일. 시립미술관." },
        { who: "narrator", text: "폐관 후, 관장 고인물이 밀실 전시실에서 숨진 채 발견되었다." },
        { who: "narrator", text: "벽에는 혈흔으로 「무명한」. 문은 안에서 잠겨 있었다." },
        { who: "judge", bg: "museum", text: "다잉메시지가 아니오. 범인은 그 탐정, 무명한. 연행합시다." },
        { who: "yujoe", mood: "smirk", text: "명백하다. 이름까지 남겨 놓고 도망을 못 친 거지." },
        { who: "muhyeong", mood: "angry", text: "아니! 제 생각에 범인은 경비 정문수입니다! 열쇠를 가진 건 그뿐이니까!" },
        { who: "gonan", mood: "smirk", text: "평민이 추리하면 이 몸의 시간이 줄어든다." },
        {
          who: "gonan",
          mood: "angry",
          splash: "take",
          stamp: "마취다!",
          shake: true,
          text: "쿨럭. 마취. 잘 자, 평민. 네 추리는 소파에서나 해.",
        },
        { who: "muhyeong", extra: "sleep", mood: "sleep", text: "큭… 중요 단서는… 문틈에…" },
        { who: "inner", text: "지금부터 이 몸이 추리한다. 현장, 밀실, 가짜 글씨. 코난이 하던 그거. 이번엔 헬멧이 한다." },
        { who: "narrator", text: "단서를 모아라. 안 모으면 무명한만 연행된다." },
      ],
      next: "invest:museum",
    },
    gather_intro: {
      type: "talk",
      bg: "museum",
      lines: [
        { who: "judge", text: "다들 모였소. 방울 꼬마, 빨리 범인을 말하시오. 아니면 무명한을 연행하오." },
        { who: "yujoe", mood: "smirk", text: "다잉메시지에 이름이 있다. 수사는 끝났다. 쇼는 짧게." },
        { who: "gonan", mood: "angry", text: "쇼가 아니야. 진실은 언제나 하나고, 그 하나를 이 몸이 정한다." },
        { who: "inner", text: "증언을 하나씩 추궁해. 거짓말이 보이면 증거를 들이밀어. 틀리면 저 평민이 지구대다." },
      ],
      next: "cx1",
    },
    cx1: {
      type: "cross",
      bg: "museum",
      witness: "jeong",
      intro: [
        { who: "judge", text: "경비, 그날 밤을 말하시오." },
        { who: "jeong", text: "네. 저는 정직합니다. 이름부터." },
      ],
      statements: [
        {
          text: "폐관 후 전시실은 완전히 잠겼습니다. 열쇠는 저뿐입니다.",
          press: {
            lines: [
              { who: "gonan", mood: "smirk", text: "열쇠만? 빗장은? 안에서 거는 그거. 평민 머리로도 떠오르지 않냐." },
              { who: "jeong", text: "빗장도 있습니다. 안에서 안 걸면 안 걸립니다." },
              { who: "inner", text: "빗장 쪽이 허점이다. 자국 증거를 들이밀 타이밍." },
            ],
          },
        },
        {
          text: "그 이후 안으로 들어간 사람은 무명한 탐정뿐입니다.",
          press: {
            lines: [
              { who: "gonan", text: "무명한은 오후에 왔다가 나갔어. 밤에 안에 있던 건 이 몸 소파야." },
              { who: "jeong", text: "명함이 안에 있어서… 들어간 줄 알았습니다." },
              { who: "yujoe", mood: "smirk", text: "명함이 있으면 범인이다. 수사 끝." },
            ],
          },
        },
        {
          text: "전도만 씨는 밤 8시 30분에 나갔습니다. 그 뒤로는 안 돌아왔습니다.",
          press: {
            lines: [
              { who: "gonan", mood: "angry", text: "사람이 안 돌아와도, 줄은 돌아올 수 있어. 문에서 소리 못 들었어?" },
              { who: "jeong", mood: "sweat", text: "아… 8시 52분쯤 찰칵 소리가 났습니다. 바람인 줄 알았어요." },
            ],
            add: {
              text: "8시 52분쯤 문에서 찰칵 소리가 났습니다만, 바람인 줄 알았습니다.",
              mood: "sweat",
              present: { camera: "cx1_break", line: "cx1_break" },
              press: {
                lines: [
                  { who: "gonan", text: "바람이 빗장을 걸냐. 줄이 걸지." },
                  { who: "jeong", text: "줄은… 못 봤습니다." },
                  { who: "inner", text: "CCTV나 낚시줄을 들이밀어." },
                ],
              },
            },
          },
        },
        {
          text: "밀실입니다. 안에서 잠그지 않으면 빗장이 안 걸립니다. 다른 출입구는 없습니다.",
          present: { lock: "cx1_break", line: "cx1_break" },
          press: {
            lines: [
              { who: "gonan", mood: "think", text: "문틈은? 낚시줄은? 평민 경비면 바닥은 봐야지." },
              { who: "jeong", text: "바닥은 봤습니다. 시체만 있었습니다." },
              { who: "inner", text: "빗장 자국이랑 줄을 들이밀 타이밍이다." },
            ],
          },
        },
      ],
    },
    cx1_break: {
      type: "talk",
      bg: "museum",
      lines: [
        { who: "gonan", mood: "angry", text: "밀실이 아니야. 문틈으로 줄을 걸면 밖에서 빗장이 잠긴다. 열쇠는 시체 주머니에 넣으면 끝이지." },
        { who: "jeong", mood: "shock", text: "그, 그건… 바람인 줄…" },
        { who: "yujoe", mood: "angry", text: "밀실이 깨져도 다잉메시지는 남는다. 벽에 이름이 있다." },
        { who: "gonan", mood: "smirk", text: "이름이 있다고 범인이냐. 글씨부터 감식해." },
        { who: "judge", text: "일단… 출입은 의문이 생겼소. 감식, 나와 보시오." },
      ],
      next: "cx2",
    },
    cx2: {
      type: "cross",
      bg: "museum",
      witness: "meseu",
      intro: [
        { who: "meseu", text: "감식과장 메스를입니다. 과학은 다잉메시지이고, 다잉메시지는 무명한입니다." },
        { who: "gonan", mood: "normal", text: "과학이 한 단어로 끝나면 박사 청구서가 안 나와." },
      ],
      statements: [
        {
          text: "사인은 흉기에 의한 자상입니다. 그 외의 가능성은 없습니다.",
          press: {
            lines: [
              { who: "gonan", text: "그건 맞다. 이 몸은 인정해. 드문 일이야." },
              { who: "meseu", text: "감사합니다. 그러면 범인도 인정하십시오." },
              { who: "inner", text: "사인은 맞다. 글씨가 가짜다." },
            ],
          },
        },
        {
          text: "벽의 「무명한」은 피해자가 범인 이름을 남긴 다잉메시지입니다.",
          present: { autopsy: "cx2_break" },
          press: {
            lines: [
              { who: "gonan", text: "죽어가면서 자기 의뢰인 이름을 또박또박? 평민 손글씨치곤 너무 정성이야." },
              { who: "meseu", text: "공포 속에서도 정의는 남습니다." },
              { who: "inner", text: "부검 메모랑 정면 충돌이다. 들이밀어." },
            ],
          },
        },
        {
          text: "혈흔형으로 보아 글씨는 범행 직후, 피해자의 손으로 쓰였습니다.",
          present: { autopsy: "cx2_break" },
          press: {
            lines: [
              { who: "gonan", text: "직후? 죽은 뒤지. 네 메모에 그렇게 적혀 있어. 현장에 두고 온 그거." },
              { who: "meseu", mood: "sweat", text: "메모는… 초안입니다. 과학의 초안." },
            ],
          },
        },
        {
          text: "따라서 범인은 무명한입니다. 이름이 남아 있으니까요.",
          present: { tranq: "cx2_break", bump: "cx2_break" },
          press: {
            lines: [
              { who: "gonan", mood: "smirk", text: "20:41에 그 평민은 내 소파에서 기절해 있었어. 시체가 이름을 쓸 때 코 골고 있었지." },
              { who: "meseu", text: "기절은 과학이 아닙니다." },
              { who: "yujoe", mood: "smirk", text: "마취는 알리바이가 아니다. 범행 도구다." },
            ],
          },
        },
      ],
    },
    cx2_break: {
      type: "talk",
      bg: "museum",
      lines: [
        { who: "gonan", mood: "angry", text: "다잉메시지가 아니야! 글씨는 사후에 써졌다. 시체 손가락을 잡고 「무명한」을 쓴 거야." },
        { who: "meseu", mood: "shock", text: "부검 메모를… 현장에 두고 왔군요. 과학의 패배입니다." },
        { who: "yujoe", mood: "angry", text: "가짜 글씨여도 범인은 있다. 누명을 씌운 자가 범인이지." },
        { who: "judge", text: "그렇다면 자물쇠에 관심이 많던 인물을 부르겠소. 전도만." },
        { who: "jeondoman", mood: "smirk", text: "저요? 전 그냥 건전한 수집가인데요." },
      ],
      next: "cx3",
    },
    cx3: {
      type: "cross",
      bg: "museum",
      witness: "jeondoman",
      intro: [
        { who: "judge", text: "알리바이를 말하시오." },
        { who: "jeondoman", text: "물론이죠. 전 8시 30분에 나갔습니다. 진품만 취급하는 사람답게, 현장에도 안 남겼어요." },
        { who: "inner", text: "이 새끼 말이 벌써 그림이야. 추궁해서 줄이랑 위작을 꺼내." },
      ],
      statements: [
        {
          text: "저는 그날 밤 8시 30분에 나갔습니다. 그 이후 미술관에는 그림자도 안 남겼어요.",
          present: { camera: "cx3_break" },
          press: {
            lines: [
              { who: "gonan", text: "그림자를 안 남겨도, 줄은 남기지. 20:51 프레임." },
              { who: "jeondoman", mood: "sweat", text: "상상력이 풍부하시네요, 꼬마 씨." },
            ],
          },
        },
        {
          text: "미술관은 낮에 그림만 보고 갔습니다. 관람, 끝.",
          present: { visitor: "cx3_nudge" },
          press: {
            lines: [
              { who: "gonan", text: "자물쇠 사진 찍어도 되냐고 두 번 물은 관람이 관람이냐." },
              { who: "jeondoman", text: "건축 미학입니다. 빗장은 예술이에요." },
            ],
          },
        },
        {
          text: "낚시 같은 건 취미가 아닙니다. 전 손을 더럽히지 않아요.",
          press: {
            lines: [
              { who: "gonan", mood: "smirk", text: "손은 안 더럽히고 줄만 더럽히지. 창고에 낚시줄, 문틈에도 낚시줄." },
              { who: "jeondoman", mood: "shock", text: "그건… 포장용 실이고, 전 그날 창고에 안 갔어요." },
              { who: "yujoe", mood: "angry", text: "증인, 묻지도 않은 창고를 왜 변명하나." },
            ],
            add: {
              text: "포장용 실일 뿐이고, 그날은 창고에 가지도 않았습니다.",
              mood: "sweat",
              present: { line: "cx3_break", ledger: "cx3_break" },
              press: {
                lines: [
                  { who: "inner", text: "창고? 문틈에서 줄이 나왔는데. 들이밀어." },
                ],
              },
            },
          },
        },
        {
          text: "위작 같은 추한 말, 관심 없습니다. 전 진품만 취급합니다.",
          present: { ledger: "cx3_break" },
          press: {
            lines: [
              { who: "gonan", text: "관장이 안료 감정 맡긴 그 진품. 가짜더라. 결과가 나가기 전에 입을 막은 거지." },
              { who: "jeondoman", mood: "smirk", text: "감정은 취향입니다. 취향으로 사람을 안 죽입니다." },
            ],
          },
        },
      ],
    },
    cx3_nudge: {
      type: "talk",
      checkpoint: false,
      bg: "museum",
      lines: [
        { who: "gonan", text: "낮에 ‘끝’이 아니야. 명단에 빗장 질문이 두 번이고, 야간 출입도 있어." },
        { who: "jeondoman", mood: "sweat", text: "그게 살인의 증거가 되나요? 질문하는 게 유죄면 이 나라 망했어요." },
        { who: "judge", text: "아직 부족하오. 추궁을 계속하시오." },
        { who: "inner", text: "방향은 맞다. 알리바이랑 줄을 깨야 해." },
      ],
      next: "RESUME_CROSS",
    },
    cx3_break: {
      type: "talk",
      bg: "museum",
      lines: [
        { who: "gonan", mood: "angry", text: "집에? 창고에 안 가? CCTV엔 줄이 빨려 들어가고, 문틈엔 낚시줄이 남아 있어." },
        { who: "jeondoman", mood: "shock", text: "끄억— 그, 그건 포장용…" },
        { who: "judge", text: "증인의 얼굴이 가짜 그림처럼 변했소." },
        { who: "jeondoman", text: "습관입니다. 습관!" },
      ],
      next: "finale_q",
    },
    finale_q: {
      type: "talk",
      bg: "museum",
      lines: [
        { who: "judge", text: "방울 꼬마, 밀실을 한 문장으로 설명하시오. 못 하면 무명한을 연행하오." },
        { who: "gonan", mood: "think", text: "드디어… 드디어! 드디어!!" },
      ],
      choice: [
        { label: "무명한이 안에서 찌르고 자기 이름을 남겼다", wrong: true },
        { label: "문틈으로 낚시줄을 걸어 밖에서 빗장을 잠갔다", next: "finale" },
        { label: "천장 창으로 물구나무 침입 후 행글라이더 탈출", wrong: true },
      ],
    },
    finale: {
      type: "talk",
      bg: "museum",
      lines: [
        {
          who: "gonan",
          mood: "angry",
          splash: "reveal",
          stamp: "범인은 바로 너야!",
          text: "범인은 바로 너야, 전도만. 이 평민 새끼.",
        },
        { who: "gonan", text: "관장이 네 가짜 그림을 감정에 넘겼어. 결과가 나가기 전에 입을 막아야 했지." },
        { who: "gonan", text: "찌른 다음, 시체 손가락으로 「무명한」을 썼다. 오후에 명함을 두고 간 평민 탐정에게 누명을 씌운 거야." },
        { who: "gonan", text: "빗장에 낚시줄을 걸고 문틈으로 당긴다. 안에서 잠긴 밀실. 줄은 회수. 너는 8시 30분에 ‘나간’ 사람이 되지." },
        { who: "jeondoman", mood: "shock", shake: true, text: "관장이 진품을 가짜라 했어! 내 수집은 예술이라고! 예술을 몰라!" },
        { who: "yujoe", mood: "shock", text: "자백이다. …이런 수법이 통할 줄은." },
        { who: "judge", text: "무명한, 누명 해제. 전도만은 구속. 그리고 방울 꼬마, 현장에서 권총은 금지요." },
        { who: "gonan", mood: "smirk", text: "마취침이야. 평민 진정제. 이미 한 명 재웠는데." },
        { who: "muhyeong", mood: "angry", text: "제 생각에 이번 일의 공범은 고난 성이고—" },
        { who: "gonan", shake: true, mood: "angry", text: "마취. 잘 자, 평민. 착수금은 이 몸 통장으로." },
        { who: "baksa", mood: "angry", text: "고난 성——! 88만 원!" },
        { who: "miryeon", mood: "angry", text: "넌 또 뭐야. 그 방울 벗고 얘기해." },
        { who: "gonan", mood: "sweat", text: "세계귀족은 도망도 품위 있게. 굴려." },
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
        { who: "narrator", text: "진실은 언제나 하나. 단, 발표권은 방울 헬멧이 가지고 있다." },
      ],
    },
    gameover: {
      type: "talk",
      checkpoint: false,
      bg: "museum",
      lines: [
        { who: "judge", splash: "guilty", stamp: "연행", text: "이 수사는 이것으로 끝이오. 무명한, 연행. 다잉메시지면 충분하오." },
        { who: "muhyeong", mood: "sleep", extra: "sleep", text: "중요 단서는… 고난 가방 속에…" },
        { who: "gonan", mood: "sweat", text: "항소하면 착수금부터 다시야. 일단 체크포인트." },
      ],
      choice: [
        { label: "체크포인트에서 다시 추리", next: "RETRY" },
      ],
    },
  },
};
