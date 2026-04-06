import { useId, useMemo, useState } from "react";
import type { TFunction } from "i18next";
import { SKILLS, canonicalizeSkill } from "../../constants/skills";

type Props = {
  t: TFunction;
  selected: string[];
  onChange: (next: string[]) => void;
  inputClassName: string;
  addButtonClassName: string;
  chipButtonClassName: string;
  /** When set (e.g. job required skills), those options are emphasized in the picker. */
  jobRequiredLabels?: readonly string[];
};

export function SkillMultiPicker({
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
    const list = SKILLS.filter((s) => !selected.includes(s) && (!q || s.toLowerCase().includes(q)));
    if (!jobReq.size) return list;
    return [...list].sort((a, b) => Number(jobReq.has(b)) - Number(jobReq.has(a)));
  }, [query, selected, jobReq]);

  function addSkill(raw: string) {
    const canonical = canonicalizeSkill(raw);
    if (!canonical || selected.includes(canonical)) return;
    onChange([...selected, canonical]);
    setQuery("");
  }

  function remove(i: number) {
    onChange(selected.filter((_, idx) => idx !== i));
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          className={inputClassName}
          value={query}
          list={`mci-skills-list-${listId}`}
          placeholder={t("skills_pick_placeholder")}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addSkill(query);
            }
          }}
        />
        <button type="button" className={addButtonClassName} onClick={() => addSkill(query)}>
          {t("job_form_add")}
        </button>
      </div>
      <datalist id={`mci-skills-list-${listId}`}>
        {filtered.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>
      {filtered.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {filtered.slice(0, 8).map((s) => (
            <button
              key={s}
              type="button"
              className={`${chipButtonClassName} opacity-90 ${jobReq.has(s) ? "ring-1 ring-amber-500/80 bg-amber-500/10" : ""}`}
              title={jobReq.has(s) ? String(t("job_detail_filter_job_required_hint")) : undefined}
              onClick={() => addSkill(s)}
            >
              + {s}
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-1">
        {selected.map((s, i) => (
          <button
            key={`${s}-${i}`}
            type="button"
            className={`${chipButtonClassName} ring-2 font-semibold ${
              jobReq.has(s) ? "ring-emerald-600/70 bg-emerald-500/15" : "ring-primary/55 bg-primary/15"
            }`}
            title={jobReq.has(s) ? String(t("job_detail_filter_matches_job_requirement")) : undefined}
            onClick={() => remove(i)}
          >
            {s} x
          </button>
        ))}
      </div>
    </div>
  );
}
