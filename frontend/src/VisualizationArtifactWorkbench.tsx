import { useEffect, useMemo, useRef, useState } from "react";

import {
  apiBaseUrl,
  fetchVisualizationArtifacts,
  generateVisualizationArtifact,
  type VisualizationArtifact,
  type VisualizationArtifactFilters,
  type VisualizationArtifactOperation,
  type VisualizationGenerationRequest,
} from "./api/client";

type ArtifactState =
  | { status: "loading" }
  | { status: "loaded"; artifacts: VisualizationArtifact[] }
  | { status: "error"; message: string };

type FilterForm = {
  series_instance_uid: string;
  sop_instance_uid: string;
  operation: "" | VisualizationArtifactOperation;
  modality: "" | "CT" | "PT";
};

type GenerationForm = {
  series_instance_uid: string;
  operation: VisualizationArtifactOperation;
  slice_index: string;
  gaussian_sigma: string;
  window_center: string;
  window_width: string;
  lower_percentile: string;
  upper_percentile: string;
  dpi: string;
};

type GenerationStatus =
  | { status: "idle" }
  | { status: "submitting" }
  | { status: "success"; message: string }
  | { status: "error"; message: string };

type GenerationErrors = Partial<Record<keyof GenerationForm | "percentiles", string>>;

const emptyFilters: FilterForm = {
  series_instance_uid: "",
  sop_instance_uid: "",
  operation: "",
  modality: "",
};

