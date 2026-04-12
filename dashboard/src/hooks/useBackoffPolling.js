import { useEffect, useRef } from "react";

export function useBackoffPolling({
  enabled,
  onTick,
  initialDelayMs = 2000,
  maxDelayMs = 30000,
  factor = 2,
  jitterRatio = 0.15,
}) {
  const timerRef = useRef(null);

  useEffect(() => {
    if (!enabled) {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      return undefined;
    }

    let stopped = false;
    let currentDelay = initialDelayMs;

    const run = async () => {
      if (stopped) return;

      const succeeded = await onTick();
      if (stopped) return;

      if (succeeded) {
        currentDelay = initialDelayMs;
      } else {
        currentDelay = Math.min(maxDelayMs, Math.round(currentDelay * factor));
      }

      const jitter = Math.round(currentDelay * jitterRatio * Math.random());
      timerRef.current = setTimeout(run, currentDelay + jitter);
    };

    run();

    return () => {
      stopped = true;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [enabled, factor, initialDelayMs, jitterRatio, maxDelayMs, onTick]);
}
