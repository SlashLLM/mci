import { useState } from "react";
import type { TFunction } from "i18next";
import { JOB_TYPES } from "../../constants/jobTypes";

type Props = {
  t: TFunction;
  selected: string[];
  onChange: (next: string[]) => void;
  selectClassName: string;
  addButtonClassName: string;
  chipButtonClassName: string;
};

export function JobTypeMultiPicker({
  t,
  selected,
  onChange,
  selectClassName,
  addButtonClassName,
  chipButtonClassName,
}: Props) {
  const [pick, setPick] = useState("");
  const available = JOB_TYPES.filter((j) => !selected.includes(j));

  function add() {
    if (!pick || selected.includes(pick)) return;
    onChange([...selected, pick]);
    setPick("");
  }

  function remove(i: number) {
    onChange(selected.filter((_, j) => j !== i));
  }

  return (
    <div className="w-full space-y-2">
      <div className="flex w-full gap-2">
        <select className={selectClassName} value={pick} onChange={(e) => setPick(e.target.value)}>
          <option value="">{t("job_type_pick_placeholder")}</option>
          {available.map((j) => (
            <option key={j} value={j}>
              {j}
            </option>
          ))}
        </select>
        <button type="button" className={addButtonClassName} onClick={add} disabled={!pick}>
          +
        </button>
      </div>
      <div className="flex flex-wrap gap-1">
        {selected.map((j, i) => (
          <button key={`${j}-${i}`} type="button" className={chipButtonClassName} onClick={() => remove(i)}>
            {j} ×
          </button>
        ))}
      </div>
    </div>
  );
}
