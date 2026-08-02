import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { App } from "../src/App";
import { toGenerationRequest, validateGenerationForm } from "../src/VisualizationArtifactWorkbench";

const artifactImageUrl = "http://localhost:8000/api/v1/analysis/artifacts/42/image/";
const generatedArtifactImageUrl = "http://localhost:8000/api/v1/analysis/artifacts/99/image/";

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

const generatedArtifact = {
  ...baseArtifact,
  id: 99,
  operation: "gaussian",
  slice_index: 3,
  file_sha256: "b".repeat(64),
  image_url: generatedArtifactImageUrl,
};

type RecordedRequest = {
  method: string;
  path: string;
  body: unknown;
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

function installFetchMock(
  artifacts: unknown[] = [baseArtifact],
  options: {
    generated?: unknown;
    generationResponse?: Response;
    refreshedArtifacts?: unknown[];
  } = {},
) {
  const requests: RecordedRequest[] = [];
  let artifactGetCount = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input.toString());
    const method = init?.method ?? "GET";
    requests.push({
      method,
      path: `${url.pathname}${url.search}`,
      body: init?.body ? JSON.parse(init.body.toString()) : undefined,
    });

    const dashboard = dashboardResponse(url.pathname);
    if (dashboard) {
      return dashboard;
    }
    if (url.pathname === "/api/v1/analysis/artifacts/generate/" && method === "POST") {
      return options.generationResponse ?? jsonResponse(options.generated ?? generatedArtifact);
    }
    if (url.pathname === "/api/v1/analysis/artifacts/") {
      artifactGetCount += 1;
      if (artifactGetCount > 1 && options.refreshedArtifacts) {
        return jsonResponse(options.refreshedArtifacts);
      }
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

function generationInput(name: string): HTMLInputElement {
  return document.querySelector(`input[name="${name}"]`) as HTMLInputElement;
}

function generationSelect(name: string): HTMLSelectElement {
  return document.querySelector(`select[name="${name}"]`) as HTMLSelectElement;
}

function validGenerationForm(): Parameters<typeof validateGenerationForm>[0] {
  return {
    series_instance_uid: "1.2.826.0.1.series",
    operation: "rescale",
    slice_index: "",
    gaussian_sigma: "",
    window_center: "",
    window_width: "",
    lower_percentile: "",
    upper_percentile: "",
    dpi: "",
  };
}

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
    expect(screen.getAllByText("Window center").length).toBeGreaterThan(0);
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

    fireEvent.change(screen.getAllByLabelText("Series Instance UID")[0], {
      target: { value: "1.2.826.0.1.series" },
    });
    fireEvent.change(screen.getByLabelText("SOP Instance UID"), {
      target: { value: "1.2.826.0.1.sop" },
    });
    fireEvent.change(screen.getAllByLabelText("Operation")[0], { target: { value: "gaussian" } });
    fireEvent.change(screen.getByLabelText("Modality"), { target: { value: "PT" } });

    const requestCountBeforeApply = requests.length;
    fireEvent.click(screen.getByRole("button", { name: "Apply Filters" }));

    await waitFor(() => expect(requests.length).toBeGreaterThan(requestCountBeforeApply));
    const filteredRequest = requests.at(-1)?.path ?? "";
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

    fireEvent.change(screen.getAllByLabelText("Operation")[0], { target: { value: "sobel" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply Filters" }));
    await waitFor(() => expect(requests.at(-1)?.path).toContain("operation=sobel"));

    fireEvent.click(screen.getByRole("button", { name: "Clear Filters" }));

    await waitFor(() => expect(requests.at(-1)?.path).toBe("/api/v1/analysis/artifacts/"));
    expect((screen.getAllByLabelText("Operation")[0] as HTMLSelectElement).value).toBe("");
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

  test("generation controls render", async () => {
    installFetchMock();

    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    expect(screen.getByRole("heading", { name: "Generate Visualization" })).toBeTruthy();
    expect(screen.getAllByLabelText("Series Instance UID").length).toBe(2);
    expect(screen.getByLabelText("Gaussian sigma")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Generate Visualization" })).toBeTruthy();
  });

  test("valid rescale request sends the expected JSON and omits blank optional fields", async () => {
    const { requests } = installFetchMock();
    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    fireEvent.change(generationInput("generation_series_instance_uid"), {
      target: { value: "1.2.826.0.1.series" },
    });
    fireEvent.change(screen.getByLabelText("Window center"), { target: { value: "40" } });
    fireEvent.change(screen.getByLabelText("Window width"), { target: { value: "400" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate Visualization" }));

    await screen.findByText("Visualization artifact generated and selected.");
    const postRequest = requests.find((request) => request.method === "POST");
    expect(postRequest?.path).toBe("/api/v1/analysis/artifacts/generate/");
    expect(postRequest?.body).toEqual({
      series_instance_uid: "1.2.826.0.1.series",
      operation: "rescale",
      window_center: 40,
      window_width: 400,
    });
  });

  test("gaussian request sends gaussian_sigma", async () => {
    const { requests } = installFetchMock();
    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    fireEvent.change(generationInput("generation_series_instance_uid"), {
      target: { value: "1.2.826.0.1.series" },
    });
    fireEvent.change(generationSelect("generation_operation"), { target: { value: "gaussian" } });
    fireEvent.change(screen.getByLabelText("Gaussian sigma"), { target: { value: "1.5" } });
    fireEvent.change(screen.getByLabelText("Window center"), { target: { value: "45" } });
    fireEvent.change(screen.getByLabelText("Window width"), { target: { value: "350" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate Visualization" }));

    await screen.findByText("Visualization artifact generated and selected.");
    expect(requests.find((request) => request.method === "POST")?.body).toMatchObject({
      operation: "gaussian",
      gaussian_sigma: 1.5,
      window_center: 45,
      window_width: 350,
    });
  });

  test("stale gaussian_sigma is not submitted after switching from Gaussian to Rescale", async () => {
    const { requests } = installFetchMock();
    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    fireEvent.change(generationInput("generation_series_instance_uid"), {
      target: { value: "1.2.826.0.1.series" },
    });
    fireEvent.change(generationSelect("generation_operation"), { target: { value: "gaussian" } });
    fireEvent.change(screen.getByLabelText("Gaussian sigma"), { target: { value: "1.5" } });
    fireEvent.change(generationSelect("generation_operation"), { target: { value: "rescale" } });
    expect(generationInput("gaussian_sigma").value).toBe("1.5");

    fireEvent.click(screen.getByRole("button", { name: "Generate Visualization" }));

    await screen.findByText("Visualization artifact generated and selected.");
    const body = requests.find((request) => request.method === "POST")?.body;
    expect(body).toMatchObject({
      series_instance_uid: "1.2.826.0.1.series",
      operation: "rescale",
    });
    expect(body).not.toHaveProperty("gaussian_sigma");
  });

  test("stale window fields are not submitted after switching to Sobel", async () => {
    const { requests } = installFetchMock();
    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    fireEvent.change(generationInput("generation_series_instance_uid"), {
      target: { value: "1.2.826.0.1.series" },
    });
    fireEvent.change(screen.getByLabelText("Window center"), { target: { value: "40" } });
    fireEvent.change(screen.getByLabelText("Window width"), { target: { value: "400" } });
    fireEvent.change(generationSelect("generation_operation"), { target: { value: "sobel" } });
    expect(generationInput("window_center").value).toBe("40");
    expect(generationInput("window_width").value).toBe("400");

    fireEvent.click(screen.getByRole("button", { name: "Generate Visualization" }));

    await screen.findByText("Visualization artifact generated and selected.");
    const body = requests.find((request) => request.method === "POST")?.body;
    expect(body).toMatchObject({
      series_instance_uid: "1.2.826.0.1.series",
      operation: "sobel",
    });
    expect(body).not.toHaveProperty("window_center");
    expect(body).not.toHaveProperty("window_width");
  });

  test("disabled stale operation-specific values do not prevent submission", async () => {
    const { requests } = installFetchMock();
    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    fireEvent.change(generationInput("generation_series_instance_uid"), {
      target: { value: "1.2.826.0.1.series" },
    });
    fireEvent.change(generationSelect("generation_operation"), { target: { value: "gaussian" } });
    fireEvent.change(screen.getByLabelText("Gaussian sigma"), { target: { value: "0" } });
    fireEvent.change(generationSelect("generation_operation"), { target: { value: "rescale" } });
    fireEvent.change(screen.getByLabelText("Window width"), { target: { value: "0" } });
    fireEvent.change(generationSelect("generation_operation"), { target: { value: "sobel" } });

    fireEvent.click(screen.getByRole("button", { name: "Generate Visualization" }));

    await screen.findByText("Visualization artifact generated and selected.");
    const body = requests.find((request) => request.method === "POST")?.body;
    expect(body).toEqual({
      series_instance_uid: "1.2.826.0.1.series",
      operation: "sobel",
    });
  });

  test("toGenerationRequest omits disabled and blank optional fields", () => {
    expect(
      toGenerationRequest({
        ...validGenerationForm(),
        operation: "rescale",
        gaussian_sigma: "1.5",
        window_center: "",
        window_width: "",
        lower_percentile: "",
        upper_percentile: "",
        dpi: "",
      }),
    ).toEqual({
      series_instance_uid: "1.2.826.0.1.series",
      operation: "rescale",
    });

    expect(
      toGenerationRequest({
        ...validGenerationForm(),
        operation: "sobel",
        gaussian_sigma: "1.5",
        window_center: "40",
        window_width: "400",
        slice_index: "2",
        lower_percentile: "5",
        upper_percentile: "95",
        dpi: "120",
      }),
    ).toEqual({
      series_instance_uid: "1.2.826.0.1.series",
      operation: "sobel",
      slice_index: 2,
      lower_percentile: 5,
      upper_percentile: 95,
      dpi: 120,
    });
  });

  test("validation rejects non-finite supplied numeric values", () => {
    expect(validateGenerationForm({ ...validGenerationForm(), slice_index: "Infinity" })).toHaveProperty(
      "slice_index",
    );
    expect(
      validateGenerationForm({
        ...validGenerationForm(),
        operation: "gaussian",
        gaussian_sigma: "Infinity",
      }),
    ).toHaveProperty("gaussian_sigma");
    expect(
      validateGenerationForm({
        ...validGenerationForm(),
        window_center: "Infinity",
      }),
    ).toHaveProperty("window_center");
    expect(
      validateGenerationForm({
        ...validGenerationForm(),
        window_width: "Infinity",
      }),
    ).toHaveProperty("window_width");
    expect(
      validateGenerationForm({
        ...validGenerationForm(),
        lower_percentile: "NaN",
      }),
    ).toHaveProperty("percentiles");
    expect(
      validateGenerationForm({
        ...validGenerationForm(),
        upper_percentile: "Infinity",
      }),
    ).toHaveProperty("percentiles");
    expect(validateGenerationForm({ ...validGenerationForm(), dpi: "Infinity" })).toHaveProperty(
      "dpi",
    );
  });

  test("frontend validation prevents invalid generation submissions", async () => {
    const { requests } = installFetchMock();
    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    fireEvent.click(screen.getByRole("button", { name: "Generate Visualization" }));
    expect(await screen.findByText("Series Instance UID is required.")).toBeTruthy();

    fireEvent.change(generationInput("generation_series_instance_uid"), {
      target: { value: "1.2.826.0.1.series" },
    });
    fireEvent.change(screen.getByLabelText("Slice index"), { target: { value: "-1" } });
    fireEvent.change(screen.getByLabelText("Window width"), { target: { value: "0" } });
    fireEvent.change(screen.getByLabelText("Lower percentile"), { target: { value: "99" } });
    fireEvent.change(screen.getByLabelText("Upper percentile"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("DPI"), { target: { value: "1.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate Visualization" }));

    expect(await screen.findByText("Slice index must be a non-negative integer.")).toBeTruthy();
    expect(screen.getByText("Window width must be greater than zero.")).toBeTruthy();
    expect(screen.getByText("Percentiles must satisfy 0 <= lower < upper <= 100.")).toBeTruthy();
    expect(screen.getByText("DPI must be a positive integer.")).toBeTruthy();
    expect(requests.some((request) => request.method === "POST")).toBe(false);
  });

  test("non-positive gaussian sigma prevents submission", async () => {
    const { requests } = installFetchMock();
    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    fireEvent.change(generationInput("generation_series_instance_uid"), {
      target: { value: "1.2.826.0.1.series" },
    });
    fireEvent.change(generationSelect("generation_operation"), { target: { value: "gaussian" } });
    fireEvent.change(screen.getByLabelText("Gaussian sigma"), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate Visualization" }));

    expect(await screen.findByText("Gaussian sigma must be greater than zero.")).toBeTruthy();
    expect(requests.some((request) => request.method === "POST")).toBe(false);
  });

  test("submit button is disabled while generation is pending", async () => {
    let resolveGeneration: (response: Response) => void = () => undefined;
    const generationPromise = new Promise<Response>((resolve) => {
      resolveGeneration = resolve;
    });
    const requests: RecordedRequest[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(input.toString());
        const method = init?.method ?? "GET";
        requests.push({ method, path: `${url.pathname}${url.search}`, body: undefined });
        const dashboard = dashboardResponse(url.pathname);
        if (dashboard) {
          return dashboard;
        }
        if (url.pathname === "/api/v1/analysis/artifacts/generate/") {
          return generationPromise;
        }
        return jsonResponse([baseArtifact]);
      }),
    );

    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });
    fireEvent.change(generationInput("generation_series_instance_uid"), {
      target: { value: "1.2.826.0.1.series" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate Visualization" }));

    expect(await screen.findByRole("button", { name: "Generating..." })).toHaveProperty(
      "disabled",
      true,
    );
    resolveGeneration(jsonResponse(generatedArtifact));
    await screen.findByText("Visualization artifact generated and selected.");
    expect(requests.some((request) => request.method === "POST")).toBe(true);
  });

  test("successful generation selects returned artifact, refreshes list, and avoids duplicates", async () => {
    const { requests } = installFetchMock([baseArtifact], {
      refreshedArtifacts: [baseArtifact, generatedArtifact],
    });
    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    fireEvent.change(generationInput("generation_series_instance_uid"), {
      target: { value: "1.2.826.0.1.series" },
    });
    fireEvent.change(generationSelect("generation_operation"), { target: { value: "gaussian" } });
    fireEvent.change(screen.getByLabelText("Gaussian sigma"), { target: { value: "1.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate Visualization" }));

    const selectedGenerated = await screen.findByRole("button", {
      name: /CT gaussian Slice 3 HU 512 x 512/i,
    });
    expect(selectedGenerated.getAttribute("aria-pressed")).toBe("true");
    expect(
      await screen.findByRole("img", {
        name: /CT gaussian visualization artifact, slice 3/i,
      }),
    ).toBeTruthy();
    expect(requests.filter((request) => request.path.startsWith("/api/v1/analysis/artifacts/")).length)
      .toBeGreaterThanOrEqual(3);
    expect(screen.getAllByRole("button", { name: /CT gaussian Slice 3/i })).toHaveLength(1);
  });

  test("generated artifact is displayed even when active filters exclude it", async () => {
    installFetchMock([baseArtifact], { refreshedArtifacts: [] });
    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    fireEvent.change(generationInput("generation_series_instance_uid"), {
      target: { value: "1.2.826.0.1.series" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate Visualization" }));

    expect(
      await screen.findByRole("button", { name: /CT gaussian Slice 3 HU 512 x 512/i }),
    ).toBeTruthy();
  });

  test("controlled backend validation errors are displayed safely and preserve state", async () => {
    installFetchMock([baseArtifact], {
      generationResponse: jsonResponse(
        { detail: "Failed at /tmp/qmip/outputs/visualizations/private.png" },
        { status: 400 },
      ),
    });
    render(<App />);
    const originalArtifact = await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    fireEvent.change(generationInput("generation_series_instance_uid"), {
      target: { value: "1.2.826.0.1.series" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate Visualization" }));

    expect(await screen.findByText("Backend request failed.")).toBeTruthy();
    expect(document.body.textContent).not.toContain("/tmp/qmip");
    expect(document.body.textContent).not.toContain("outputs/visualizations");
    expect(generationInput("generation_series_instance_uid").value).toBe("1.2.826.0.1.series");
    expect(originalArtifact.getAttribute("aria-pressed")).toBe("true");
  });

  test("upload, editing, deletion, and filesystem controls are absent", async () => {
    installFetchMock();

    render(<App />);
    await screen.findByRole("button", { name: /CT rescale Slice 12/i });

    expect(screen.queryByRole("button", { name: /post|upload|edit|delete|browse|filesystem|run/i }))
      .toBeNull();
  });
});
