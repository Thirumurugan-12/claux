import { Chip } from "../../components/Chip";
import type { ToolCall } from "../../api";

/** The inline trace of tools an assistant turn ran — one chip per call, tinted by outcome. */
export function ToolTrace({ toolCalls }: { toolCalls: ToolCall[] }) {
  if (!toolCalls.length) return null;
  return (
    <div className="tool-trace">
      <span className="tool-trace-label">Traced</span>
      {toolCalls.map((tc, i) => (
        <Chip
          key={i}
          tone={tc.ok ? "success" : "danger"}
          dot
          mono
          title={tc.ok ? "tool ran" : (tc.error ?? "denied")}
        >
          {tc.tool}
        </Chip>
      ))}
    </div>
  );
}
