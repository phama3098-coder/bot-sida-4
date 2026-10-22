//#region src/core/types.d.ts
/** Attributes of an icon node (values as Lucide exports them: string or
 *  number). `undefined` is allowed on purpose — lucide's SVGProps includes it
 *  and the runtime treats an undefined attr as absent (fallback). */
type IconNodeAttrs = Record<string, string | number | undefined>;
/** Lucide-style icon data: a `[tag, attrs]` list. Structurally typed —
 *  Lucide is neither a dependency nor a peer; Feather/Tabler/custom paths
 *  work just the same. */
type IconNode = ReadonlyArray<readonly [string, IconNodeAttrs]>;
/** Input accepted by the core: an IconNode or a raw `d` attribute.
 *  (SVGElement is resolved in the dom layer — the core never touches DOM.) */
type IconInput = IconNode | string;
/** Normalized subpath: a chain of cubics packed as points
 *  [p0, c1, c2, p1, c1', c2', p2, …] → Float64Array of length 2·(3m+1),
 *  with m = number of segments. Consecutive segments share an endpoint. */
interface CubicPath {
  pts: Float64Array;
  closed: boolean;
}
/** Subpath sampled at N points by arc length + its topology. It is the
 *  currency between resample and plan; an intermediate shape (interruption)
 *  is also a list of Sampled. */
interface Sampled {
  pts: Float64Array;
  closed: boolean;
  /** Region contours only: true for a hole (negative winding). Carried
   *  explicitly because a hole collapsing mid-flight has ~zero area and
   *  could not be re-classified from its points. */
  hole?: boolean;
}
//#endregion
//#region src/core/plan.d.ts
interface PlanItem {
  /** Points of A with the chosen correspondence (if A is a closed loop it
   *  may come circularly re-indexed: same points, different cut). */
  a: Float64Array;
  /** A centered on its centroid. */
  aC: Float64Array;
  /** B brought into A's frame: R(−θ)·(b − c_B)/σ. */
  bT: Float64Array;
  /** B oriented, raw (for linear mode and for exact t=1). */
  bO: Float64Array;
  ca: readonly [number, number];
  cb: readonly [number, number];
  theta: number;
  lnSigma: number;
  res: number;
  /** true if both endpoints are closed loops: the subpath flies with Z.
   *  Closed → open flies open: the loop opens at the chosen cut. */
  closed: boolean;
  /** Region plans only: the item is a hole (negative winding). Collapsing
   *  and growing holes are items too — their far endpoint is one point. */
  hole?: boolean;
  /** Region plans only: a hole that vanishes or appears blends its shape on
   *  one half of the flight (0 = collapses on [0, ½], 1 = grows on [½, 1])
   *  while it keeps riding its outer the whole way. */
  half?: 0 | 1;
  /** Block transport (set by the global hybrid, else null): mid-flight the
   *  centroid rides the shared similarity around the global centroid instead
   *  of lerping — off = c_A − g_A; drift closes c(1) = c_B exactly. */
  block: {
    off: readonly [number, number];
    drift: readonly [number, number];
  } | null;
}
interface MorphPlan {
  items: PlanItem[];
  n: number;
}
/** Builds the morph plan between two lists of sampled subpaths. The plan is
 *  cacheable and serializable; it accepts any list — including intermediate
 *  shapes (interruptions). Filled regions use buildRegionPlan (lazy chunk,
 *  src/region/plan.ts) instead. */
declare function buildPlan(srcSubs: readonly Sampled[], dstSubs: readonly Sampled[]): MorphPlan;
//#endregion
export { IconInput as a, Sampled as c, CubicPath as i, PlanItem as n, IconNode as o, buildPlan as r, IconNodeAttrs as s, MorphPlan as t };