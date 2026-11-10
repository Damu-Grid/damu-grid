import { MoveQueue } from "@/components/move-queue";

export default function DispatchPage() {
  return (
    <MoveQueue
      action="dispatch"
      title="Dispatch"
      intro="Reserved moves waiting for the sending officer. Recheck the physical units before you dispatch."
    />
  );
}
