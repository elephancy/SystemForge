// @vitest-environment jsdom

import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { RouteMetadata } from "../src/components/RouteMetadata";

afterEach(() => {
  cleanup();
  document.head.innerHTML = "";
});

const renderPath = (path: string) => {
  document.head.innerHTML = [
    '<meta name="description" content="">',
    '<meta property="og:title" content="">',
    '<meta property="og:description" content="">',
    '<meta property="og:url" content="">',
    '<meta name="twitter:title" content="">',
    '<meta name="twitter:description" content="">',
  ].join("");
  return render(
    <MemoryRouter initialEntries={[path]}>
      <RouteMetadata />
    </MemoryRouter>,
  );
};

describe("route metadata", () => {
  it("keeps known workspaces indexable", async () => {
    renderPath("/lab");
    await waitFor(() =>
      expect(
        document.head
          .querySelector('meta[name="robots"]')
          ?.getAttribute("content"),
      ).toBe("index,follow"),
    );
    expect(document.title).toBe("Lab — SystemForge");
    const canonicals = document.head.querySelectorAll('link[rel="canonical"]');
    expect(canonicals).toHaveLength(1);
    expect(canonicals[0]?.getAttribute("href")).toBe(`${window.location.origin}/lab`);
  });

  it("describes the completed-run replay workspace", async () => {
    renderPath("/replay");
    await waitFor(() => expect(document.title).toContain("Replay a run"));
    expect(
      document.head
        .querySelector('meta[name="description"]')
        ?.getAttribute("content"),
    ).toContain("replay bundle");
    expect(
      document.head
        .querySelector('meta[name="robots"]')
        ?.getAttribute("content"),
    ).toBe("index,follow");
  });

  it("updates an existing canonical without creating a second one", async () => {
    renderPath("/custom");
    const existing = document.createElement("link");
    existing.rel = "canonical";
    existing.href = `${window.location.origin}/custom`;
    // React may already have run the effect; replace the head link to exercise
    // an existing self-canonical on a fresh render.
    document.head.querySelector('link[rel="canonical"]')?.remove();
    document.head.append(existing);
    cleanup();
    render(<MemoryRouter initialEntries={["/custom"]}><RouteMetadata /></MemoryRouter>);
    await waitFor(() => expect(document.title).toBe("Create a scenario — SystemForge"));
    expect(document.head.querySelectorAll('link[rel="canonical"]')).toHaveLength(1);
    expect(existing.getAttribute("href")).toBe(`${window.location.origin}/custom`);
  });

  it("keeps the decision workbench as an indexable workspace", async () => {
    renderPath("/decisions");
    await waitFor(() => expect(document.title).toContain("Decision workbench"));
    expect(
      document.head
        .querySelector('meta[name="robots"]')
        ?.getAttribute("content"),
    ).toBe("index,follow");
  });

  it("marks exact shared links noindex", async () => {
    renderPath("/scenario/abc-123");
    await waitFor(() =>
      expect(
        document.head
          .querySelector('meta[name="robots"]')
          ?.getAttribute("content"),
      ).toBe("noindex,follow"),
    );
    expect(document.title).toBe("Shared scenario — SystemForge");
  });

  it("does not mislabel nested unknown paths as shared scenarios", async () => {
    renderPath("/scenario/abc-123/extra");
    await waitFor(() => expect(document.title).toContain("Page not found"));
    expect(document.title).not.toContain("Shared");
  });
});
