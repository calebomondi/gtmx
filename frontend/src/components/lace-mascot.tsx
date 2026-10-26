/**
 * Lace: the Thalace agent mascot.
 *
 * An orange square with two black square eyes and a small orange glint in each.
 * All motion lives inside the square. No dependencies, no hooks, so it works in
 * server and client components alike.
 *
 * Usage:
 *   <Lace state="thinking" size={48} />
 *   <Lace state="sleepy" size={32} phase={3} />   // start 3s into the loop
 *   <Lace state="idle" look={{ x: 6, y: -3 }} />   // eyes turned up and right
 *
 * States:
 *   sleepy    heavy lids, slow drift          (queued, low priority)
 *   idle      calm blinks                     (ready)
 *   thinking  looks up, squints while glints circle, then an "aha" pop (working)
 *   alert     bigger eyes, quick glances      (needs attention, just triggered)
 *
 * Below 24px the face is simplified (larger eyes, no glints, no corner radius)
 * so it stays legible as a favicon or tiny status icon.
 */
import type { CSSProperties, ReactElement, SVGAttributes } from "react";

export type LaceState = "sleepy" | "idle" | "thinking" | "alert";

const LACE_COLORS = { body: "#FEA853", eye: "#1F1F1F" } as const;

export interface LaceProps
  extends Omit<SVGAttributes<SVGSVGElement>, "width" | "height" | "viewBox" | "children"> {
  state?: LaceState;
  /** Rendered width and height in px. */
  size?: number;
  /** Seconds into the loop to start at, so several Laces don't move in unison. */
  phase?: number;
  /** Set false for a still face. Reduced-motion preferences are always respected. */
  animated?: boolean;
  /** Where the eyes look, as an offset in viewBox units (about ±8 reads
   * well). While set, the state's own glancing around stops; blinks go on. */
  look?: { x: number; y: number } | null;
  /** Accessible name. Defaults to "Lace, <state>". */
  title?: string;
  /** Hide from assistive tech when the state is already shown in text nearby. */
  decorative?: boolean;
}

interface Geometry {
  lx: number;
  rx: number;
  y: number;
  s: number;
  r: number;
  glint: number;
  g0: number;
}

function geometry(state: LaceState, compact: boolean): Geometry {
  if (compact) {
    const alert = state === "alert";
    return { lx: alert ? 16 : 18, rx: alert ? 80 : 82, y: alert ? 34 : 38, s: alert ? 44 : 40, r: 0, glint: 0, g0: 0 };
  }
  if (state === "alert") return { lx: 20, rx: 82, y: 38, s: 38, r: 4, glint: 8, g0: 6 };
  return { lx: 24, rx: 84, y: 42, s: 32, r: 3.5, glint: 7, g0: 5 };
}

function Eye({ x, g, className, glintClassName }: { x: number; g: Geometry; className: string; glintClassName?: string }) {
  return (
    <g className={className}>
      <rect x={x} y={g.y} width={g.s} height={g.s} rx={g.r} fill={LACE_COLORS.eye} />
      {g.glint > 0 && (
        <rect className={glintClassName} x={x + g.g0} y={g.y + g.g0} width={g.glint} height={g.glint} rx={1.5} fill={LACE_COLORS.body} />
      )}
    </g>
  );
}

const D = "var(--lace-phase,0s)";

