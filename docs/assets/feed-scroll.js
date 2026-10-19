/* 피드 최상단 고무줄 스크롤만 담당한다. 글 렌더/필터는 app.js. */
(function (root) {
  const MAX_PULL = 88;
  const THRESHOLD = 48;
  const RESIST = 0.38;
  const RELEASE_MS = 420;

  function attach(scroller, options) {
    const feed = options.feed;
    const head = options.head;
    let pull = 0;
    let tracking = false;
    let pulling = false;
    let releasing = false;
    let startY = 0;
    let startPull = 0;
    let wheelTimer = 0;

    function atTop() {
      return scroller.scrollTop <= 1;
    }

    function showHead(on) {
      head.classList.toggle("show", on);
    }

    function setPull(px, withTransition) {
      pull = Math.max(0, Math.min(MAX_PULL, px));
      feed.style.transition = withTransition
        ? `transform ${RELEASE_MS}ms cubic-bezier(0.22, 1.45, 0.36, 1)`
        : "none";
      feed.style.willChange = pull || withTransition ? "transform" : "";
      feed.style.transform = pull ? `translate3d(0, ${pull}px, 0)` : "";
      const t = MAX_PULL ? pull / MAX_PULL : 0;
      head.style.setProperty("--pull", t.toFixed(3));
      showHead(atTop() || pull > 1);
    }

    function release(allowLoad) {
      tracking = false;
      pulling = false;
      window.clearTimeout(wheelTimer);
      if (pull <= 0) {
        setPull(0, false);
        showHead(atTop());
        return;
      }
      /* 휠은 고무줄만 하고 글을 붙이지 않는다. 터치로 충분히 당겼을 때만 이전 50개를 붙인다. */
      const shouldLoad = allowLoad && pull >= THRESHOLD && options.canLoadOlder();
      releasing = true;
      if (shouldLoad) options.onPullOlder();
      setPull(0, true);
      window.setTimeout(() => {
        releasing = false;
        feed.style.transition = "";
        showHead(atTop());
      }, RELEASE_MS);
    }

    scroller.addEventListener(
      "wheel",
      (event) => {
        if (releasing) {
          event.preventDefault();
          return;
        }
        if (event.deltaY < 0 && atTop()) {
          event.preventDefault();
          setPull(pull + -event.deltaY * RESIST, false);
          window.clearTimeout(wheelTimer);
          wheelTimer = window.setTimeout(() => release(false), 140);
        } else if (pull > 0 && event.deltaY > 0) {
          event.preventDefault();
          setPull(pull - event.deltaY * RESIST, false);
          if (pull <= 0) release(false);
        }
      },
      { passive: false },
    );

    scroller.addEventListener(
      "touchstart",
      (event) => {
        if (!atTop() && pull <= 0) return;
        tracking = true;
        startY = event.touches[0].clientY;
        startPull = pull;
      },
      { passive: true },
    );

    scroller.addEventListener(
      "touchmove",
      (event) => {
        if (!tracking || releasing) return;
        const dy = event.touches[0].clientY - startY;
        if (dy > 4 && atTop()) {
          pulling = true;
          if (event.cancelable) event.preventDefault();
          setPull(startPull + dy * RESIST, false);
        } else if (pulling) {
          if (event.cancelable) event.preventDefault();
          setPull(startPull + dy * RESIST, false);
          if (pull <= 0 && dy < 0) {
            tracking = false;
            pulling = false;
          }
        } else if (!atTop()) {
          tracking = false;
        }
      },
      { passive: false },
    );

    scroller.addEventListener(
      "touchend",
      () => {
        if (pulling || pull > 0) release(true);
        tracking = false;
        pulling = false;
      },
      { passive: true },
    );

    scroller.addEventListener(
      "touchcancel",
      () => {
        if (pull > 0) release(true);
        tracking = false;
        pulling = false;
      },
      { passive: true },
    );

    function syncHead() {
      if (pull > 0 || releasing) return;
      showHead(atTop());
    }

    return { syncHead, atTop, reset: () => setPull(0, false) };
  }

  root.FeedScroll = { attach };
})(window);
