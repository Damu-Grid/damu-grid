import { MoveQueue } from "@/components/move-queue";

export default function ReceivePage() {
  return (
    <MoveQueue
      action="receive"
      title="Receive"
      intro={
        <>
          Moves on their way to you. Confirm arrival and cool-box evidence.{" "}
          <strong>Receipt is not a release for transfusion.</strong>
        </>
      }
    />
  );
}