const LACE_CSS = `
.lace-fb{transform-box:fill-box;transform-origin:center}
.lace-blink{animation:lace-blink 4.6s ease-in-out ${D} infinite}
.lace-blink-rare{animation-duration:5.6s}
.lace-sleepy-look{animation:lace-sleepy-look 16s ease-in-out ${D} infinite}
.lace-sleepy-eye{transform-origin:center bottom;transform:scaleY(.6);animation:lace-sleepy-eye 11s ease-in-out ${D} infinite}
.lace-think-look{animation:lace-think-look 7s ease-in-out ${D} infinite}
.lace-think-eye{animation:lace-think-eye 7s ease-in-out ${D} infinite}
.lace-think-glint{animation:lace-think-glint 7s linear ${D} infinite}
.lace-alert-look{animation:lace-alert-look 2.8s cubic-bezier(.3,.8,.3,1) ${D} infinite}
@keyframes lace-blink{0%,90%{transform:scaleY(1)}93%{transform:scaleY(.08)}96%,100%{transform:scaleY(1)}}
@keyframes lace-sleepy-look{0%,12%{transform:translate(0,2px)}22%,34%{transform:translate(-5px,4px)}48%,58%{transform:translate(0,6px)}74%,86%{transform:translate(5px,3px)}100%{transform:translate(0,2px)}}
@keyframes lace-sleepy-eye{0%,38%{transform:scaleY(.6)}43%,50%{transform:scaleY(.12)}56%{transform:scaleY(.7)}60%,72%{transform:scaleY(.6)}76%{transform:scaleY(.06)}82%,100%{transform:scaleY(.6)}}
@keyframes lace-think-look{0%,8%{transform:translate(0,0)}18%,50%{transform:translate(9px,-8px)}58%,100%{transform:translate(0,0)}}
@keyframes lace-think-eye{0%,16%{transform:scale(1)}24%,50%{transform:scaleY(.78)}56%{transform:scale(1.08,1.18)}62%,100%{transform:scale(1)}}
@keyframes lace-think-glint{0%,24%{transform:translate(0,0)}30.5%{transform:translate(16px,0)}37%{transform:translate(16px,16px)}43.5%{transform:translate(0,16px)}50%,100%{transform:translate(0,0)}}
@keyframes lace-alert-look{0%,8%{transform:translate(0,0)}12%,26%{transform:translate(-10px,-2px)}30%,44%{transform:translate(10px,-2px)}48%,62%{transform:translate(0,-8px)}66%,80%{transform:translate(8px,3px)}84%,100%{transform:translate(0,0)}}
.lace-gaze{transition:transform .12s ease-out}
.lace-looking .lace-sleepy-look,.lace-looking .lace-think-look,.lace-looking .lace-alert-look{animation:none}
.lace-static *{animation:none!important}
@media (prefers-reduced-motion:reduce){.lace *{animation:none!important}}
`;

export function Lace({
  state = "idle",
  size = 48,
  phase = 0,
  animated = true,
  look = null,
  title,
  decorative = false,
  className,
  style,
  ...rest
}: LaceProps) {
  const g = geometry(state, size < 24);

  const eyes = (cls: string, glintCls?: string) => (
    <>
      <Eye x={g.lx} g={g} className={cls} glintClassName={glintCls} />
      <Eye x={g.rx} g={g} className={cls} glintClassName={glintCls} />
    </>
  );

  let face: ReactElement;
  switch (state) {
    case "sleepy":
      face = <g className="lace-sleepy-look">{eyes("lace-fb lace-sleepy-eye")}</g>;
      break;
    case "thinking":
      face = <g className="lace-think-look">{eyes("lace-fb lace-think-eye", "lace-think-glint")}</g>;
      break;
    case "alert":
      face = <g className="lace-alert-look">{eyes("lace-fb lace-blink lace-blink-rare")}</g>;
      break;
    default:
      face = eyes("lace-fb lace-blink");
  }

  return (
    <svg
      {...rest}
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 140 140"
      width={size}
      height={size}
      className={["lace", animated ? "" : "lace-static", look ? "lace-looking" : "", className].filter(Boolean).join(" ")}
      style={{ "--lace-phase": `-${phase}s`, ...style } as CSSProperties}
      role={decorative ? undefined : "img"}
      aria-hidden={decorative || undefined}
    >
      {!decorative && <title>{title ?? `Lace, ${state}`}</title>}
      <style>{LACE_CSS}</style>
      <rect width="140" height="140" rx="9" fill={LACE_COLORS.body} />
      <g className="lace-gaze" style={look ? { transform: `translate(${look.x}px,${look.y}px)` } : undefined}>
        {face}
      </g>
    </svg>
  );
}

export default Lace;
