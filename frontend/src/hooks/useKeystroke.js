import { useCallback, useRef } from "react";

export function useKeystroke() {
  const timingRef = useRef({
    keyDown: [],
    keyUp: [],
    dwellTimes: [],
    flightTimes: [],
    lastKeyUp: null,
  });

  const onKeyDown = useCallback(() => {
    timingRef.current.keyDown.push(performance.now());
  }, []);

  const onKeyUp = useCallback(() => {
    const timing = timingRef.current;
    const now = performance.now();
    timing.keyUp.push(now);
    if (timing.keyDown.length > 0) {
      const down = timing.keyDown[timing.keyDown.length - 1];
      timing.dwellTimes.push(now - down);
    }
    if (timing.lastKeyUp !== null) {
      timing.flightTimes.push(now - timing.lastKeyUp);
    }
    timing.lastKeyUp = now;
  }, []);

  const keyHandlers = { onKeyDown, onKeyUp };

  const getPayload = useCallback(() => {
    const timing = timingRef.current;
    return {
      present: timing.dwellTimes.length >= 3,
      timing: {
        key_down: [...timing.keyDown],
        key_up: [...timing.keyUp],
        dwell_times: [...timing.dwellTimes],
        flight_times: [...timing.flightTimes],
      },
    };
  }, []);

  return { keyHandlers, getPayload };
}
