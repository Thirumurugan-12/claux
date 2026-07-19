import { IconButton } from "./IconButton";
import { Moon, Sun } from "./icons";
import type { Theme } from "../hooks/useTheme";

interface ThemeToggleProps {
  theme: Theme;
  onToggle: () => void;
}

export function ThemeToggle({ theme, onToggle }: ThemeToggleProps) {
  const label = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
  return (
    <IconButton label={label} onClick={onToggle}>
      {theme === "dark" ? <Sun /> : <Moon />}
    </IconButton>
  );
}
