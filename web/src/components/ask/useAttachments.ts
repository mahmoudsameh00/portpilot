"use client";
// Documents attached in the composer (D-FE-11): a picked file is uploaded at once — the conversation is opened
// first if this is its first need — and its chip shows the API's verdict before the question is sent. The checks
// here are a comfort only (type, size, count); the API validates, screens and decides (ADR-042 – ADR-044), and a
// refused file shows the API's message, never the document's text.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  listUploadsApiV1ConversationsConversationIdUploadsGet as listUploads,
  removeUploadApiV1ConversationsConversationIdUploadsDocumentIdDelete as removeUpload,
  uploadApiV1ConversationsConversationIdUploadsPost as uploadFile,
} from "@/api/generated/client";
import { BffError } from "@/lib/bff/client";

export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
export const MAX_UPLOADS = 5;
export const UPLOAD_ACCEPT =
  ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
export const UPLOAD_HINT = `PDF or Word, up to 5 MB each, ${MAX_UPLOADS} per conversation. Uploaded text is treated as untrusted and labelled so in answers.`;

export type Attachment = {
  id: string;
  name: string;
  state: "uploading" | "accepted" | "refused";
  /** The API's verdict line (or the comfort check's reason); plain text. */
  message?: string;
  /** Sections the screening removed from an accepted document. */
  removed?: number;
  documentId?: string;
};

/** The comfort check before a file is sent: null = send it, else the reason shown on its chip. */
export function localProblem(file: { name: string; size: number }, used: number): string | null {
  if (!/\.(pdf|docx)$/i.test(file.name)) return "Only PDF or Word (.docx) files can be attached.";
  if (file.size > MAX_UPLOAD_BYTES) return "This file is larger than 5 MB.";
  if (used >= MAX_UPLOADS) return `A conversation holds at most ${MAX_UPLOADS} documents.`;
  return null;
}

function refusal(error: unknown): string {
  if (error instanceof BffError) {
    if (error.status === 409) return "This conversation is busy. Attach the document again in a moment.";
    const upload = error.problem["upload"];
    const message =
      upload !== null && typeof upload === "object" ? (upload as Record<string, unknown>)["message"] : null;
    return typeof message === "string" && message ? message : error.title;
  }
  return "The upload failed. Try again.";
}

export function useAttachments(conversationId: string | null, ensureConversation: () => Promise<string>) {
  const qc = useQueryClient();
  const [items, setItems] = useState<Attachment[]>([]);
  const itemsRef = useRef<Attachment[]>([]);
  useEffect(() => {
    itemsRef.current = items;
  }, [items]);
  const queue = useRef<Promise<void>>(Promise.resolve());
  const listed = useQuery({
    queryKey: ["uploads", conversationId],
    queryFn: () => listUploads(conversationId as string),
    enabled: conversationId !== null,
  });
  const listedIds = (listed.data ?? []).map((d) => d.document_id);
  const listedRef = useRef<string[]>([]);
  useEffect(() => {
    listedRef.current = listedIds;
  });

  const patch = useCallback(
    (id: string, change: Partial<Attachment>) =>
      setItems((all) => all.map((a) => (a.id === id ? { ...a, ...change } : a))),
    [],
  );

  const add = useCallback(
    (files: File[]) => {
      // documents already in the conversation + those on their way (an accepted chip may not be listed yet)
      let used =
        listedRef.current.length +
        itemsRef.current.filter(
          (a) =>
            a.state === "uploading" ||
            (a.state === "accepted" && !listedRef.current.includes(a.documentId ?? "")),
        ).length;
      const fresh: Attachment[] = [];
      for (const file of files) {
        const id = crypto.randomUUID();
        const problem = localProblem(file, used);
        if (problem) {
          fresh.push({ id, name: file.name, state: "refused", message: problem });
          continue;
        }
        used += 1;
        fresh.push({ id, name: file.name, state: "uploading" });
        // one after another: the API holds the conversation busy during an upload (a parallel one would get 409)
        queue.current = queue.current.then(async () => {
          try {
            const conversation = await ensureConversation();
            const out = await uploadFile(conversation, { file });
            patch(id, {
              state: "accepted",
              message: out.message,
              removed: out.removed.length,
              documentId: out.document_id ?? undefined,
            });
            void qc.invalidateQueries({ queryKey: ["uploads", conversation] });
          } catch (error) {
            patch(id, { state: "refused", message: refusal(error) });
          }
        });
      }
      setItems((all) => [...all, ...fresh]);
    },
    [ensureConversation, patch, qc],
  );

  /** Takes a chip away; an accepted document also leaves the conversation (the API deletes it). */
  const remove = useCallback(
    async (id: string) => {
      const item = itemsRef.current.find((a) => a.id === id);
      if (!item || item.state === "uploading") return;
      if (item.state === "accepted" && item.documentId) {
        try {
          const conversation = await ensureConversation();
          await removeUpload(conversation, item.documentId);
          void qc.invalidateQueries({ queryKey: ["uploads", conversation] });
        } catch (error) {
          // already gone (404) is the wanted end state; anything else keeps the chip and says why
          if (!(error instanceof BffError && error.status === 404)) {
            patch(id, { message: "This document could not be removed. Try again." });
            return;
          }
        }
      }
      setItems((all) => all.filter((a) => a.id !== id));
    },
    [ensureConversation, patch, qc],
  );

  /** At Send: the accepted documents' names go with the question and the chips leave the composer. */
  const takeSent = useCallback((): string[] => {
    const names = itemsRef.current.filter((a) => a.state === "accepted").map((a) => a.name);
    setItems([]);
    return names;
  }, []);

  return { items, add, remove, takeSent, uploading: items.some((a) => a.state === "uploading") };
}
