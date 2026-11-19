// The deck remains available when the approved Power BI rows still need synchronization.
export function PublicationSync({ status }: { status?: string }) {
  if (status === "synced" || status === "not_required") return null;
  const message =
    status === "pending"
      ? "The approved deck is saved. Power BI synchronization is pending; its approved-pack page may still show an earlier version. Ask the project owner to retry synchronization."
      : status === "superseded"
        ? "A newer pack has been published for this week. This download is the earlier approved version."
        : "This saved pack has no verified synchronization record. Check Power BI before assuming its approved-pack page matches this deck.";
  return (
    <p
      role="status"
      className="rounded-lg border border-waiting/40 bg-waiting-wash px-4 py-3 text-sm text-waiting-ink"
    >
      {message}
    </p>
  );
}
