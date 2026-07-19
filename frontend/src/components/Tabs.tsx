import type { ReactNode } from "react";

export interface TabItem<T extends string> {
  id: T;
  label: string;
  icon: ReactNode;
  /** Show a small indicator that data is available under this tab. */
  hasData?: boolean;
}

interface TabsProps<T extends string> {
  items: TabItem<T>[];
  value: T;
  onChange: (id: T) => void;
  ariaLabel: string;
}

/** Underlined tab strip. The active tab is the only element carrying the accent. */
export function Tabs<T extends string>({ items, value, onChange, ariaLabel }: TabsProps<T>) {
  return (
    <div className="tabs" role="tablist" aria-label={ariaLabel}>
      {items.map((item) => (
        <button
          key={item.id}
          role="tab"
          aria-selected={value === item.id}
          className={value === item.id ? "tab active" : "tab"}
          onClick={() => onChange(item.id)}
        >
          {item.icon}
          <span>{item.label}</span>
          {item.hasData && <span className="tab-dot" aria-label="data available" />}
        </button>
      ))}
    </div>
  );
}
