import { useCallback, useRef } from "react";

// statistical floor for sending keystroke timing; mirrors the service's
// min_keys. Not a real-login-length assumption (model is length-agnostic).
const MIN_KEY_PAIRS = 10;

export function useKeystroke() {
  const timingRef = useRef({
    events: [],
    pendingByCode: {},
  });

  const onKeyDown = useCallback((event) => {
    if (event.repeat) return;
    const timing = timingRef.current;
    const now = performance.now();
    const entry = { code: event.code, down: now, up: null };
    timing.events.push(entry);
    if (!timing.pendingByCode[event.code]) {
      timing.pendingByCode[event.code] = [];
    }
    timing.pendingByCode[event.code].push(entry);
  }, []);

  const onKeyUp = useCallback((event) => {
    const timing = timingRef.current;
    const now = performance.now();
    const pending = timing.pendingByCode[event.code] || [];
    const entry = pending.shift();
    if (entry) {
      entry.up = now;
    }
  }, []);

  const keyHandlers = { onKeyDown, onKeyUp };

  const getPayload = useCallback(() => {
    const timing = timingRef.current;
    const completed = timing.events.filter((entry) => entry.up !== null);
    const keyDown = completed.map((entry) => entry.down);
    const keyUp = completed.map((entry) => entry.up);
    const dwellTimes = completed.map((entry) => entry.up - entry.down);
    const flightTimes = completed.map((entry, index) =>
      index === 0 ? -1 : entry.down - completed[index - 1].down
    );

    return {
      present: completed.length >= MIN_KEY_PAIRS,
      timing: {
        key_down: keyDown,
        key_up: keyUp,
        dwell_times: dwellTimes,
        flight_times: flightTimes,
      },
    };
  }, []);

  return { keyHandlers, getPayload };
}
