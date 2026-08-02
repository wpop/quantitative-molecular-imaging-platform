const DEFAULT_API_BASE_URL = "http://localhost:8000";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, "");

export type Overview = {
  studies_count: number;
  series_count: number;
  instances_count: number;
  modalities: string[];
  source_datasets: string[];
  source_subjects: string[];
  ingestion_jobs_count: number;
  latest_ingestion_status: string | null;
  latest_ingestion_started_at: string | null;
  latest_ingestion_completed_at: string | null;
};

export type ImagingStudy = {
  id: number;
  study_instance_uid: string;
  study_description: string;
  modality_summary: string;
  source_dataset: string;
  source_subject_id: string;
  series_count: number;
};

export type ImagingSeries = {
  id: number;
  study: number;
  study_instance_uid: string;
  series_instance_uid: string;
  modality: string;
  series_description: string;
  body_part_examined: string;
  number_of_instances: number;
};

export type AnalysisRun = {
  id: number;
  study: number;
  study_instance_uid: string;
  status: string;
  name: string;
  algorithm_name: string;
  algorithm_version: string;
  measurements_count: number;
  created_at: string;
};

export type MeasurementMetadata = {
  modality?: string;
  series_instance_uid?: string;
  [key: string]: unknown;
};

export type MeasurementResult = {
  id: number;
  analysis_run: number;
  analysis_run_id: number;
  algorithm_name: string;
  algorithm_version: string;
  study_instance_uid: string;
  name: string;
  value: string;
  unit: string;
  region_label: string;
  metadata: MeasurementMetadata;
  created_at: string;
};

export type VisualizationArtifactOperation = "rescale" | "gaussian" | "sobel";

export type VisualizationArtifact = {
  id: number;
  instance_id: number;
  sop_instance_uid: string;
  series_instance_uid: string;
  study_instance_uid: string;
  operation: VisualizationArtifactOperation;
  modality: string;
  slice_index: number;
  value_units: string;
  rows: number;
  columns: number;
  colormap: string;
  display_minimum: number | null;
  display_maximum: number | null;
  window_center: number | null;
  window_width: number | null;
  mime_type: string;
  file_size_bytes: number;
  file_sha256: string;
  created_at: string;
  updated_at: string;
  image_url: string;
};

export type VisualizationArtifactFilters = {
  series_instance_uid?: string;
  sop_instance_uid?: string;
  operation?: VisualizationArtifactOperation;
  modality?: string;
};

type DashboardData = {
  overview: Overview;
  studies: ImagingStudy[];
  series: ImagingSeries[];
  analysisRuns: AnalysisRun[];
  analysisResults: MeasurementResult[];
};

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    const body = await response.text();
    const detail = body ? ` ${body.slice(0, 240)}` : "";
    throw new Error(`Backend request failed: ${response.status} ${response.statusText}.${detail}`);
  }

  return (await response.json()) as T;
}

function buildArtifactPath(filters: VisualizationArtifactFilters): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) {
      query.set(key, value);
    }
  }
  const queryString = query.toString();
  return queryString ? `/api/v1/analysis/artifacts/?${queryString}` : "/api/v1/analysis/artifacts/";
}

export async function fetchVisualizationArtifacts(
  filters: VisualizationArtifactFilters = {},
): Promise<VisualizationArtifact[]> {
  return fetchJson<VisualizationArtifact[]>(buildArtifactPath(filters));
}

export async function fetchDashboardData(): Promise<DashboardData> {
  const [overview, studies, series, analysisRuns, analysisResults] = await Promise.all([
    fetchJson<Overview>("/api/v1/overview/"),
    fetchJson<ImagingStudy[]>("/api/v1/imaging/studies/"),
    fetchJson<ImagingSeries[]>("/api/v1/imaging/series/"),
    fetchJson<AnalysisRun[]>("/api/v1/analysis/runs/"),
    fetchJson<MeasurementResult[]>("/api/v1/analysis/results/"),
  ]);

  return {
    overview,
    studies,
    series,
    analysisRuns,
    analysisResults,
  };
}

export { apiBaseUrl };
