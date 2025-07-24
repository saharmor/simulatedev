import { useEffect, useState } from "react";
import { onOpenUrl } from "@tauri-apps/plugin-deep-link";

export function useDeepLink() {
  const [deepLinkUrl, setDeepLinkUrl] = useState<string | null>(null);

  useEffect(() => {
    // Listen for deep link events
    const unlisten = onOpenUrl((urls) => {
      if (urls.length > 0) {
        setDeepLinkUrl(urls[0]);
      }
    });

    return () => {
      unlisten.then((fn) => fn());
    };
  }, []);

  const parseDeepLink = (url: string) => {
    try {
      const parsedUrl = new URL(url);
      const path = parsedUrl.pathname;
      const searchParams = new URLSearchParams(parsedUrl.search);

      return {
        path,
        params: Object.fromEntries(searchParams.entries()),
      };
    } catch (error) {
      console.error("Failed to parse deep link URL:", error);
      return null;
    }
  };

  const clearDeepLink = () => {
    setDeepLinkUrl(null);
  };

  return {
    deepLinkUrl,
    parseDeepLink,
    clearDeepLink,
  };
}
