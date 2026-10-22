import { n as index_d_exports } from "./index-DDNCPQ4Z.js";
import { a as IconInput } from "./plan-DhaDhEVq.js";
import { r as SpringPreset } from "./spring-BgZHrI2W.js";
//#region src/dom/index.d.ts
/** Target element, structurally typed: any object with setAttribute works
 *  (a real SVGPathElement, or a fake in tests). */
interface PathEl {
  setAttribute(name: string, value: string): void;
}
/** Morph physics: named preset or custom spring. */
interface MorphOptions {
  stiffness?: number;
  damping?: number;
}
/** Reduced-motion policy. `"never"` (default): morphs always animate,
 *  ignoring the OS setting. `"user"`: while the OS reduce-motion setting is
 *  on, `morphTo` degrades to an instant `set`. `"always"`: every `morphTo`
 *  jumps (tests, screenshots). */
type ReducedMotionMode = "never" | "user" | "always";
interface CreateMorphOptions {
  /** Reduced-motion policy; also live via the `reducedMotion` property. */
  reducedMotion?: ReducedMotionMode;
  /** Stroke width the element draws with (24-unit grid). Only used to
   *  outline stroke icons when they morph with a fill icon, so the region
   *  in flight matches the stroke at rest. Default 2; live via the
   *  `strokeWidth` property. */
  strokeWidth?: number;
}
interface Morph {
  /** Animates toward the icon with spring physics. Interruptible: mid-flight
   *  it re-plans from the intermediate shape while preserving velocity. */
  morphTo(icon: IconInput, spring?: SpringPreset | MorphOptions): void;
  /** Jumps to the icon without animating (canonical d, no frames). */
  set(icon: IconInput): void;
  /** Renders the morph toward `icon` frozen at t (no spring) — the
   *  controlled-mode primitive: scrubbing, gestures, scroll. A later
   *  morphTo takes off from that intermediate shape. */
  seek(icon: IconInput, t: number): void;
  /** Current progress (t of the last frame; 1 at rest). Assigning it is
   *  equivalent to seek(target, t) on the active target. */
  progress: number;
  /** Reduced-motion policy, live: assigning it applies to the next morphTo. */
  reducedMotion: ReducedMotionMode;
  /** Stroke width used to outline stroke icons in stroke↔fill morphs. */
  strokeWidth: number;
  /** Unregisters the instance; later calls are no-ops. */
  destroy(): void;
}
/** Canonical `d` of an icon: the input string verbatim, or the real cubics
 *  quantized to 4 decimals (the at-rest snap; engine-stable bytes so SSR
 *  hydration matches, see fmtCanon in core/serialize). Exported because it
 *  is what a binding renders at SSR/rest before any runtime exists. A fill
 *  icon's translucent duotone layer is left out (one path can't paint it). */
declare function canonicalD(icon: IconInput): string;
type RegionModule = typeof index_d_exports;
/** Replaces how the region normalizer is loaded (default: dynamic import of
 *  the bundled chunk). E.g. `setRegionLoader(async () => region)` after a
 *  static `import * as region from "morphicons/region"` to never touch the
 *  network mid-interaction. The next need loads through the new loader. */
declare function setRegionLoader(loader: () => Promise<RegionModule>): void;
/** Starts (or joins) loading the region normalizer. Call it early — on
 *  idle, on hover — to keep the first stroke↔fill morph off the network. */
declare function preloadRegion(): Promise<RegionModule>;
/** The paint attributes a binding renders on the `<path>` with its first
 *  icon (SSR included), so a fill icon is filled before any script runs.
 *  None for a stroke icon: it inherits the `<svg>`'s stroke as always. */
declare function restAttrs(icon?: IconInput): Record<string, string> | undefined;
/** Creates the morph instance over a `<path>` and paints the initial icon. */
declare function createMorph(el: PathEl, icon: IconInput, options?: CreateMorphOptions): Morph;
//#endregion
export { ReducedMotionMode as a, preloadRegion as c, PathEl as i, restAttrs as l, Morph as n, canonicalD as o, MorphOptions as r, createMorph as s, CreateMorphOptions as t, setRegionLoader as u };