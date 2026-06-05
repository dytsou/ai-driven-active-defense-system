import { useCallback, useState } from "react";

export function usePortalPanels() {
  const [activePanel, setActivePanel] = useState("login");

  const showPanel = useCallback((panel) => {
    setActivePanel(panel);
  }, []);

  function panelClass(panel) {
    return `auth-panel auth-panel--${panel}${activePanel === panel ? " is-active" : ""}`;
  }

  function panelAriaHidden(panel) {
    return activePanel !== panel;
  }

  return { activePanel, showPanel, panelClass, panelAriaHidden };
}
