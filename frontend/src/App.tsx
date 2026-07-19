import { useCallback, useEffect, useState } from "react";
import type { ToolCall } from "./api";
import { useTheme } from "./hooks/useTheme";
import { useDemoRoles } from "./hooks/useDemoRoles";
import { TopBar } from "./features/layout/TopBar";
import { StatusBar } from "./features/layout/StatusBar";
import { SessionPanel } from "./features/layout/SessionPanel";
import { Workspace } from "./features/layout/Workspace";
import { ChatPane } from "./features/chat/ChatPane";
import { CaseDrawer } from "./features/case/CaseDrawer";

export default function App() {
  const { theme, toggle } = useTheme();
  const { roles, roleIdx, setRoleIdx, current, principal } = useDemoRoles();

  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [openCase, setOpenCase] = useState<string | null>(null);

  const onAnswer = useCallback((tcs: ToolCall[]) => setToolCalls(tcs), []);

  // A role change is a fresh RBAC context — clear the panes and any open case file.
  useEffect(() => {
    setToolCalls([]);
    setOpenCase(null);
  }, [principal]);

  return (
    <div className="app">
      <TopBar
        roles={roles}
        roleIdx={roleIdx}
        onRoleChange={setRoleIdx}
        theme={theme}
        onToggleTheme={toggle}
      />

      <main className="bento">
        {/* Remount the chat on role change so the new principal starts a clean conversation. */}
        <ChatPane key={principal.role} principal={principal} onAnswer={onAnswer} />
        <SessionPanel current={current} toolCalls={toolCalls} />
        <Workspace toolCalls={toolCalls} onOpenCase={setOpenCase} />
      </main>

      <StatusBar />

      {openCase && <CaseDrawer crimeNo={openCase} principal={principal} onClose={() => setOpenCase(null)} />}
    </div>
  );
}
