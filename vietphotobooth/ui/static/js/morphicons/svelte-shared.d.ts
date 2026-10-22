import { a as IconInput, c as Sampled, o as IconNode } from "./plan-DhaDhEVq.js";
import { r as SpringPreset } from "./spring-BgZHrI2W.js";
import { a as ReducedMotionMode, i as PathEl, n as Morph, r as MorphOptions } from "./index-DpvKR75N.js";
import { i as createController, n as computeInitialD, r as computeInitialPaint, t as MorphHandle } from "./controller-DKm8s2ni.js";
import { SVGAttributes } from "svelte/elements";
//#region src/svelte/shared.d.ts
/** Rest props fall through to the `<svg>` fully typed (class, style, data-*,
 *  events, ARIA…) via svelte/elements, like lucide-svelte — typos in an SVG
 *  attr fail the build. `from`/`to` are omitted because the SMIL animation
 *  attributes of the same name collide with the controlled-mode pair. */
export interface MorphIconProps extends Omit<SVGAttributes<SVGSVGElement>, "from" | "to"> {
  /** Uncontrolled mode: the current icon; changing the prop animates. */
  icon?: IconInput;
  /** Controlled mode: source endpoint of the pair. */
  from?: IconInput;
  /** Controlled mode: target endpoint of the pair. */
  to?: IconInput;
  /** Controlled mode: 0..1 progress of the frozen morph (no spring). */
  progress?: number;
  /** Physics for uncontrolled/imperative mode: preset or custom spring. */
  spring?: SpringPreset | MorphOptions;
  /** Reduced-motion policy: "never" (default) animates regardless of the OS
   *  setting, "user" honors prefers-reduced-motion (morphs degrade to an
   *  instant swap while it is on), "always" always jumps. */
  reducedMotion?: ReducedMotionMode;
  size?: number | string;
  color?: string;
  strokeWidth?: number | string;
  /** Like lucide-svelte: stroke width does not scale with `size`. */
  absoluteStrokeWidth?: boolean;
  /** Accessibility: with label → role="img" + <title>; without → aria-hidden. */
  label?: string;
}
//#endregion
export { type IconInput, type IconNode, type Morph, type MorphHandle, type MorphOptions, type PathEl, type ReducedMotionMode, type Sampled, type SpringPreset, computeInitialD, computeInitialPaint, createController };