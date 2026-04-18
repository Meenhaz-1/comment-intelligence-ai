import Link from "next/link";

import { Editor } from "@/lib/types";

export function EditorHeader({ editor }: { editor: Editor }) {
  return (
    <header>
      <div className="dashboard-topbar">
        <Link href="/" className="back-link">
          {"← Back to Home"}
        </Link>
      </div>
      <h1 className="editor-name">{editor.name}</h1>
      <p className="subtitle" style={{ textAlign: "left", maxWidth: "unset" }}>
        Recipe Creator performance across reach, intent, and quality.
      </p>
    </header>
  );
}
