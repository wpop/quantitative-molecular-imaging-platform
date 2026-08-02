import { useEffect, useMemo, useState } from "react";

import {
  apiBaseUrl,
  fetchVisualizationArtifacts,
  type VisualizationArtifact,
  type VisualizationArtifactFilters,
  type VisualizationArtifactOperation,
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

const emptyFilters: FilterForm = {
  series_instance_uid: "",
  sop_instance_uid: "",
  operation: "",
  modality: "",
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatNumber(value: number | null): string {
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

function ArtifactMetadata({ artifact }: { artifact: VisualizationArtifact }) {
  const rows = [
    ["Modality", artifact.modality],
    ["Operation", artifact.operation],
    ["Slice index", artifact.slice_index.toLocaleString()],
    ["Value units", artifact.value_units],
    ["Rows x columns", `${artifact.rows.toLocaleString()} x ${artifact.columns.toLocaleString()}`],
    ["Display minimum", formatNumber(artifact.display_minimum)],
    ["Display maximum", formatNumber(artifact.display_maximum)],
    ["Window center", formatNumber(artifact.window_center)],
    ["Window width", formatNumber(artifact.window_width)],
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

  useEffect(() => {
    let ignore = false;
    setState({ status: "loading" });
    fetchVisualizationArtifacts(activeFilters)
      .then((artifacts) => {
        if (!ignore) {
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
        if (!ignore) {
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

  function applyFilters() {
    setActiveFilters(toRequestFilters(filterForm));
  }

  function clearFilters() {
    setFilterForm(emptyFilters);
    setActiveFilters({});
  }

  return (
    <section aria-labelledby="artifact-workbench-heading" className="dashboard-section">
      <div className="section-heading">
        <div>
          <h2 id="artifact-workbench-heading">Visualization Artifacts</h2>
          <p>Registered PNG artifacts from read-only analysis metadata.</p>
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
