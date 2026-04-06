/** Canonical skills catalogue — keep in sync with backend `app.constants.skills.SKILLS`. */
export const SKILLS = [
  "Web Development",
  "Mobile App Development",
  "Data Analysis",
  "Data Entry",
  "Database Management",
  "Software Development",
  "UI/UX Design",
  "Graphic Design",
  "Video Editing",
  "Digital Marketing",
  "SEO (Search Engine Optimization)",
  "Social Media Management",
  "Content Management Systems (CMS)",
  "Cloud Computing",
  "Cybersecurity",
  "Networking",
  "IT Support",
  "Automation / Scripting",
  "AI / Machine Learning",
  "DevOps",
  "API Integration",
  "Testing / QA",
  "Microsoft Excel",
  "Google Workspace",
  "CRM Software",
  "POS Systems",
  "Communication",
  "Teamwork",
  "Leadership",
  "Time Management",
  "Problem Solving",
  "Critical Thinking",
  "Adaptability",
  "Multitasking",
  "Creativity",
  "Emotional Intelligence",
  "Conflict Resolution",
  "Decision Making",
  "Work Ethic",
  "Reliability",
  "Accountability",
  "Attention to Detail",
  "Customer Service",
  "Interpersonal Skills",
  "Negotiation",
  "Persuasion",
  "Stress Management",
  "Organization",
  "Active Listening",
] as const;

export type SkillId = (typeof SKILLS)[number];

const SKILL_BY_LOWER = new Map<string, SkillId>(SKILLS.map((s) => [s.toLowerCase(), s]));
const SKILL_SET = new Set<string>(SKILLS);

export function isAllowedSkill(value: string): value is SkillId {
  return SKILL_SET.has(value);
}

export function canonicalizeSkill(value: string): SkillId | null {
  return SKILL_BY_LOWER.get((value || "").trim().toLowerCase()) ?? null;
}
