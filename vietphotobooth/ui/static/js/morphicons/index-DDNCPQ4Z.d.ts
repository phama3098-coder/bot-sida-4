import { a as IconInput, c as Sampled, o as IconNode, t as MorphPlan } from "./plan-DhaDhEVq.js";
//#endregion
//#region src/region/plan.d.ts
/** Samples a normalized region: one Sampled per contour, every one closed,
 *  `hole` read from the winding (outers positive, holes negative). N per
 *  contour: 64, or 128 for every contour of an icon that 64 can't follow
 *  (snowflake tips, spiral turns: the landing would snap). */
declare function resampleRegion(icon: IconInput, N?: number): Sampled[];
/** Region plan: outers ↔ outers (holed contours never duplicated), holes ↔
 *  overlapping holes of the paired outer, direction locked; whatever has no
 *  partner collapses/grows without ever breaking the nesting (rules above).
 *  Every item flies closed. */
declare function buildRegionPlan(srcSubs: readonly Sampled[], dstSubs: readonly Sampled[]): MorphPlan;
//#endregion
//#region src/core/region.d.ts
/** How an icon is painted: centerlines with a stroke, or filled surface. */
type Paint = "stroke" | "fill";
/** Paint of an icon. Raw `d` strings and IconNodes that never declare a
 *  painted fill are stroke icons — the historical contract, so every
 *  existing input keeps its meaning. One element with a painted `fill` makes
 *  the whole icon a fill icon (mixed stroke+fill icons need the region path
 *  too: their silhouette is not a set of centerlines). */
declare function paintOf(icon: IconInput): Paint;
/** True when the icon is already a normalized region (no work left). */
declare function isRegion(icon: IconInput): boolean;
declare namespace index_d_exports {
  export { Paint, RegionOptions, buildRegionPlan, isRegion, paintOf, regionContours, regionOf, regionPlan, regionPlanFrom, resampleRegion, toRegion };
}
interface RegionOptions {
  /** Width for stroked elements that don't declare `stroke-width` (Lucide
   *  data carries none: the binding draws it). Default 2. */
  strokeWidth?: number;
  /** Grid step of the distance field, in icon units (24-unit grid).
   *  Default ⅛: corners are rebuilt exactly, curves deviate < 0.01. */
  cell?: number;
}
/** Contours of the visible surface: closed, non-overlapping, outers
 *  positive / holes negative (nesting depth decides which is which). */
declare function regionContours(input: IconInput, options?: RegionOptions): Float64Array[];
/** Any icon → its canonical region: one `<path>` (nonzero) whose contours
 *  are the visible surface. Idempotent on regions. Stroke icons outline at
 *  `strokeWidth` (round caps and joins — Lucide, Tabler, Feather,
 *  Heroicons outline); fill icons honor each element's fill rule. */
declare function toRegion(input: IconInput, options?: RegionOptions): IconNode;
/** The region the driver draws for an icon (cached): a stroke icon
 *  outlined at the element's stroke width, a fill icon as is. */
declare function regionOf(icon: IconInput, strokeWidth: number): IconNode;
/** Region plan from `src` at rest to `dst` (cached by reference). */
declare function regionPlan(src: IconInput, dst: IconInput, strokeWidth: number): MorphPlan;
/** Region plan from the shape in flight to `dst` (never cached): region
 *  samples as they are, or a centerline `d` (a stroke morph interrupted
 *  toward a fill icon), outlined as it is. */
declare function regionPlanFrom(shape: Sampled[] | string, dst: IconInput, strokeWidth: number): MorphPlan;
//#endregion
export { regionPlan as a, Paint as c, buildRegionPlan as d, resampleRegion as f, regionOf as i, isRegion as l, index_d_exports as n, regionPlanFrom as o, regionContours as r, toRegion as s, RegionOptions as t, paintOf as u };