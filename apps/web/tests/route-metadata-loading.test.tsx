// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Link, MemoryRouter } from "react-router-dom";
import { App } from "../src/App";

vi.mock("../src/pages/LandingPage", () => ({
  LandingPage: () => <Link to="/lab">Open lab</Link>,
}));
vi.mock("../src/pages/LabPage", () => new Promise(() => {}));
vi.mock("../src/pages/SharedScenarioPage", () => new Promise(() => {}));
vi.mock("../src/components/RouteStatePage", () => ({
  NotFoundPage: () => null,
  RouteErrorBoundary: ({ children }: { children: React.ReactNode }) => children,
  RouteLoadingState: () => <p>Loading lab</p>,
}));

afterEach(() => {
  cleanup();
  document.head.innerHTML = "";
});

it("sets the canonical while a directly opened route is still loading", async () => {
  render(
    <MemoryRouter initialEntries={["/lab"]}>
      <App />
    </MemoryRouter>,
  );
  expect(await screen.findByText("Loading lab")).toBeTruthy();
  await waitFor(() => expect(document.title).toBe("Lab — SystemForge"));
  expect(
    document.head.querySelector('link[rel="canonical"]')?.getAttribute("href"),
  ).toBe(`${window.location.origin}/lab`);
});

it("sets noindex while a shared scenario is still loading", async () => {
  render(
    <MemoryRouter initialEntries={["/scenario/abc-123"]}>
      <App />
    </MemoryRouter>,
  );
  expect(await screen.findByText("Loading lab")).toBeTruthy();
  await waitFor(() =>
    expect(
      document.head
        .querySelector('meta[name="robots"]')
        ?.getAttribute("content"),
    ).toBe("noindex,follow"),
  );
  expect(document.title).toBe("Shared scenario — SystemForge");
});