const emptyGenerationForm: GenerationForm = {
  series_instance_uid: "",
  operation: "rescale",
  slice_index: "",
  gaussian_sigma: "",
  window_center: "",
  window_width: "",
  lower_percentile: "",
  upper_percentile: "",
  dpi: "",
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatNullableNumber(value: number | null): string {
  return value === null ? "Not available" : value.toLocaleString();
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value.toLocaleString()} B`;
  }
  return `${(value / 1024).toLocaleString(undefined, { maximumFractionDigits: 1 })} KB`;
}

function toRequestFilters(filters: FilterForm): VisualizationArtifactFilters {
  return {
    series_instance_uid: filters.series_instance_uid.trim() || undefined,
    sop_instance_uid: filters.sop_instance_uid.trim() || undefined,
    operation: filters.operation || undefined,
    modality: filters.modality || undefined,
  };
}

function artifactImageSrc(artifact: VisualizationArtifact): string {
  return new URL(artifact.image_url, `${apiBaseUrl}/`).toString();
}

function parseOptionalNumber(value: string): number | undefined {
  return value.trim() === "" ? undefined : Number(value);
}

function parseOptionalInteger(value: string): number | undefined {
  return value.trim() === "" ? undefined : Number(value);
}

export function validateGenerationForm(form: GenerationForm): GenerationErrors {
  const errors: GenerationErrors = {};
  if (form.series_instance_uid.trim() === "") {
    errors.series_instance_uid = "Series Instance UID is required.";
  }

  const sliceIndex = parseOptionalInteger(form.slice_index);
  if (
    sliceIndex !== undefined &&
    (!Number.isFinite(sliceIndex) || !Number.isInteger(sliceIndex) || sliceIndex < 0)
  ) {
    errors.slice_index = "Slice index must be a non-negative integer.";
  }

  if (form.operation === "gaussian") {
    const gaussianSigma = parseOptionalNumber(form.gaussian_sigma);
    if (gaussianSigma !== undefined && (!Number.isFinite(gaussianSigma) || gaussianSigma <= 0)) {
      errors.gaussian_sigma = "Gaussian sigma must be greater than zero.";
    }
  }

  if (form.operation === "rescale" || form.operation === "gaussian") {
    const windowCenter = parseOptionalNumber(form.window_center);
    if (windowCenter !== undefined && !Number.isFinite(windowCenter)) {
      errors.window_center = "Window center must be a finite number.";
    }

    const windowWidth = parseOptionalNumber(form.window_width);
    if (windowWidth !== undefined && (!Number.isFinite(windowWidth) || windowWidth <= 0)) {
      errors.window_width = "Window width must be greater than zero.";
    }
  }

  const dpi = parseOptionalInteger(form.dpi);
  if (dpi !== undefined && (!Number.isFinite(dpi) || !Number.isInteger(dpi) || dpi <= 0)) {
    errors.dpi = "DPI must be a positive integer.";
  }

  if (form.lower_percentile.trim() !== "" || form.upper_percentile.trim() !== "") {
    const lower = parseOptionalNumber(form.lower_percentile) ?? 1.0;
    const upper = parseOptionalNumber(form.upper_percentile) ?? 99.0;
    if (!Number.isFinite(lower) || !Number.isFinite(upper) || !(0 <= lower && lower < upper && upper <= 100)) {
      errors.percentiles = "Percentiles must satisfy 0 <= lower < upper <= 100.";
    }
  }

  return errors;
}

function assignOptionalNumber<T extends keyof VisualizationGenerationRequest>(
  request: VisualizationGenerationRequest,
  key: T,
  value: VisualizationGenerationRequest[T] | undefined,
) {
  if (value !== undefined) {
    Object.assign(request, { [key]: value });
  }
}

export function toGenerationRequest(form: GenerationForm): VisualizationGenerationRequest {
  const request: VisualizationGenerationRequest = {
    series_instance_uid: form.series_instance_uid.trim(),
    operation: form.operation,
  };

  assignOptionalNumber(request, "slice_index", parseOptionalInteger(form.slice_index));

  if (form.operation === "gaussian") {
    assignOptionalNumber(request, "gaussian_sigma", parseOptionalNumber(form.gaussian_sigma));
  }

  if (form.operation === "rescale" || form.operation === "gaussian") {
    assignOptionalNumber(request, "window_center", parseOptionalNumber(form.window_center));
    assignOptionalNumber(request, "window_width", parseOptionalNumber(form.window_width));
  }

  assignOptionalNumber(request, "lower_percentile", parseOptionalNumber(form.lower_percentile));
  assignOptionalNumber(request, "upper_percentile", parseOptionalNumber(form.upper_percentile));
  assignOptionalNumber(request, "dpi", parseOptionalInteger(form.dpi));

  return request;
}

function mergeArtifactById(
  artifacts: VisualizationArtifact[],
  generatedArtifact: VisualizationArtifact,
): VisualizationArtifact[] {
  const withoutGenerated = artifacts.filter((artifact) => artifact.id !== generatedArtifact.id);
  return [generatedArtifact, ...withoutGenerated];
}

function ArtifactMetadata({ artifact }: { artifact: VisualizationArtifact }) {
  const rows = [
    ["Modality", artifact.modality],
    ["Operation", artifact.operation],
    ["Slice index", artifact.slice_index.toLocaleString()],
    ["Value units", artifact.value_units],
    ["Rows x columns", `${artifact.rows.toLocaleString()} x ${artifact.columns.toLocaleString()}`],
    ["Display minimum", formatNullableNumber(artifact.display_minimum)],
    ["Display maximum", formatNullableNumber(artifact.display_maximum)],
    ["Window center", formatNullableNumber(artifact.window_center)],
    ["Window width", formatNullableNumber(artifact.window_width)],
    ["Colormap", artifact.colormap],
    ["File size", formatBytes(artifact.file_size_bytes)],
    ["SHA-256", artifact.file_sha256],
    ["Study UID", artifact.study_instance_uid],
    ["Series UID", artifact.series_instance_uid],
    ["SOP UID", artifact.sop_instance_uid],
  ];

  return (
    <dl className="artifact-metadata">
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd className={label.includes("UID") || label === "SHA-256" ? "mono" : undefined}>
            {value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function VisualizationArtifactWorkbench() {
  const [filterForm, setFilterForm] = useState<FilterForm>(emptyFilters);
  const [activeFilters, setActiveFilters] = useState<VisualizationArtifactFilters>({});
  const [state, setState] = useState<ArtifactState>({ status: "loading" });
  const [selectedArtifactId, setSelectedArtifactId] = useState<number | null>(null);
  const [failedImageIds, setFailedImageIds] = useState<Set<number>>(new Set());
  const [generationForm, setGenerationForm] = useState<GenerationForm>(emptyGenerationForm);
  const [generationErrors, setGenerationErrors] = useState<GenerationErrors>({});
  const [generationStatus, setGenerationStatus] = useState<GenerationStatus>({ status: "idle" });
  const latestRequestId = useRef(0);

  useEffect(() => {
    let ignore = false;
    const requestId = latestRequestId.current + 1;
    latestRequestId.current = requestId;
    setState({ status: "loading" });
    fetchVisualizationArtifacts(activeFilters)
      .then((artifacts) => {
        if (!ignore && latestRequestId.current === requestId) {
          setState({ status: "loaded", artifacts });
          setSelectedArtifactId((currentId) => {
            if (artifacts.length === 0) {
              return null;
            }
            if (currentId !== null && artifacts.some((artifact) => artifact.id === currentId)) {
              return currentId;
            }
            return artifacts[0].id;
          });
          setFailedImageIds(new Set());
        }
      })
      .catch(() => {
        if (!ignore && latestRequestId.current === requestId) {
          setState({
            status: "error",
            message: "Visualization artifacts could not be loaded.",
          });
          setSelectedArtifactId(null);
        }
      });

    return () => {
      ignore = true;
    };
  }, [activeFilters]);

  const selectedArtifact = useMemo(() => {
    if (state.status !== "loaded" || selectedArtifactId === null) {
      return null;
    }
    return state.artifacts.find((artifact) => artifact.id === selectedArtifactId) ?? null;
  }, [selectedArtifactId, state]);

  function updateFilter<K extends keyof FilterForm>(key: K, value: FilterForm[K]) {
    setFilterForm((current) => ({ ...current, [key]: value }));
  }

  function updateGenerationForm<K extends keyof GenerationForm>(key: K, value: GenerationForm[K]) {
    setGenerationForm((current) => ({ ...current, [key]: value }));
    setGenerationErrors((current) => ({ ...current, [key]: undefined }));
  }

  function applyFilters() {
    setActiveFilters(toRequestFilters(filterForm));
  }

  function clearFilters() {
    setFilterForm(emptyFilters);
    setActiveFilters({});
  }

  async function handleGenerateVisualization() {
    const errors = validateGenerationForm(generationForm);
    setGenerationErrors(errors);
    if (Object.keys(errors).length > 0) {
      setGenerationStatus({ status: "error", message: "Review the highlighted fields." });
      return;
    }

    setGenerationStatus({ status: "submitting" });
    try {
      const generatedArtifact = await generateVisualizationArtifact(toGenerationRequest(generationForm));
      const refreshedArtifacts = await fetchVisualizationArtifacts(activeFilters);
      const artifacts = mergeArtifactById(refreshedArtifacts, generatedArtifact);
      latestRequestId.current += 1;
      setState({ status: "loaded", artifacts });
      setSelectedArtifactId(generatedArtifact.id);
      setFailedImageIds(new Set());
      setGenerationStatus({
        status: "success",
        message: "Visualization artifact generated and selected.",
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Visualization artifact could not be generated.";
      setGenerationStatus({ status: "error", message });
    }
  }

  const sigmaDisabled = generationForm.operation !== "gaussian";
  const windowDisabled = generationForm.operation === "sobel";
  const isSubmitting = generationStatus.status === "submitting";

  return (
    <section aria-labelledby="artifact-workbench-heading" className="dashboard-section">
      <div className="section-heading">
        <div>
          <h2 id="artifact-workbench-heading">Visualization Artifacts</h2>
          <p>Registered PNG artifacts from analysis metadata and controlled generation.</p>
        </div>
        {state.status === "loaded" ? (
          <span>{state.artifacts.length.toLocaleString()} artifacts</span>
        ) : null}
      </div>

      <form
        className="artifact-filters"
        onSubmit={(event) => {
          event.preventDefault();
          applyFilters();
        }}
      >
        <label>
          Series Instance UID
          <input
            name="series_instance_uid"
            type="text"
            value={filterForm.series_instance_uid}
            onChange={(event) => updateFilter("series_instance_uid", event.target.value)}
          />
        </label>
        <label>
          SOP Instance UID
          <input
            name="sop_instance_uid"
            type="text"
            value={filterForm.sop_instance_uid}
            onChange={(event) => updateFilter("sop_instance_uid", event.target.value)}
          />
        </label>
        <label>
          Operation
          <select
            name="operation"
            value={filterForm.operation}
            onChange={(event) =>
              updateFilter("operation", event.target.value as FilterForm["operation"])
            }
          >
            <option value="">All</option>
            <option value="rescale">Rescale</option>
            <option value="gaussian">Gaussian</option>
            <option value="sobel">Sobel</option>
          </select>
        </label>
        <label>
          Modality
          <select
            name="modality"
            value={filterForm.modality}
            onChange={(event) => updateFilter("modality", event.target.value as FilterForm["modality"])}
          >
            <option value="">All</option>
            <option value="CT">CT</option>
            <option value="PT">PT</option>
          </select>
        </label>
        <div className="filter-actions">
          <button type="submit">Apply Filters</button>
          <button type="button" className="secondary-button" onClick={clearFilters}>
            Clear Filters
          </button>
        </div>
      </form>

      <form
        aria-labelledby="generate-visualization-heading"
        className="artifact-generation"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void handleGenerateVisualization();
        }}
      >
        <div className="generation-heading">
          <h3 id="generate-visualization-heading">Generate Visualization</h3>
          <p>Run the registered backend pipeline from a PostgreSQL-selected series UID.</p>
        </div>
        <div className="generation-grid">
          <label>
            Series Instance UID
            <input
              aria-describedby={
                generationErrors.series_instance_uid ? "generation-series-error" : undefined
              }
              name="generation_series_instance_uid"
              type="text"
              value={generationForm.series_instance_uid}
              onChange={(event) => updateGenerationForm("series_instance_uid", event.target.value)}
            />
            {generationErrors.series_instance_uid ? (
              <span className="field-error" id="generation-series-error">
                {generationErrors.series_instance_uid}
              </span>
            ) : null}
          </label>
          <label>
            Operation
            <select
              name="generation_operation"
              value={generationForm.operation}
              onChange={(event) =>
                updateGenerationForm("operation", event.target.value as VisualizationArtifactOperation)
              }
            >
              <option value="rescale">Rescale</option>
              <option value="gaussian">Gaussian</option>
              <option value="sobel">Sobel</option>
            </select>
          </label>
          <label>
            Slice index
            <input
              aria-describedby={generationErrors.slice_index ? "generation-slice-error" : undefined}
              min="0"
              name="slice_index"
              type="number"
              value={generationForm.slice_index}
              onChange={(event) => updateGenerationForm("slice_index", event.target.value)}
            />
            {generationErrors.slice_index ? (
              <span className="field-error" id="generation-slice-error">
                {generationErrors.slice_index}
              </span>
            ) : null}
          </label>
          <label>
            Gaussian sigma
            <input
              aria-describedby={
                generationErrors.gaussian_sigma ? "generation-sigma-error" : undefined
              }
              disabled={sigmaDisabled}
              min="0"
              name="gaussian_sigma"
              step="any"
              type="number"
              value={generationForm.gaussian_sigma}
              onChange={(event) => updateGenerationForm("gaussian_sigma", event.target.value)}
            />
            {generationErrors.gaussian_sigma ? (
              <span className="field-error" id="generation-sigma-error">
                {generationErrors.gaussian_sigma}
              </span>
            ) : null}
          </label>
          <label>
            Window center
            <input
              aria-describedby={
                generationErrors.window_center ? "generation-window-center-error" : undefined
              }
              disabled={windowDisabled}
              name="window_center"
              step="any"
              type="number"
              value={generationForm.window_center}
              onChange={(event) => updateGenerationForm("window_center", event.target.value)}
            />
            {generationErrors.window_center ? (
              <span className="field-error" id="generation-window-center-error">
                {generationErrors.window_center}
              </span>
            ) : null}
          </label>
          <label>
            Window width
            <input
              aria-describedby={generationErrors.window_width ? "generation-window-error" : undefined}
              disabled={windowDisabled}
              min="0"
              name="window_width"
              step="any"
              type="number"
              value={generationForm.window_width}
              onChange={(event) => updateGenerationForm("window_width", event.target.value)}
            />
            {generationErrors.window_width ? (
              <span className="field-error" id="generation-window-error">
                {generationErrors.window_width}
              </span>
            ) : null}
          </label>
          <label>
            Lower percentile
            <input
              aria-describedby={generationErrors.percentiles ? "generation-percentile-error" : undefined}
              max="100"
              min="0"
              name="lower_percentile"
              step="any"
              type="number"
              value={generationForm.lower_percentile}
              onChange={(event) => updateGenerationForm("lower_percentile", event.target.value)}
            />
          </label>
          <label>
            Upper percentile
            <input
              aria-describedby={generationErrors.percentiles ? "generation-percentile-error" : undefined}
              max="100"
              min="0"
              name="upper_percentile"
              step="any"
              type="number"
              value={generationForm.upper_percentile}
              onChange={(event) => updateGenerationForm("upper_percentile", event.target.value)}
            />
            {generationErrors.percentiles ? (
              <span className="field-error" id="generation-percentile-error">
                {generationErrors.percentiles}
              </span>
            ) : null}
          </label>
          <label>
            DPI
            <input
              aria-describedby={generationErrors.dpi ? "generation-dpi-error" : undefined}
              min="1"
              name="dpi"
              type="number"
              value={generationForm.dpi}
              onChange={(event) => updateGenerationForm("dpi", event.target.value)}
            />
            {generationErrors.dpi ? (
              <span className="field-error" id="generation-dpi-error">
                {generationErrors.dpi}
              </span>
            ) : null}
          </label>
        </div>
        <div className="generation-actions">
          <button disabled={isSubmitting} type="submit">
            {isSubmitting ? "Generating..." : "Generate Visualization"}
          </button>
          {generationStatus.status === "submitting" ? (
            <span role="status">Generating visualization artifact...</span>
          ) : null}
        </div>
        {generationStatus.status === "success" ? (
          <div className="notice success compact" role="status">
            {generationStatus.message}
          </div>
        ) : null}
        {generationStatus.status === "error" ? (
          <div className="notice error compact" role="alert">
            {generationStatus.message}
          </div>
        ) : null}
      </form>

      {state.status === "loading" ? (
        <div className="notice compact" role="status">
          Loading visualization artifacts...
        </div>
      ) : null}

      {state.status === "error" ? (
        <div className="notice error compact" role="alert">
          <strong>Artifact API is not available.</strong>
          <span>{state.message}</span>
        </div>
      ) : null}

      {state.status === "loaded" && state.artifacts.length === 0 ? (
        <div className="notice compact" role="status">
          No registered visualization artifacts match the current filters.
        </div>
      ) : null}

      {state.status === "loaded" && state.artifacts.length > 0 ? (
        <div className="artifact-workbench">
          <div className="artifact-list" aria-label="Visualization artifact list">
            {state.artifacts.map((artifact) => {
              const isSelected = artifact.id === selectedArtifactId;
              return (
                <button
                  aria-pressed={isSelected}
                  className={`artifact-list-item${isSelected ? " selected" : ""}`}
                  key={artifact.id}
                  type="button"
                  onClick={() => setSelectedArtifactId(artifact.id)}
                >
                  <span>
                    <strong>{artifact.modality}</strong>
                    <span>{artifact.operation}</span>
                  </span>
                  <span>Slice {artifact.slice_index.toLocaleString()}</span>
                  <span>{artifact.value_units}</span>
                  <span>
                    {artifact.rows.toLocaleString()} x {artifact.columns.toLocaleString()}
                  </span>
                  <time dateTime={artifact.created_at}>{formatDate(artifact.created_at)}</time>
                </button>
              );
            })}
          </div>

          <div className="artifact-detail" aria-live="polite">
            {selectedArtifact ? (
              <>
                <div className="artifact-image-shell">
                  {failedImageIds.has(selectedArtifact.id) ? (
                    <div className="notice error compact" role="alert">
                      The registered PNG image could not be loaded.
                    </div>
                  ) : (
                    <img
                      src={artifactImageSrc(selectedArtifact)}
                      alt={`${selectedArtifact.modality} ${selectedArtifact.operation} visualization artifact, slice ${selectedArtifact.slice_index}`}
                      onError={() =>
                        setFailedImageIds((current) => new Set(current).add(selectedArtifact.id))
                      }
                    />
                  )}
                </div>
                <ArtifactMetadata artifact={selectedArtifact} />
              </>
            ) : (
              <div className="notice compact" role="status">
                Select a visualization artifact to inspect its PNG and metadata.
              </div>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
