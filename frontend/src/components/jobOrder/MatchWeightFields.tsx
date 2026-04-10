import type { TFunction } from "i18next";

export type MatchWeightConfig = {
  weight_proximity: number;
  weight_rating: number;
  weight_job_type: number;
  weight_completion: number;
  weight_tier: number;
};

export const DEFAULT_MATCH_WEIGHTS: MatchWeightConfig = {
  weight_proximity: 0.3,
  weight_rating: 0.25,
  weight_job_type: 0.2,
  weight_completion: 0.15,
  weight_tier: 0.1,
};

const FIELD_META: Array<{ key: keyof MatchWeightConfig; labelKey: string }> = [
  { key: "weight_proximity", labelKey: "job_match_weight_proximity" },
  { key: "weight_rating", labelKey: "job_match_weight_rating" },
  { key: "weight_job_type", labelKey: "job_match_weight_job_type" },
  { key: "weight_completion", labelKey: "job_match_weight_completion" },
  { key: "weight_tier", labelKey: "job_match_weight_tier" },
];

export function normalizeMatchWeights(weights: MatchWeightConfig): MatchWeightConfig {
  const total = Object.values(weights).reduce((sum, value) => sum + Math.max(0, Number(value) || 0), 0);
  if (total <= 0) return DEFAULT_MATCH_WEIGHTS;
  return {
    weight_proximity: Math.max(0, Number(weights.weight_proximity) || 0) / total,
    weight_rating: Math.max(0, Number(weights.weight_rating) || 0) / total,
    weight_job_type: Math.max(0, Number(weights.weight_job_type) || 0) / total,
    weight_completion: Math.max(0, Number(weights.weight_completion) || 0) / total,
    weight_tier: Math.max(0, Number(weights.weight_tier) || 0) / total,
  };
}

export function formatMatchWeightPercent(value: number): string {
  return `${Math.round((value || 0) * 100)}%`;
}

export function MatchWeightFields({
  t,
  value,
  onChange,
  disabled = false,
}: {
  t: TFunction;
  value: MatchWeightConfig;
  onChange: (next: MatchWeightConfig) => void;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-3">
      {FIELD_META.map((field) => (
        <label key={field.key} className="block">
          <div className="mb-1 flex items-center justify-between gap-2 text-xs">
            <span className="font-medium text-on-surface">{t(field.labelKey)}</span>
            <span className="text-on-surface-variant">{formatMatchWeightPercent(value[field.key])}</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="1"
            value={Math.round((value[field.key] || 0) * 100)}
            disabled={disabled}
            onChange={(e) => {
              const next = normalizeMatchWeights({
                ...value,
                [field.key]: Number(e.target.value) / 100,
              });
              onChange(next);
            }}
            className="w-full accent-primary"
          />
        </label>
      ))}
    </div>
  );
}
