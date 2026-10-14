import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceArea,
  ReferenceLine,
  Brush,
} from "recharts";
import type { Series, Flaw } from "../../types";
import { Empty } from "../ui";
export function chartData(series: Series) {
  const rows = new Map<
    number,
    { time: number; reference?: number | null; participant?: number | null }
  >();
  for (const role of ["reference", "participant"] as const)
    for (const p of series[role]) {
      const item = rows.get(p.time_seconds) || { time: p.time_seconds };
      item[role] = p.value;
      rows.set(p.time_seconds, item);
    }
  return [...rows.values()].sort((a, b) => a.time - b.time);
}
export default function FeatureChart({
  name,
  series,
  flaws,
  current,
  onSeek,
}: {
  name: string;
  series: Series;
  flaws: Flaw[];
  current: number;
  onSeek: (time: number) => void;
}) {
  const data = chartData(series);
  if (!data.some((p) => p.reference != null || p.participant != null))
    return (
      <Empty
        title={`${name.replaceAll("_", " ")} unavailable`}
        description="No measurements were supplied by the analysis provider."
      />
    );
  return (
    <div className="feature-chart">
      <div className="row between">
        <h3>{name.replaceAll("_", " ")}</h3>
        <span className="muted tiny">
          {series.unit} ·{" "}
          {series.time_axis === "participant_aligned"
            ? "Aligned to participant time"
            : "Independent recording clocks"}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={270}>
        <LineChart
          data={data}
          onClick={(state) => {
            const time = Number(state?.activeLabel);
            if (Number.isFinite(time)) onSeek(time);
          }}
          margin={{ left: 0, right: 15, top: 15, bottom: 15 }}
        >
          <CartesianGrid
            stroke="#282c39"
            strokeDasharray="3 5"
            vertical={false}
          />
          <XAxis
            dataKey="time"
            type="number"
            domain={["dataMin", "dataMax"]}
            stroke="#838a9e"
            tickFormatter={(v) => `${Number(v).toFixed(0)}s`}
            label={{
              value: "Time (seconds)",
              position: "insideBottom",
              offset: -8,
              fill: "#838a9e",
            }}
          />
          <YAxis
            stroke="#838a9e"
            width={48}
            tickFormatter={(v) =>
              Number(v).toFixed(Math.abs(Number(v)) < 1 ? 2 : 0)
            }
          />
          <Tooltip
            contentStyle={{
              background: "#191d29",
              border: "1px solid #34394b",
              borderRadius: 8,
            }}
            labelFormatter={(v) => `${Number(v).toFixed(2)} seconds`}
          />
          <Legend verticalAlign="top" />
          <Line
            type="linear"
            data={data.filter((row) => row.reference !== undefined)}
            dataKey="reference"
            name="Reference"
            stroke="#6ac9b6"
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
          <Line
            type="linear"
            data={data.filter((row) => row.participant !== undefined)}
            dataKey="participant"
            name="Participant"
            stroke="#a89af0"
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
          {series.time_axis === "participant_aligned" &&
            flaws.map((f) => (
              <ReferenceArea
                key={f.id}
                x1={f.start_seconds}
                x2={f.end_seconds}
                fill="#e47f91"
                fillOpacity={0.08}
              />
            ))}
          <ReferenceLine x={current} stroke="#ded5ff" strokeDasharray="3 3" />
          {series.time_axis === "participant_aligned" && (
            <Brush
              dataKey="time"
              height={20}
              stroke="#68618d"
              fill="#131720"
              travellerWidth={8}
              tickFormatter={(v) => `${Number(v).toFixed(0)}s`}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
