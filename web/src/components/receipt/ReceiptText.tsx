// Model text with its numbers as chips. Plain text only: model text is never parsed as HTML (plan §4.5).
// The block around it carries dir="auto" (an inner dir would hide the text from the block's direction check).
import { toSegments, type NumberSpan } from "@/lib/receipts";
import { NumberChip } from "./NumberChip";

export function ReceiptText({ text, numbers }: { text: string; numbers: readonly NumberSpan[] }) {
  return (
    <>
      {toSegments(text, numbers).map((seg, i) =>
        seg.kind === "text" ? <span key={i}>{seg.text}</span> : <NumberChip key={i} span={seg.span} />,
      )}
    </>
  );
}
