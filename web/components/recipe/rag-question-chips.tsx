import { RagQueryType } from "@/lib/types";

const CHIP_CONFIG: Array<{ label: string; queryType: RagQueryType }> = [
  { label: "Why is this recipe not working?", queryType: "issue" },
  { label: "How are users fixing it?", queryType: "fix" },
  { label: "What issue appears most often?", queryType: "issue" },
  { label: "What should the editor change first?", queryType: "editorial" },
  { label: "Is the feedback consistent or mixed?", queryType: "mixed" },
];

export function RagQuestionChips({
  activeQueryType,
  disabled,
  onSelect,
}: {
  activeQueryType?: RagQueryType | null;
  disabled?: boolean;
  onSelect: (chip: { label: string; queryType: RagQueryType }) => void;
}) {
  return (
    <div className="rag-chip-row">
      {CHIP_CONFIG.map((chip) => (
        <button
          className={`rag-chip ${activeQueryType === chip.queryType ? "active" : ""}`}
          disabled={disabled}
          key={`${chip.queryType}-${chip.label}`}
          onClick={() => onSelect(chip)}
          type="button"
        >
          {chip.label}
        </button>
      ))}
    </div>
  );
}
