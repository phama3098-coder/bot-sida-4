import { a as IconInput } from "./plan-DhaDhEVq.js";
import { r as SpringPreset } from "./spring-BgZHrI2W.js";
import { a as ReducedMotionMode, i as PathEl, r as MorphOptions } from "./index-DpvKR75N.js";
//#region src/dom/controller.d.ts
/** Imperative surface exposed by every binding (ref / bind:this / element). */
interface MorphHandle {
  morphTo(icon: IconInput, spring?: SpringPreset | MorphOptions): void;
  set(icon: IconInput): void;
}
/** The mode-deciding props, shared by every binding's prop surface. */
interface MorphModeProps {
  icon?: IconInput;
  from?: IconInput;
  to?: IconInput;
  progress?: number;
}
interface MorphCtrlProps extends MorphModeProps {
  reducedMotion?: ReducedMotionMode;
  /** The stroke width on the 24 grid (absoluteStrokeWidth already resolved):
   *  what a stroke icon is outlined at when it morphs with a fill icon. */
  strokeWidth?: number | string;
}
interface MorphWatchProps extends MorphCtrlProps {
  spring?: SpringPreset | MorphOptions;
}
/** The initial d is a constant for every binding: computed once from the
 *  mount-time props (server and client produce the same string → hydration
 *  without mismatch) and from then on only the driver mutates it outside the
 *  template. */
declare function computeInitialD({ icon, from, to, progress }: MorphModeProps): string;
/** Paint attributes of the initial `<path>` (SSR included), a constant like
 *  the initial d: a fill icon is filled before any script runs. A frozen
 *  stroke pair paints as the endpoint it is nearer to; one with a fill
 *  endpoint rests on `from` mid-way, like its d (frozenEnd). */
declare function computeInitialPaint({ icon, from, to, progress }: MorphModeProps): Record<string, string> | undefined;
/** Per-instance driver state — the exact logic of the React/Vue bindings
 *  (mount, mode watch, controlled seek with re-basing, imperative). Takes the
 *  init-time props: they seed the watch baselines so a watcher that fires on
 *  mount (Svelte's $effect, unlike Vue's watch) is a no-op. All change
 *  detection lives HERE, under tsc — the shells only wire their reactive
 *  surface to these methods.
 *
 *  Lifecycle contract (shared verbatim by the bindings):
 *  - Lazy driver: an iconless mount keeps the element and births the driver
 *    on the FIRST icon that shows up (prop or imperative). `morphTo` with no
 *    driver behaves as `set` — there is nothing to fly from.
 *  - Controlled wins: while `from` and `to` are both present the pair owns
 *    the path and `icon` changes are ignored; dropping the pair hands the
 *    path back to `icon`.
 *  - Every exit from controlled mode (imperative call or icon takeover)
 *    invalidates the frozen pair, so returning to it re-bases on `from`. */
declare function createController({ icon, from, to, progress, reducedMotion, strokeWidth }: MorphCtrlProps): {
  mount(mountEl: PathEl, { icon, from, to, progress, reducedMotion, strokeWidth }: MorphCtrlProps): void;
  destroy(): void;
  /** Prop watcher: ONE owner decides per run — the controlled pair while it
   *  is fully present, `icon` otherwise (mount doesn't fire thanks to the
   *  init-time baselines). */
  watch({ icon, from, to, progress, spring, reducedMotion, strokeWidth }: MorphWatchProps): void;
  morphTo(icon: IconInput, spring?: SpringPreset | MorphOptions): void;
  set(icon: IconInput): void;
};
//#endregion
export { createController as i, computeInitialD as n, computeInitialPaint as r, MorphHandle as t };