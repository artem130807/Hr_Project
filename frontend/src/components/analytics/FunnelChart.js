import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

export default function FunnelChart({ data }) {
    if (!data || data.length === 0) {
        return (
            <div className="mb-8">
                <h2 className="text-xl font-semibold mb-2 text-slate-900">Воронка найма</h2>
                <p className="text-slate-500">Нет данных для отображения</p>
            </div>
        );
    }

    return (
        <div className="mb-8" data-testid="funnel-chart">
            <h2 className="text-xl font-semibold mb-2 text-slate-900">Воронка найма</h2>
            <ResponsiveContainer width="100%" height={500}>
                <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 150 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                        dataKey="name"
                        interval={0}
                        angle={-45}
                        textAnchor="end"
                        height={150}
                        style={{ fontSize: "12px" }}
                    />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#4f46e5" name="Кандидаты" />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}
