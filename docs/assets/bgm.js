/* 지정한 나는솔로 쇼츠를 오디오만 반복한다. 클릭과 같은 턴에 iframe을 넣어 자동재생이 막히지 않게 한다. */
(function () {
  const VIDEO_ID = "DnJHXGvCpxM";
  const buttons = [...document.querySelectorAll(".bgm-toggle")];
  const host = document.querySelector("#bgm-host");
  if (!buttons.length || !host) return;

  let player = null;
  let on = false;

  function embedSrc(play) {
    const origin = encodeURIComponent(location.origin);
    return `https://www.youtube.com/embed/${VIDEO_ID}?autoplay=${play ? 1 : 0}&loop=1&playlist=${VIDEO_ID}&playsinline=1&controls=0&enablejsapi=1&rel=0&origin=${origin}`;
  }

  function label() {
    for (const button of buttons) {
      const compact = button.dataset.bgm === "compact";
      button.textContent = on ? (compact ? "BGM 끔" : "BGM 끄기") : compact ? "BGM" : "BGM 켜기";
      button.setAttribute("aria-pressed", String(on));
    }
  }

  function ensureApi() {
    if (window.YT?.Player || document.querySelector("script[src*='youtube.com/iframe_api']")) return;
    const script = document.createElement("script");
    script.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(script);
  }

  function bindPlayer() {
    const iframe = host.querySelector("iframe");
    if (!iframe || !window.YT?.Player || player) return;
    player = new window.YT.Player(iframe, {
      events: {
        onReady(event) {
          if (!on) {
            event.target.pauseVideo();
            return;
          }
          event.target.unMute();
          event.target.setVolume(56);
          event.target.playVideo();
        },
        onStateChange(event) {
          if (on && event.data === window.YT.PlayerState.ENDED) event.target.playVideo();
        },
      },
    });
  }

  function start() {
    on = true;
    label();
    if (player) {
      try {
        player.unMute();
        player.playVideo();
      } catch {
        /* onReady가 이어서 재생한다. */
      }
      return;
    }
    let iframe = host.querySelector("iframe");
    if (!iframe) {
      iframe = document.createElement("iframe");
      iframe.id = "bgm-frame";
      iframe.allow = "autoplay; encrypted-media";
      iframe.title = "배경 음악";
      host.append(iframe);
    }
    iframe.src = embedSrc(true);
    bindPlayer();
  }

  function stop() {
    on = false;
    label();
    try {
      player?.pauseVideo();
    } catch {
      /* 플레이어가 없으면 iframe만 멈춘다. */
    }
    const iframe = host.querySelector("iframe");
    if (!player && iframe) iframe.src = embedSrc(false);
  }

  window.onYouTubeIframeAPIReady = function () {
    bindPlayer();
  };

  for (const button of buttons) {
    button.addEventListener("click", () => {
      if (on) stop();
      else start();
    });
  }

  ensureApi();
  label();
})();
