export const CERTIFICATIONS = [
  "AWS Certified Cloud Practitioner",
  "Microsoft Certified: Azure Fundamentals",
  "Google IT Support Professional Certificate",
  "CompTIA A+",
  "CompTIA Network+",
  "CompTIA Security+",
  "Cisco Certified Network Associate (CCNA)",
  "Certified Ethical Hacker (CEH)",
  "Oracle Certified Java Programmer",
  "Microsoft Certified: Power BI Data Analyst",
  "Google Data Analytics Professional Certificate",
  "IBM Data Science Professional Certificate",
  "Certified Kubernetes Administrator (CKA)",
  "Docker Certified Associate",
  "Salesforce Administrator Certification",
  "HubSpot Content Marketing Certification",
  "Google Ads Certification",
  "Meta Social Media Marketing Certification",
  "Adobe Certified Professional (Photoshop / Illustrator)",
  "Project Management Professional (PMP)",
  "Certified Associate in Project Management (CAPM)",
  "Scrum Master Certification (CSM)",
  "Lean Six Sigma Yellow Belt",
  "Lean Six Sigma Green Belt",
  "Digital Marketing Certification",
  "Human Resource Management Certification",
  "Customer Service Certification",
  "Business Communication Certification",
  "Financial Accounting Certification",
  "Bookkeeping Certification",
  "Sales Certification",
  "Leadership & Management Certification",
  "Time Management Certification",
] as const;

export type CertificationId = (typeof CERTIFICATIONS)[number];

const CERT_BY_LOWER = new Map<string, CertificationId>(CERTIFICATIONS.map((c) => [c.toLowerCase(), c]));

export function canonicalizeCertification(value: string): CertificationId | null {
  return CERT_BY_LOWER.get((value || "").trim().toLowerCase()) ?? null;
}
