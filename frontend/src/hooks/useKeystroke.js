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
    // flight = up-to-up, matching the original hook. The service IGNORES this
    // field (it derives all 24 features from key_down/key_up itself), so we keep
    // the original semantics to minimise changes to this shared file.
    const flightTimes = completed
      .slice(1)
      .map((entry, index) => entry.up - completed[index].up);

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