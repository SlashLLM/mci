import { useId, useMemo, useState } from "react";
import type { TFunction } from "i18next";
import { CERTIFICATIONS, canonicalizeCertification } from "../../constants/certifications";

type Props = {
  t: TFunction;
  selected: string[];
  onChange: (next: string[]) => void;
  inputClassName: string;
  addButtonClassName: string;
  chipButtonClassName: string;
  jobRequiredLabels?: readonly string[];
};

export function CertificationMultiPicker({
  t,
  selected,
  onChange,
  inputClassName,
  addButtonClassName,
  chipButtonClassName,
  jobRequiredLabels,
}: Props) {
  const [query, setQuery] = useState("");
  const listId = useId().replace(/:/g, "_");

  const jobReq = useMemo(() => new Set(jobRequiredLabels || []), [jobRequiredLabels]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = CERTIFICATIONS.filter((c) => !selected.includes(c) && (!q || c.toLowerCase().includes(q)));
    if (!jobReq.size) return list;
    return [...list].sort((a, b) => Number(jobReq.has(b)) - Number(jobReq.has(a)));
  }, [query, selected, jobReq]);

  function addCert(raw: string) {
    const canonical = canonicalizeCertification(raw);
    if (!canonical || selected.includes(canonical)) return;
    onChange([...selected, canonical]);
    setQuery("");
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          className={inputClassName}
          value={query}
          list={`mci-certs-list-${listId}`}
          placeholder={t("cert_pick_placeholder")}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addCert(query);
            }
          }}
        />
        <button type="button" className={addButtonClassName} onClick={() => addCert(query)}>
          {t("job_form_add")}
        </button>
      </div>
      <datalist id={`mci-certs-list-${listId}`}>
        {filtered.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
      {filtered.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {filtered.slice(0, 8).map((c) => (
            <button
              key={c}
              type="button"
              className={`${chipButtonClassName} opacity-90 ${jobReq.has(c) ? "ring-1 ring-amber-500/80 bg-amber-500/10" : ""}`}
              title={jobReq.has(c) ? String(t("job_detail_filter_job_required_hint")) : undefined}
              onClick={() => addCert(c)}
            >
              + {c}
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-1">
        {selected.map((c, i) => (
          <button
            key={`${c}-${i}`}
            type="button"
            className={`${chipButtonClassName} ring-2 font-semibold ${
              jobReq.has(c) ? "ring-emerald-600/70 bg-emerald-500/15" : "ring-primary/55 bg-primary/15"
            }`}
            title={jobReq.has(c) ? String(t("job_detail_filter_matches_job_requirement")) : undefined}
            onClick={() => onChange(selected.filter((_, idx) => idx !== i))}
          >
            {c} x
          </button>
        ))}
      </div>
    </div>
  );
}
