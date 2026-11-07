import { mkdir, readFile, writeFile } from "node:fs/promises";
import metadata from "../src/routeMetadata.json" with { type: "json" };

const output = new URL("../dist/nginx/", import.meta.url);
const template = await readFile(
  new URL("../dist/client/index.html", import.meta.url),
  "utf8",
);
const escape = (text) =>
  text
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");

function render(page, pathname, indexable) {
  let html = template;
  function replace(pattern, replacement) {
    if ([...html.matchAll(pattern)].length !== 1)
      throw new Error(`Expected one metadata match: ${pattern}`);
    html = html.replace(pattern, () => replacement);
  }
  replace(/<title>[^<]*<\/title>/g, `<title>${escape(page.title)}</title>`);
  for (const [attribute, key, value] of [
    ["name", "description", page.description],
    ["property", "og:title", page.title],
    ["property", "og:description", page.description],
    ["property", "og:url", `https://systemforge.elfeel.me${pathname ?? "/"}`],
    ["name", "twitter:title", page.title],
    ["name", "twitter:description", page.description],
  ]) {
    replace(
      new RegExp(
        `<meta\\s+${attribute}="${key}"\\s+content="[^"]*"\\s*\\/>`,
        "g",
      ),
      `<meta ${attribute}="${key}" content="${escape(value)}" />`,
    );
  }
  const canonical = pathname
    ? `\n    <link rel="canonical" href="https://systemforge.elfeel.me${escape(pathname)}" />`
    : "";
  return html.replace(
    "</head>",
    `    <meta name="robots" content="${indexable ? "index,follow" : "noindex,follow"}" />${canonical}\n  </head>`,
  );
}

await mkdir(new URL("__seo/", output), { recursive: true });
for (const [pathname, page] of Object.entries(metadata)) {
  const file = pathname === "/" ? "index.html" : `__seo${pathname}.html`;
  await writeFile(new URL(file, output), render(page, pathname, true));
}
await writeFile(
  new URL("__seo/shared.html", output),
  render(
    {
      title: "Shared scenario — SystemForge",
      description: "Open a shared scenario in the Lab.",
    },
    null,
    false,
  ),
);
await writeFile(
  new URL("__seo/not-found.html", output),
  render(
    {
      title: "Page not found — SystemForge",
      description: "This SystemForge page does not exist.",
    },
    null,
    false,
  ),
);
