import { useEffect, useMemo, useState } from "react";

import {
  PLATFORM_RESOURCE_TYPE_OPTIONS,
  isKnownPlatformResourceType,
  resourceListFilterLabel,
  type ResourceListFilter,
} from "../domain/platformResourceRegistry";

export type PickerItem = {
  id: string;
  name: string;
  hint?: string;
  enabled?: boolean;
  /** Platform resource connector type (web, file_store, …). */
  resourceType?: string;
  /** File picker: 应用文件库 | 平台共享文件库 */
  fileSource?: string;
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

function matchesPickerFilter(item: PickerItem, q: string): boolean {
  if (!q) return true;
  return (
    item.id.toLowerCase().includes(q) ||
    item.name.toLowerCase().includes(q) ||
    (item.hint ?? "").toLowerCase().includes(q) ||
    (item.resourceType ?? "").toLowerCase().includes(q) ||
    (item.fileSource ?? "").toLowerCase().includes(q)
  );
}

function PickerListRows(props: {
  items: PickerItem[];
  selected: string[];
  onChange: (selected: string[]) => void;
  disabled?: boolean;
  emptyText: string;
}) {
  const selectedSet = useMemo(() => new Set(props.selected), [props.selected]);

  if (props.items.length === 0) {
    return <p className="picker-list-empty">{props.emptyText}</p>;
  }

  return (
    <ul className="picker-resource-list" role="list">
      {props.items.map((item) => {
        const checked = selectedSet.has(item.id);
        const itemDisabled = props.disabled || item.enabled === false;
        return (
          <li key={item.id}>
            <label
              className={`picker-resource-row ${checked ? "is-selected" : ""} ${itemDisabled && !checked ? "is-disabled" : ""}`}
            >
              <input
                type="checkbox"
                checked={checked}
                disabled={itemDisabled}
                onChange={() => {
                  if (!itemDisabled) {
                    props.onChange(togglePickerId(props.selected, item.id));
                  }
                }}
              />
              <div className="picker-resource-row__main">
                <span className="picker-resource-row__title">{item.name}</span>
                {item.hint ? <span className="picker-resource-row__sub">{item.hint}</span> : null}
              </div>
              <code className="picker-resource-row__id">{item.id}</code>
            </label>
          </li>
        );
      })}
    </ul>
  );
}

function defaultResourceTypeTab(items: PickerItem[], selected: string[]): ResourceListFilter {
  const selectedSet = new Set(selected);
  for (const item of items) {
    if (selectedSet.has(item.id)) {
      const t = item.resourceType ?? "";
      if (isKnownPlatformResourceType(t)) return t;
      if (t) return "other";
    }
  }
  for (const opt of PLATFORM_RESOURCE_TYPE_OPTIONS) {
    if (items.some((item) => item.resourceType === opt.id)) return opt.id;
  }
  if (items.some((item) => item.resourceType && !isKnownPlatformResourceType(item.resourceType))) {
    return "other";
  }
  return "web";
}

type ResourceTypeMultiPickerSectionProps = Omit<IdMultiPickerSectionProps, "compact"> & {
  typeHint?: string;
};

export function ResourceTypeMultiPickerSection({
  title,
  description,
  typeHint = "勾选表示追加绑定到本 Agent。",
  items,
  selected,
  onChange,
  disabled,
  emptyText = "该类型下暂无资源配置",
}: ResourceTypeMultiPickerSectionProps) {
  const [filter, setFilter] = useState("");
  const [typeTab, setTypeTab] = useState<ResourceListFilter>(() => defaultResourceTypeTab(items, selected));

  const showOtherTab = useMemo(
    () => items.some((item) => item.resourceType && !isKnownPlatformResourceType(item.resourceType)),
    [items],
  );

  useEffect(() => {
    if (typeTab === "other" && !showOtherTab) {
      setTypeTab(defaultResourceTypeTab(items, selected));
    }
    if (typeTab !== "all" && typeTab !== "other" && !items.some((item) => item.resourceType === typeTab)) {
      const next = defaultResourceTypeTab(items, selected);
      if (next !== typeTab) setTypeTab(next);
    }
  }, [items, selected, showOtherTab, typeTab]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return items.filter((item) => {
      const t = item.resourceType ?? "";
      if (typeTab === "other") {
        if (!t || isKnownPlatformResourceType(t)) return false;
      } else if (typeTab !== "all" && t !== typeTab) {
        return false;
      }
      return matchesPickerFilter(item, q);
    });
  }, [filter, items, typeTab]);

  const selectedInTab = useMemo(() => {
    return selected.filter((id) => {
      const item = items.find((row) => row.id === id);
      if (!item) return false;
      const t = item.resourceType ?? "";
      if (typeTab === "other") return t && !isKnownPlatformResourceType(t);
      if (typeTab === "all") return true;
      return t === typeTab;
    }).length;
  }, [items, selected, typeTab]);

  return (
    <section className="agent-binding-section agent-binding-section--resource-list" aria-label={title}>
      <div className="agent-binding-section__head">
        <h3 className="agent-binding-section__title">
          {title}
          <span className="agent-selected-count">
            {selected.length} 项已选
            {typeTab !== "all" ? ` · 当前类型 ${selectedInTab}` : ""}
          </span>
        </h3>
        {description ? <p className="agent-binding-section__desc">{description}</p> : null}
      </div>
      <nav className="resource-kind-tabs agent-binding-resource-tabs" aria-label={`${title} 资源类型`}>
        {PLATFORM_RESOURCE_TYPE_OPTIONS.map((opt) => (
          <button
            key={opt.id}
            type="button"
            className={`resource-kind-tab ${typeTab === opt.id ? "is-active" : ""}`}
            aria-current={typeTab === opt.id ? "true" : undefined}
            onClick={() => setTypeTab(opt.id)}
            disabled={disabled}
          >
            {opt.label}
          </button>
        ))}
        {showOtherTab ? (
          <button
            type="button"
            className={`resource-kind-tab ${typeTab === "other" ? "is-active" : ""}`}
            aria-current={typeTab === "other" ? "true" : undefined}
            onClick={() => setTypeTab("other")}
            disabled={disabled}
          >
            其他类型
          </button>
        ) : null}
      </nav>
      <p className="picker-type-hint muted">
        当前查看「{resourceListFilterLabel(typeTab)}」下的资源配置；{typeHint}
      </p>
      <input
        type="search"
        className="agent-binding-filter"
        placeholder="输入关键字筛选本类型资源…"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
        disabled={disabled}
        aria-label={`${title} 筛选`}
      />
      <PickerListRows
        items={filtered}
        selected={selected}
        onChange={onChange}
        disabled={disabled}
        emptyText={emptyText}
      />
    </section>
  );
}

