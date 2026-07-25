import type { Tone } from "@/lib/types";
import { toneClasses } from "@/lib/tone";

export function Dot({ tone }: { tone: Tone }) {
  return <span className={`inline-block h-2 w-2 rounded-full ${toneClasses[tone].dot}`} />;
}
