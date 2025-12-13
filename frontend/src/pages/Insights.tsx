import React, { useEffect, useMemo, useState } from 'react';

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api';

type TimeRange = '1d' | '7d' | '30d' | 'all';

type InsightsResponse = {
  queryVolume: {
    total: number;
    avgPerDay: number;
    changePercent: number;
  };
  satisfactionRate: {
    helpfulCount: number;
    notHelpfulCount: number;
    percent: number;
  };
  avgQualityScore: number;
  topDocuments: Array<{
    documentId: string;
    filename: string;
    citationCount: number;
    avgQualityScore: number;
  }>;
  citationAccuracy: number;
  errorPatterns: Record<string, number>;
};

const cardStyle: React.CSSProperties = {
  background: 'rgba(255, 255, 255, 0.02)',
  border: '1px solid rgba(255, 255, 255, 0.06)',
  borderRadius: 'var(--radius-lg)',
  padding: 'var(--space-4)',
};

const gridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
  gap: 'var(--space-4)',
};

const sectionStyle: React.CSSProperties = {
  marginTop: 'var(--space-6)',
};

const labelStyle: React.CSSProperties = {
  fontSize: 'var(--font-size-sm)',
  color: 'var(--color-text-secondary)',
  margin: 0,
};

const valueStyle: React.CSSProperties = {
  fontSize: 'var(--font-size-2xl)',
  fontWeight: 600,
  color: 'var(--color-text-primary)',
  margin: 'var(--space-2) 0 0 0',
};

const Insights: React.FC = () => {
  const [timeRange, setTimeRange] = useState<TimeRange>('7d');
  const [data, setData] = useState<InsightsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(
          `${apiBaseUrl}/insights?time_range=${encodeURIComponent(timeRange)}`,
          { signal: controller.signal },
        );
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          const msg =
            typeof body?.message === 'string'
              ? body.message
              : `Failed to load insights (${res.status})`;
          throw new Error(msg);
        }
        const json = (await res.json()) as InsightsResponse;
        setData(json);
      } catch (e) {
        if (e instanceof DOMException && e.name === 'AbortError') return;
        setError(e instanceof Error ? e.message : 'Failed to load insights');
        setData(null);
      } finally {
        setLoading(false);
      }
    };

    void run();

    return () => controller.abort();
  }, [timeRange]);

  const sortedPatterns = useMemo(() => {
    const patterns = data?.errorPatterns ?? {};
    return Object.entries(patterns).sort((a, b) => b[1] - a[1]);
  }, [data]);

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-4)' }}>
        <div>
          <p style={labelStyle}>Insights</p>
          <p style={{ margin: 0, color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
            Aggregated feedback + evaluation metrics
          </p>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <span style={labelStyle}>Range</span>
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as TimeRange)}
            aria-label="Time range"
            style={{
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              color: 'var(--color-text-primary)',
              borderRadius: 'var(--radius-sm)',
              padding: '6px 10px',
            }}
          >
            <option value="1d">Last 24h</option>
            <option value="7d">Last 7d</option>
            <option value="30d">Last 30d</option>
            <option value="all">All time</option>
          </select>
        </label>
      </div>

      {error && (
        <div
          role="alert"
          style={{
            ...cardStyle,
            borderColor: 'rgba(255, 84, 89, 0.3)',
            background: 'rgba(255, 84, 89, 0.08)',
            color: 'var(--color-error)',
          }}
        >
          {error}
        </div>
      )}

      {loading && (
        <div style={{ ...cardStyle, color: 'var(--color-text-secondary)' }}>Loading…</div>
      )}

      {data && !loading && (
        <>
          <div style={gridStyle}>
            <div style={cardStyle}>
              <p style={labelStyle}>Total Feedback</p>
              <p style={valueStyle}>{data.queryVolume.total}</p>
              <p style={{ ...labelStyle, marginTop: 'var(--space-2)' }}>
                Avg/day: {data.queryVolume.avgPerDay.toFixed(1)}
              </p>
            </div>

            <div style={cardStyle}>
              <p style={labelStyle}>Satisfaction</p>
              <p style={valueStyle}>{(data.satisfactionRate.percent * 100).toFixed(1)}%</p>
              <p style={{ ...labelStyle, marginTop: 'var(--space-2)' }}>
                👍 {data.satisfactionRate.helpfulCount} / 👎 {data.satisfactionRate.notHelpfulCount}
              </p>
            </div>

            <div style={cardStyle}>
              <p style={labelStyle}>Avg Quality Score</p>
              <p style={valueStyle}>{data.avgQualityScore.toFixed(2)}</p>
              <p style={{ ...labelStyle, marginTop: 'var(--space-2)' }}>Range: 0–1</p>
            </div>

            <div style={cardStyle}>
              <p style={labelStyle}>Citation Accuracy</p>
              <p style={valueStyle}>{(data.citationAccuracy * 100).toFixed(1)}%</p>
            </div>
          </div>

          <div style={sectionStyle}>
            <h2 style={{ margin: 0, fontSize: 'var(--font-size-lg)' }}>Error patterns</h2>
            <div style={{ ...cardStyle, marginTop: 'var(--space-3)' }}>
              {sortedPatterns.length === 0 ? (
                <p style={{ ...labelStyle, margin: 0 }}>No patterns yet.</p>
              ) : (
                <ul style={{ margin: 0, paddingLeft: '18px' }}>
                  {sortedPatterns.slice(0, 20).map(([key, count]) => (
                    <li key={key} style={{ color: 'var(--color-text-secondary)', margin: '4px 0' }}>
                      <span style={{ color: 'var(--color-text-primary)' }}>{key}</span>: {count}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
};

export default Insights;
