import { useEffect, useMemo, useState } from "react";

import {
  type AnalysisRun,
  type ImagingSeries,
  type MeasurementResult,
  type Overview,
  apiBaseUrl,
  fetchDashboardData,
} from "./api/client";

type DashboardState =
  | { status: "loading" }
  | { status: "loaded"; data: Awaited<ReturnType<typeof fetchDashboardData>> }
  | { status: "error"; message: string };

function formatList(values: string[]): string {
  return values.length > 0 ? values.join(", ") : "None";
}

function formatNullable(value: string | null | undefined): string {
  return value && value.length > 0 ? value : "Not available";
}

function OverviewCards({ overview }: { overview: Overview }) {
  const cards = [
    { label: "Studies", value: overview.studies_count.toLocaleString() },
    { label: "Series", value: overview.series_count.toLocaleString() },
    { label: "Instances", value: overview.instances_count.toLocaleString() },
    { label: "Modalities", value: formatList(overview.modalities) },
    { label: "Latest ingestion", value: formatNullable(overview.latest_ingestion_status) },
  ];

  return (
    <section aria-labelledby="overview-heading" className="dashboard-section">
      <div className="section-heading">
        <h2 id="overview-heading">Overview</h2>
      </div>
      <div className="overview-grid">
        {cards.map((card) => (
          <article className="metric-card" key={card.label}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
          </article>
        ))}
      </div>
    </section>
  );
}

function ImagingSeriesTable({ series }: { series: ImagingSeries[] }) {
  return (
    <section aria-labelledby="series-heading" className="dashboard-section">
      <div className="section-heading">
        <h2 id="series-heading">Imaging Series</h2>
        <span>{series.length.toLocaleString()} records</span>
      </div>
      <div className="table-shell">
        <table>
          <thead>
            <tr>
              <th>Modality</th>
              <th>SeriesInstanceUID</th>
              <th>Instances</th>
              <th>Body part</th>
            </tr>
          </thead>
          <tbody>
            {series.map((item) => (
              <tr key={item.id}>
                <td>
                  <span className="tag">{item.modality}</span>
                </td>
                <td className="mono">{item.series_instance_uid}</td>
                <td>{item.number_of_instances.toLocaleString()}</td>
                <td>{formatNullable(item.body_part_examined)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function latestRunLabel(runs: AnalysisRun[]): string {
  if (runs.length === 0) {
    return "No analysis runs";
  }
  const run = runs[0];
  return `${run.algorithm_name} ${run.algorithm_version} - ${run.status}`;
}

function AnalysisResultsTable({
  results,
  runs,
}: {
  results: MeasurementResult[];
  runs: AnalysisRun[];
}) {
  return (
    <section aria-labelledby="analysis-heading" className="dashboard-section">
      <div className="section-heading">
        <div>
          <h2 id="analysis-heading">Analysis Results</h2>
          <p>{latestRunLabel(runs)}</p>
        </div>
        <span>{results.length.toLocaleString()} measurements</span>
      </div>
      <div className="table-shell">
        <table>
          <thead>
            <tr>
              <th>Algorithm</th>
              <th>Measurement</th>
              <th>Value</th>
              <th>Unit</th>
              <th>Region</th>
              <th>Modality</th>
            </tr>
          </thead>
          <tbody>
            {results.map((result) => (
              <tr key={result.id}>
                <td>{result.algorithm_name}</td>
                <td>{result.name}</td>
                <td>{result.value}</td>
                <td>{result.unit}</td>
                <td className="mono">{formatNullable(result.region_label)}</td>
                <td>{formatNullable(result.metadata.modality)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SafetyNote() {
  return (
    <section aria-labelledby="safety-heading" className="safety-note">
      <h2 id="safety-heading">Safety Note</h2>
      <p>
        This dashboard displays metadata only. It does not load DICOM pixels, does not expose raw
        DICOM files, and does not perform image diagnosis.
      </p>
    </section>
  );
}

export function App() {
  const [state, setState] = useState<DashboardState>({ status: "loading" });

  useEffect(() => {
    let ignore = false;
    fetchDashboardData()
      .then((data) => {
        if (!ignore) {
          setState({ status: "loaded", data });
        }
      })
      .catch((error: unknown) => {
        if (!ignore) {
          const message = error instanceof Error ? error.message : "Unknown backend error.";
          setState({ status: "error", message });
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  const content = useMemo(() => {
    if (state.status === "loading") {
      return <div className="notice">Loading metadata from {apiBaseUrl}...</div>;
    }

    if (state.status === "error") {
      return (
        <div className="notice error">
          <strong>Backend is not available.</strong>
          <span>{state.message}</span>
        </div>
      );
    }

    return (
      <>
        <OverviewCards overview={state.data.overview} />
        <ImagingSeriesTable series={state.data.series} />
        <AnalysisResultsTable
          results={state.data.analysisResults}
          runs={state.data.analysisRuns}
        />
        <SafetyNote />
      </>
    );
  }, [state]);

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Metadata-only research demo</p>
          <h1>Quantitative Molecular Imaging Platform</h1>
          <p>
            A compact dashboard for PostgreSQL imaging metadata, ingestion status, and stored
            quantitative analysis results.
          </p>
        </div>
        <div className="api-pill">
          <span>API</span>
          <strong>{apiBaseUrl}</strong>
        </div>
      </header>
      {content}
    </main>
  );
}
