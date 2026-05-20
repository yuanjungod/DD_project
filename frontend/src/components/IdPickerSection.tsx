import { useMemo, useState } from "react";

export type PickerItem = {
  id: string;
  name: string;
  hint?: string;
  enabled?: boolean;
};

type IdSelectFieldProps = {
  label: string;
  items: PickerItem[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  hint?: string;
};

export function IdSelectField({
  label,
  items,
  value,
  onChange,
  disabled,
  placeholder = "请选择…",
  hint,
}: IdSelectFieldProps) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled}>
        <option value="">{placeholder}</option>
        {items.map((item) => (
          <option key={item.id} value={item.id} disabled={item.enabled === false}>
            {item.name !== item.id ? `${item.name} (${item.id})` : item.id}
          </option>
        ))}
      </select>
      {hint ? (
        <span className="muted" style={{ fontSize: "12px", fontWeight: 500 }}>
          {hint}
        </span>
      ) : null}
    </label>
  );
}

type IdMultiPickerSectionProps = {
  title: string;
  description?: string;
  items: PickerItem[];
  selected: string[];
  onChange: (selected: string[]) => void;
  disabled?: boolean;
  emptyText?: string;
  compact?: boolean;
};

export function togglePickerId(selected: string[], id: string): string[] {
  return selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id];
}

export function IdMultiPickerSection({
  title,
  description,
  items,
  selected,
  onChange,
  disabled,
  emptyText = "暂无可选项",
  compact,
}: IdMultiPickerSectionProps) {
  const [filter, setFilter] = useState("");
  const selectedSet = useMemo(() => new Set(selected), [selected]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (item) =>
        item.id.toLowerCase().includes(q) ||
        item.name.toLowerCase().includes(q) ||
        (item.hint ?? "").toLowerCase().includes(q),
    );
  }, [filter, items]);

  return (
    <section
      className={`agent-binding-section${compact ? " agent-binding-section--compact" : ""}`}
      aria-label={title}
    >
      <div className="agent-binding-section__head">
        <h3 className="agent-binding-section__title">
          {title}
          <span className="agent-selected-count">{selected.length} 项已选</span>
        </h3>
        {description ? <p className="agent-binding-section__desc">{description}</p> : null}
      </div>
      <input
        type="search"
        className="agent-binding-filter"
        placeholder="输入关键字筛选…"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
        disabled={disabled}
        aria-label={`${title} 筛选`}
      />
      <div className="agent-option-grid">
        {filtered.length === 0 ? (
          <p className="agent-binding-empty">{emptyText}</p>
        ) : (
          filtered.map((item) => {
            const checked = selectedSet.has(item.id);
            const itemDisabled = disabled || item.enabled === false;
            return (
              <label
                key={item.id}
                className={`agent-option-tile ${checked ? "is-selected" : ""} ${itemDisabled && !checked ? "is-disabled" : ""}`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={itemDisabled}
                  onChange={() => {
                    if (!itemDisabled) {
                      onChange(togglePickerId(selected, item.id));
                    }
                  }}
                />
                <div className="agent-option-tile__body">
                  <span className="agent-option-tile__title">{item.name}</span>
                  {item.hint ? <span className="agent-option-tile__sub">{item.hint}</span> : null}
                  <code>{item.id}</code>
                </div>
              </label>
            );
          })
        )}
      </div>
    </section>
  );
}
