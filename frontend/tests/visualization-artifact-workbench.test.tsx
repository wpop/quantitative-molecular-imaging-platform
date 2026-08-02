import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { App } from "../src/App";

const artifactImageUrl = "http://localhost:8000/api/v1/analysis/artifacts/42/image/";

const baseArtifact = {
  id: 42,
  instance_id: 7,
  sop_instance_uid: "1.2.826.0.1.sop",
  series_instance_uid: "1.2.826.0.1.series",
  study_instance_uid: "1.2.826.0.1.study",
  operation: "rescale",
  modality: "CT",
  slice_index: 12,
  value_units: "HU",
  rows: 512,
  columns: 512,
  colormap: "gray",
  display_minimum: -200,
  display_maximum: 200,
  window_center: 40,
  window_width: 400,
  mime_type: "image/png",
  file_size_bytes: 2048,
  file_sha256: "a".repeat(64),
  created_at: "2026-08-02T10:00:00Z",
  updated_at: "2026-08-02T10:05:00Z",
  image_url: artifactImageUrl,
  relative_path: "outputs/visualizations/private-artifact.png",
  absolute_path: "/tmp/qmip/private-artifact.png",
};

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
    ...init,
  });
}

function dashboardResponse(path: string) {
  if (path === "/api/v1/overview/") {
    return jsonResponse({
      studies_count: 1,
      series_count: 1,
      instances_count: 1,
      modalities: ["CT"],
      source_datasets: [],
      source_subjects: [],
      ingestion_jobs_count: 0,
      latest_ingestion_status: null,
      latest_ingestion_started_at: null,
      latest_ingestion_completed_at: null,
    });
  }
  if (path === "/api/v1/imaging/studies/") {
    return jsonResponse([]);
  }
  if (path === "/api/v1/imaging/series/") {
    return jsonResponse([]);
  }
  if (path === "/api/v1/analysis/runs/") {
    return jsonResponse([]);
  }
  if (path === "/api/v1/analysis/results/") {
    return jsonResponse([]);
  }
  return null;
}

function installFetchMock(artifacts: unknown[] = [baseArtifact]) {
  const requests: string[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(input.toString());
    requests.push(`${url.pathname}${url.search}`);

    const dashboard = dashboardResponse(url.pathname);
    if (dashboard) {
      return dashboard;
    }
    if (url.pathname === "/api/v1/analysis/artifacts/") {
      return jsonResponse(artifacts);
    }
    return jsonResponse({ detail: "Not found" }, { status: 404, statusText: "Not Found" });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { requests };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("VisualizationArtifactWorkbench", () => {
  test("renders artifact API responses and automatically selects the first artifact", async () => {
    installFetchMock();

    render(<App />);

    const selectedArtifact = await screen.findByRole("button", {
      name: /CT rescale Slice 12 HU 512 x 512/i,
    });

    expect(selectedArtifact.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("Visualization Artifacts")).toBeTruthy();
    expect(screen.getAllByText("HU").length).toBeGreaterThan(0);
  });

  test("uses image_url for the selected PNG and displays artifact metadata", async () => {
    installFetchMock();

    render(<App />);

    const image = await screen.findByRole("img", {
      name: /CT rescale visualization artifact, slice 12/i,
    });

    expect(image.getAttribute("src")).toBe(artifactImageUrl);
    expect(screen.getByText("Rows x columns")).toBeTruthy();
    expect(screen.getAllByText("512 x 512").length).toBeGreaterThan(0);
    expect(screen.getByText("Display minimum")).toBeTruthy();
    expect(screen.getByText("-200")).toBeTruthy();
    expect(screen.getByText("Window center")).toBeTruthy();
    expect(screen.getByText("40")).toBeTruthy();
    expect(screen.getByText(baseArtifact.file_sha256)).toBeTruthy();
    expect(screen.getByText(baseArtifact.study_instance_uid)).toBeTruthy();
    expect(screen.getByText(baseArtifact.series_instance_uid)).toBeTruthy();
    expect(screen.getByText(baseArtifact.sop_instance_uid)).toBeTruthy();
  });

  test("apply filters sends the supported query parameters", async () => {
    const { requests } = installFetchMock();
    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    fireEvent.change(screen.getByLabelText("Series Instance UID"), {
      target: { value: "1.2.826.0.1.series" },
    });
    fireEvent.change(screen.getByLabelText("SOP Instance UID"), {
      target: { value: "1.2.826.0.1.sop" },
    });
    fireEvent.change(screen.getByLabelText("Operation"), { target: { value: "gaussian" } });
    fireEvent.change(screen.getByLabelText("Modality"), { target: { value: "PT" } });

    const requestCountBeforeApply = requests.length;
    fireEvent.click(screen.getByRole("button", { name: "Apply Filters" }));

    await waitFor(() => expect(requests.length).toBeGreaterThan(requestCountBeforeApply));
    const filteredRequest = requests.at(-1) ?? "";
    expect(filteredRequest).toContain("/api/v1/analysis/artifacts/?");
    expect(filteredRequest).toContain("series_instance_uid=1.2.826.0.1.series");
    expect(filteredRequest).toContain("sop_instance_uid=1.2.826.0.1.sop");
    expect(filteredRequest).toContain("operation=gaussian");
    expect(filteredRequest).toContain("modality=PT");
  });

  test("clear filters removes active filters and reloads the collection", async () => {
    const { requests } = installFetchMock();
    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    fireEvent.change(screen.getByLabelText("Operation"), { target: { value: "sobel" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply Filters" }));
    await waitFor(() => expect(requests.at(-1)).toContain("operation=sobel"));

    fireEvent.click(screen.getByRole("button", { name: "Clear Filters" }));

    await waitFor(() => expect(requests.at(-1)).toBe("/api/v1/analysis/artifacts/"));
    expect((screen.getByLabelText("Operation") as HTMLSelectElement).value).toBe("");
  });

  test("empty API responses display the empty state", async () => {
    installFetchMock([]);

    render(<App />);

    expect(
      await screen.findByText("No registered visualization artifacts match the current filters."),
    ).toBeTruthy();
  });

  test("API failures display a controlled error", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(input.toString());
      const dashboard = dashboardResponse(url.pathname);
      if (dashboard) {
        return dashboard;
      }
      return jsonResponse({ detail: "Service unavailable" }, { status: 503 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByText("Artifact API is not available.")).toBeTruthy();
    expect(screen.getByText("Visualization artifacts could not be loaded.")).toBeTruthy();
  });

  test("PNG loading failures display a controlled image error", async () => {
    installFetchMock();

    render(<App />);

    const image = await screen.findByRole("img", {
      name: /CT rescale visualization artifact, slice 12/i,
    });
    fireEvent.error(image);

    expect(await screen.findByText("The registered PNG image could not be loaded.")).toBeTruthy();
  });

  test("local filesystem paths from JSON are never rendered", async () => {
    installFetchMock();

    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    expect(document.body.textContent).not.toContain("outputs/visualizations");
    expect(document.body.textContent).not.toContain("/tmp/qmip");
  });

  test("write, editing, deletion, and operation execution controls are absent", async () => {
    installFetchMock();

    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    expect(screen.queryByRole("button", { name: /post|upload|edit|delete|execute|generate|run/i }))
      .toBeNull();
  });
});
