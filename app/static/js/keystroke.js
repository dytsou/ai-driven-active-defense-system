(function () {
  const timing = {
    keyDown: [],
    keyUp: [],
    dwellTimes: [],
    flightTimes: [],
  };
  let lastKeyUp = null;

  function onKeyDown() {
    timing.keyDown.push(performance.now());
  }

  function onKeyUp(event) {
    const now = performance.now();
    timing.keyUp.push(now);
    if (timing.keyDown.length > 0) {
      const down = timing.keyDown[timing.keyDown.length - 1];
      timing.dwellTimes.push(now - down);
    }
    if (lastKeyUp !== null) {
      timing.flightTimes.push(now - lastKeyUp);
    }
    lastKeyUp = now;
  }

  function getPayload() {
    return {
      present: timing.dwellTimes.length > 0,
      timing: {
        key_down: timing.keyDown,
        key_up: timing.keyUp,
        dwell_times: timing.dwellTimes,
        flight_times: timing.flightTimes,
      },
    };
  }

  window.ActiveDefenseKeystroke = {
    attach: function attach(selector) {
      const fields = document.querySelectorAll(selector);
      fields.forEach((field) => {
        field.addEventListener("keydown", onKeyDown);
        field.addEventListener("keyup", onKeyUp);
      });
    },
    getPayload,
  };
})();
