import type { CSSProperties, ReactNode } from "react";

export function Card({
  children,
  style,
  className = "",
  onClick,
}: {
  children: ReactNode;
  style?: CSSProperties;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`bg-surface border-[0.5px] border-line rounded-[13px] shadow-[0_1px_2px_rgba(30,28,24,.04)] ${className}`}
      style={style}
    >
      {children}
    </div>
  );
}
