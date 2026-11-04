import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import metadata from "../routeMetadata.json";

const setMeta = (selector: string, content: string) => {
  const element = document.head.querySelector<HTMLMetaElement>(selector);
  if (element) element.content = content;
};

export function RouteMetadata() {
  const location = useLocation();

  useEffect(() => {
    document.documentElement.scrollTop = 0;
    document.documentElement.scrollLeft = 0;
    document.body.scrollTop = 0;
    document.body.scrollLeft = 0;
    const isShared = /^\/scenario\/[A-Za-z0-9-]+$/.test(location.pathname);
    const route =
      metadata[location.pathname as keyof typeof metadata] ??
      (isShared
        ? {
            title: "Shared scenario — SystemForge",
            description: "Open a shared scenario in the Lab.",
          }
        : {
            title: "Page not found — SystemForge",
            description: "This SystemForge page does not exist.",
          });
    const canonicalUrl = `${window.location.origin}${location.pathname}`;
    document.title = route.title;
    setMeta('meta[name="description"]', route.description);
    setMeta('meta[property="og:title"]', route.title);
    setMeta('meta[property="og:description"]', route.description);
    setMeta('meta[property="og:url"]', canonicalUrl);
    setMeta('meta[name="twitter:title"]', route.title);
    setMeta('meta[name="twitter:description"]', route.description);
    let canonical = document.head.querySelector<HTMLLinkElement>(
      'link[rel="canonical"]',
    );
    if (!canonical) {
      canonical = document.createElement("link");
      canonical.rel = "canonical";
      document.head.append(canonical);
    }
    canonical.href = canonicalUrl;
    let robots = document.head.querySelector<HTMLMetaElement>(
      'meta[name="robots"]',
    );
    if (!robots) {
      robots = document.createElement("meta");
      robots.name = "robots";
      document.head.append(robots);
    }
    robots.content = isShared
      ? "noindex,follow"
      : metadata[location.pathname as keyof typeof metadata]
        ? "index,follow"
        : "noindex,follow";
  }, [location.pathname]);

  return null;
}