type FileSourceTab = "project" | "platform";

function defaultFileSourceTab(items: PickerItem[], selected: string[]): FileSourceTab {
  const selectedSet = new Set(selected);
  for (const item of items) {
    if (selectedSet.has(item.id)) {
      return item.fileSource === "平台共享文件库" ? "platform" : "project";
    }
  }
  if (items.some((item) => item.fileSource === "应用文件库")) return "project";
  if (items.some((item) => item.fileSource === "平台共享文件库")) return "platform";
  return "project";
}

export function FileSourceMultiPickerSection({
  title,
  description,
  items,
  selected,
  onChange,
  disabled,
  emptyText = "暂无可选 file_id",
}: ResourceTypeMultiPickerSectionProps) {
  const [filter, setFilter] = useState("");
  const [sourceTab, setSourceTab] = useState<FileSourceTab>(() => defaultFileSourceTab(items, selected));

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const want = sourceTab === "platform" ? "平台共享文件库" : "应用文件库";
    return items.filter((item) => item.fileSource === want && matchesPickerFilter(item, q));
  }, [filter, items, sourceTab]);

  const selectedInTab = useMemo(
    () =>
      selected.filter((id) => {
        const item = items.find((row) => row.id === id);
        if (!item) return false;
        const want = sourceTab === "platform" ? "平台共享文件库" : "应用文件库";
        return item.fileSource === want;
      }).length,
    [items, selected, sourceTab],
  );

  return (
    <section className="agent-binding-section agent-binding-section--resource-list" aria-label={title}>
      <div className="agent-binding-section__head">
        <h3 className="agent-binding-section__title">
          {title}
          <span className="agent-selected-count">
            {selected.length} 项已选 · 当前来源 {selectedInTab}
          </span>
        </h3>
        {description ? <p className="agent-binding-section__desc">{description}</p> : null}
      </div>
      <nav className="resource-kind-tabs agent-binding-resource-tabs" aria-label={`${title} 文件来源`}>
        <button
          type="button"
          className={`resource-kind-tab ${sourceTab === "project" ? "is-active" : ""}`}
          aria-current={sourceTab === "project" ? "true" : undefined}
          onClick={() => setSourceTab("project")}
          disabled={disabled}
        >
          应用文件库
        </button>
        <button
          type="button"
          className={`resource-kind-tab ${sourceTab === "platform" ? "is-active" : ""}`}
          aria-current={sourceTab === "platform" ? "true" : undefined}
          onClick={() => setSourceTab("platform")}
          disabled={disabled}
        >
          平台共享文件库
        </button>
      </nav>
      <input
        type="search"
        className="agent-binding-filter"
        placeholder="输入关键字筛选文件…"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
        disabled={disabled}
        aria-label={`${title} 筛选`}
      />
      <PickerListRows
        items={filtered}
        selected={selected}
        onChange={onChange}
        disabled={disabled}
        emptyText={emptyText}
      />
    </section>
  );
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
    return items.filter((item) => matchesPickerFilter(item, q));
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
      {compact ? (
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
      ) : (
        <PickerListRows
          items={filtered}
          selected={selected}
          onChange={onChange}
          disabled={disabled}
          emptyText={emptyText}
        />
      )}
    </section>
  );
}
