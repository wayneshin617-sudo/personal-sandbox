/* 지정한 나는솔로 쇼츠를 오디오만 반복한다. 브라우저 정책상 켠 뒤에만 재생된다. */
(function () {
  const VIDEO_ID = "DnJHXGvCpxM";
  const button = document.querySelector("#bgm-toggle");
  if (!button) return;

  let player = null;
  let on = false;
  let loading = false;

  function label() {
    button.textContent = on ? "BGM 끄기" : "BGM 켜기";
    button.setAttribute("aria-pressed", String(on));
  }

  function ensureApi() {
    if (window.YT?.Player) return Promise.resolve();
    return new Promise((resolve) => {
      const prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = function () {
        if (typeof prev === "function") prev();
        resolve();
      };
      if (!document.querySelector("script[src*='youtube.com/iframe_api']")) {
        const script = document.createElement("script");
        script.src = "https://www.youtube.com/iframe_api";
        document.head.appendChild(script);
      }
    });
  }

  async function start() {
    if (loading) return;
    loading = true;
    try {
      await ensureApi();
      if (!player) {
        const host = document.querySelector("#bgm-host");
        player = new window.YT.Player(host, {
          videoId: VIDEO_ID,
          width: 1,
          height: 1,
          playerVars: {
            autoplay: 1,
            controls: 0,
            disablekb: 1,
            fs: 0,
            loop: 1,
            playlist: VIDEO_ID,
            modestbranding: 1,
            playsinline: 1,
            rel: 0,
          },
          events: {
            onReady(event) {
              event.target.setVolume(52);
              event.target.playVideo();
            },
            onStateChange(event) {
              if (on && event.data === window.YT.PlayerState.ENDED) event.target.playVideo();
            },
          },
        });
      } else {
        player.playVideo();
      }
      on = true;
      label();
    } finally {
      loading = false;
    }
  }

  function stop() {
    on = false;
    label();
    try {
      player?.pauseVideo();
    } catch {
      /* 플레이어가 아직 없으면 그냥 끈다. */
    }
  }

  button.addEventListener("click", () => {
    if (on) stop();
    else start();
  });
  label();
})();
