/** Starter prompts shown on an empty conversation. The last one deliberately asks for data the
 * schema does not contain — demonstrating that the assistant refuses rather than fabricates. */
export const SUGGESTIONS = [
  "Who are the most prolific repeat offenders in my jurisdiction?",
  "Show the co-offending network around the top offender.",
  "Where are the crime hotspots?",
  "Which districts are red zones versus their own baseline?",
  "How many Zero FIRs are there and where?",
  "What bank accounts are linked to that person?",
] as const;
