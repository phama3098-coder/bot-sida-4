//#region src/core/spring.d.ts
declare class Spring {
  x: number;
  v: number;
  k: number;
  c: number;
  config(k: number, c: number): void;
  /** Starts (or restarts mid-flight) preserving velocity. */
  start(): void;
  /** Advances dt seconds. Returns true on settle (|1−x| < 0.001 ∧ |v| < 0.02). */
  step(dt: number): boolean;
}
/** Spring presets (ζ = c/(2√k)) with the API's public names. */
declare const SPRING_PRESETS: {
  /** ζ = 1.00 — critically damped, no overshoot. */
  readonly smooth: {
    readonly k: 170;
    readonly c: 26;
  };
  /** ζ = 0.73 — fast, subtle overshoot. */
  readonly snappy: {
    readonly k: 420;
    readonly c: 30;
  };
  /** ζ = 0.40 — playful. */
  readonly bouncy: {
    readonly k: 300;
    readonly c: 14;
  };
};
type SpringPreset = keyof typeof SPRING_PRESETS;
//#endregion
export { Spring as n, SpringPreset as r, SPRING_PRESETS as t };