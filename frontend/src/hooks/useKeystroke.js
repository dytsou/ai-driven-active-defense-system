import { useCallback, useRef } from "react";

export function useKeystroke() {
  const timingRef = useRef({
    keyDown: [],
    keyUp: [],
    dwellTimes: [],
    flightTimes: [],
    lastKeyDown: null,
  });

  const onKeyDown = useCallback((event) => {
    if (event.repeat) return;
    const timing = timingRef.current;
    const now = performance.now();
    timing.keyDown.push(now);
    timing.flightTimes.push(timing.lastKeyDown === null ? -1 : now - timing.lastKeyDown);
    timing.lastKeyDown = now;
  }, []);

  const onKeyUp = useCallback(() => {
    const timing = timingRef.current;
    const now = performance.now();
    timing.keyUp.push(now);
    if (timing.keyDown.length > 0) {
      const down = timing.keyDown[timing.keyDown.length - 1];
      timing.dwellTimes.push(now - down);
    }
  }, []);

  const keyHandlers = { onKeyDown, onKeyUp };

  const getPayload = useCallback(() => {
    const timing = timingRef.current;
    return {
      present: Math.min(timing.keyDown.length, timing.keyUp.length) >= 5,
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
