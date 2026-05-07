export interface Scenario {
  user: string;
  reply: string; // assistant reply, sentences end with `.` `?` or `!`
}

export const SCENARIOS: Scenario[] = [
  {
    user: "Brief me on today.",
    reply:
      "Two interviews on your calendar. The playtesting deck is ready for review. Three slides flagged for your attention. Otherwise, your morning is clear.",
  },
  {
    user: "Summarize yesterday's research notes.",
    reply:
      "Eight key insights synthesized. The strongest pattern: testers consistently abandon at the second tutorial gate. I drafted a one-paragraph summary in your inbox.",
  },
  {
    user: "What's the status of the playtest review?",
    reply:
      "Slides ready. Three need your review before sending. The remaining content is approved by Harsh.",
  },
  {
    user: "Cancel my eleven o'clock.",
    reply: "Done. Apologies sent. Calendar slot reopened. Your morning is now fully clear.",
  },
  {
    user: "Anything urgent in my inbox?",
    reply:
      "One. The grant deadline moved up by a week. I drafted a response asking for clarification. Want me to send it?",
  },
];

export function pickScenario(): Scenario {
  return SCENARIOS[Math.floor(Math.random() * SCENARIOS.length)]!;
}

export function splitSentences(text: string): string[] {
  return text.match(/[^.!?]+[.!?]+\s*/g)?.map((s) => s.trim()).filter(Boolean) ?? [text];
}
