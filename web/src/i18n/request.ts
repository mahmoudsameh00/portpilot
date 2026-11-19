import { getRequestConfig } from "next-intl/server";

// The interface is English only (owner 2026-11-06, D-FE-6): next-intl without i18n routing keeps every UI string in
// messages/en.json. Answers follow the language of the question and are rendered with dir="auto".
export default getRequestConfig(async () => ({
  locale: "en",
  messages: (await import("../../messages/en.json")).default,
  timeZone: "Africa/Cairo",
}));
