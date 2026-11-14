"use client";
// Pauses SVG animations (animateMotion) for people who ask for reduced motion; CSS animations stop by media query.
import { useEffect, useRef } from "react";

export function MotionGuard({ children, className }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () =>
      ref.current?.querySelectorAll("svg").forEach((svg) => {
        if (media.matches) svg.pauseAnimations();
        else svg.unpauseAnimations();
      });
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);
  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
