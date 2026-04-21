import { AppLink } from "@/components/navigation/navigation-progress";
import { Editor } from "@/lib/types";

export function EditorHeader({ editor }: { editor: Editor }) {
  return (
    <header>
      <div className="dashboard-topbar">
        <AppLink href="/" className="back-link">
          {"← Back to Home"}
        </AppLink>
      </div>
      <h1 className="editor-name">{editor.name}</h1>
      <p className="subtitle" style={{ textAlign: "left", maxWidth: "unset" }}>
        Recipe Creator performance across reach, intent, and quality.
      </p>
    </header>
  );
}
