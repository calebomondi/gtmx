import { useEffect } from "react"

const APP_NAME = "Thalace"

/** The browser tab says where you are ("Shanga • Chat", "Home Feed"); just
 * the app's name until the page knows (null), e.g. while a Lace loads. */
export function usePageTitle(title: string | null) {
  useEffect(() => {
    document.title = title ?? APP_NAME
  }, [title])
}
