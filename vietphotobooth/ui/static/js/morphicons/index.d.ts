import { a as IconInput, c as Sampled, i as CubicPath, n as PlanItem, o as IconNode, r as buildPlan, s as IconNodeAttrs, t as MorphPlan } from "./plan-DhaDhEVq.js";
import { n as Spring, r as SpringPreset, t as SPRING_PRESETS } from "./spring-BgZHrI2W.js";
//#region src/core/interpolate.d.ts
/** Preallocated output buffers for a plan (zero allocation per frame). */
export declare function allocOutputs(plan: MorphPlan): Float64Array[];
export declare function interpPolar(plan: MorphPlan, t: number, out: Float64Array[]): void;
/** Raw coordinate lerp (same correspondence, no decomposition). */
export declare function interpLinear(plan: MorphPlan, t: number, out: Float64Array[]): void;
//#endregion
//#region src/core/normalize.d.ts
/** Icon (IconNode or `d` string) → list of cubic subpaths. */
export declare function iconToCubics(input: IconInput): CubicPath[];
/** A source viewBox: `24`, `"0 0 20 20"` or `[minX, minY, w, h]`. */
type ViewBox = number | string | readonly [number, number, number, number];
/** Re-grids an icon drawn on `viewBox` onto the shared `grid` (24 by default),
 *  centred and preserving aspect ratio — the SVG `xMidYMid meet` rule.
 *
 *  Both endpoints of a morph must live on the same coordinate space. Lucide and
 *  Tabler already draw on 24×24; packs on 20 (Heroicons solid) or 32 (Carbon)
 *  do not, and mixing them unfitted makes Procrustes read the scale/offset gap
 *  as rotation. Apply once at module scope (not per render) and pass the
 *  resulting `d` anywhere an icon is accepted. */
export declare function fitIcon(input: IconInput, viewBox: ViewBox, grid?: number): string;
//#endregion
//#region src/core/resample.d.ts
/** Samples a cubic subpath at N points equidistant by arc length, anchoring
 *  corners and endpoints as exact samples. Returns Float64Array(2N). Closed
 *  paths distribute N intervals around the loop (without duplicating the
 *  first point); the circular start-point freedom is resolved by the plan's
 *  circular correspondence. */
export declare function resamplePath(path: CubicPath, N?: number, cornerThreshold?: number): Float64Array;
/** Full input pipeline: icon → cubics → sampled subpaths with their
 *  topology (the plan needs to know which subpaths are closed loops). */
export declare function resampleIcon(input: IconInput, N?: number): Sampled[];
//#endregion
//#region src/core/serialize.d.ts
/** Sampled subpaths → polyline `d` attribute. `closed[k]` appends Z to
 *  subpath k (closed loops in flight); without flags everything is open. */
export declare function serialize(subs: readonly Float64Array[], closed?: readonly boolean[]): string;
/** Cubic subpaths → canonical `d`, quantized to 4 decimals (engine-stable
 *  bytes; see fmtCanon). */
export declare function cubicsToPathD(paths: readonly CubicPath[]): string;
//#endregion
export { type CubicPath, type IconInput, type IconNode, type IconNodeAttrs, type MorphPlan, type PlanItem, SPRING_PRESETS, type Sampled, Spring, type SpringPreset, type ViewBox, buildPlan };