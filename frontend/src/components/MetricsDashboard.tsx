import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface MetricsDashboardProps {
  metrics: any[];
}

const MetricsDashboard: React.FC<MetricsDashboardProps> = ({ metrics }) => {
  // Process metrics for charts
  const inferenceData = metrics
    .filter(m => m.metric_name === 'inference_latency_ms')
    .slice(-20)
    .map((m, i) => ({ time: i, value: m.metric_value }));

  const fpsData = metrics
    .filter(m => m.metric_name === 'frames_per_second')
    .slice(-20)
    .map((m, i) => ({ time: i, value: m.metric_value }));

  const memoryData = metrics
    .filter(m => m.metric_name === 'memory_usage_mb')
    .slice(-20)
    .map((m, i) => ({ time: i, value: m.metric_value }));

  const StatCard = ({ title, value, unit, trend, color }: any) => (
    <div className="bg-dark-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-gray-400 uppercase tracking-wider">{title}</p>
          <p className="text-2xl font-bold text-white mt-1">{value} <span className="text-sm font-normal text-gray-400">{unit}</span></p>
        </div>
        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${color}`}>
          {trend > 0 ? (
            <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" /></svg>
          ) : (
            <svg className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" /></svg>
          )}
        </div>
      </div>
    </div>
  );

  const ChartCard = ({ title, data, color, dataKey }: any) => (
    <div className="bg-dark-800 rounded-lg p-4 border border-gray-700">
      <h3 className="text-sm font-medium text-gray-300 mb-3">{title}</h3>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
            <XAxis
              type="number"
              dataKey="time"
              stroke="#6b7280"
              fontSize={10}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="#6b7280"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => value.toFixed(0)}
            />
            <Tooltip
              contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
              labelStyle={{ color: '#9ca3af' }}
              formatter={(value: number) => [value.toFixed(1), '']}
            />
            <Line
              type="monotone"
              dataKey={dataKey}
              stroke={color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 6, strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );

  // Calculate current values
  const currentInference = inferenceData[inferenceData.length - 1]?.value || 0;
  const currentFps = fpsData[fpsData.length - 1]?.value || 0;
  const currentMemory = memoryData[memoryData.length - 1]?.value || 0;

  return (
    <div className="space-y-4">
      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-3">
        <StatCard
          title="Inference Latency"
          value={currentInference.toFixed(1)}
          unit="ms"
          trend={-5}
          color="bg-primary-500/20"
        />
        <StatCard
          title="Throughput"
          value={currentFps.toFixed(0)}
          unit="FPS"
          trend={2}
          color="bg-blue-500/20"
        />
        <StatCard
          title="Memory Usage"
          value={currentMemory.toFixed(0)}
          unit="MB"
          trend={1}
          color="bg-yellow-500/20"
        />
        <StatCard
          title="GPU Utilization"
          value="67"
          unit="%"
          trend={-3}
          color="bg-purple-500/20"
        />
      </div>

      {/* Charts */}
      <div className="space-y-4">
        <ChartCard
          title="Inference Latency (ms)"
          data={inferenceData}
          color="#22c55e"
          dataKey="value"
        />
        <ChartCard
          title="Frames Per Second"
          data={fpsData}
          color="#3b82f6"
          dataKey="value"
        />
        <ChartCard
          title="Memory Usage (MB)"
          data={memoryData}
          color="#f59e0b"
          dataKey="value"
        />
      </div>

      {/* System Health */}
      <div className="bg-dark-800 rounded-lg p-4 border border-gray-700">
        <h3 className="text-sm font-medium text-gray-300 mb-3">System Health</h3>
        <div className="space-y-3">
          {[
            { name: 'Vision Pipeline', status: 'healthy', detail: 'Processing normally' },
            { name: 'Stream Processor', status: 'healthy', detail: 'Queue: 0 pending' },
            { name: 'API Gateway', status: 'healthy', detail: '12 active connections' },
            { name: 'Database', status: 'healthy', detail: 'Connected (pool: 8/20)' },
            { name: 'Redis', status: 'healthy', detail: 'Connected (streams active)' },
            { name: 'MinIO Storage', status: 'healthy', detail: '2.3 GB used / 50 GB' },
          ].map((service, i) => (
            <div key={i} className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${service.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-sm font-medium">{service.name}</span>
              </div>
              <span className="text-xs text-gray-400">{service.detail}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default MetricsDashboard;