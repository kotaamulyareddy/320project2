import React, { useState, useEffect } from 'react';
import LiveCanvasOverlay from './components/LiveCanvasOverlay';
import EventFeed from './components/EventFeed';
import MetricsDashboard from './components/MetricsDashboard';
import { useWebSocket } from './hooks/useWebSocket';

interface DetectionEvent {
  type: string;
  camera_id: string;
  frame_id: string;
  detection_id: string;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  class_id: number;
  class_name: string;
  confidence: number;
  inference_time_ms: number;
}

interface FrameMetadata {
  type: string;
  camera_id: string;
  frame_id: string;
  frame_number: number;
  timestamp: string;
  width: number;
  height: number;
  detection_count: number;
  anomaly_score: number | null;
  is_anomaly: boolean;
  processing_time_ms: number;
  inference_time_ms: number;
}

interface Alert {
  type: string;
  alert_id: string;
  camera_id: string;
  frame_id: string | null;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  timestamp: string;
}

interface Telemetry {
  type: string;
  component: string;
  instance_id: string;
  metric_name: string;
  metric_value: number;
  metric_unit: string;
  timestamp: string;
}

const App: React.FC = () => {
  const [videoElement, setVideoElement] = useState<HTMLVideoElement | null>(null);
  const [boxes, setBoxes] = useState<DetectionEvent[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<Telemetry[]>([]);
  const [fps, setFps] = useState(0);
  const [latency, setLatency] = useState(0);
  const [connected, setConnected] = useState(false);

  const { sendMessage, lastMessage } = useWebSocket('ws://localhost:8000/api/v1/stream/ws');

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      try {
        const message = JSON.parse(lastMessage);
        switch (message.type) {
          case 'detection_event':
            setBoxes(prev => [...prev.slice(-99), message]);
            break;
          case 'frame_metadata':
            // Update FPS and latency
            setFps(Math.round(1000 / (message.processing_time_ms || 1)));
            setLatency(Math.round(message.inference_time_ms));
            break;
          case 'alert':
            setEvents(prev => [...prev.slice(-49), { ...message, timestamp: new Date().toLocaleTimeString() }]);
            break;
          case 'telemetry':
            setMetrics(prev => [...prev.slice(-99), message]);
            break;
          case 'heartbeat':
            setConnected(true);
            break;
        }
      } catch (e) {
        console.error('Failed to parse message:', e);
      }
    }
  }, [lastMessage]);

  // Handle video element ref
  const handleVideoRef = (el: HTMLVideoElement | null) => {
    setVideoElement(el);
    if (el) {
      el.play().catch(console.error);
    }
  };

  // Simulate camera feed (in production, this would be an actual RTSP/WebRTC stream)
  useEffect(() => {
    if (videoElement) {
      // For demo purposes, we'll use a placeholder
      // In production: navigator.mediaDevices.getUserMedia or RTSP stream
    }
  }, [videoElement]);

  // Subscribe to all events on connect
  useEffect(() => {
    if (connected) {
      sendMessage({
        type: 'subscribe',
        camera_ids: [],
        event_types: ['detection_event', 'frame_metadata', 'alert', 'telemetry'],
      });
    }
  }, [connected, sendMessage]);

  return (
    <div className="min-h-screen bg-dark-950">
      {/* Header */}
      <header className="bg-dark-900 border-b border-gray-800 px-6 py-4">
        <div className="max-w-full mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Edge Analytics Pipeline</h1>
              <p className="text-sm text-gray-400">Real-time Video Analytics & Anomaly Detection</p>
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div className={`w-3 h-3 rounded-full ${connected ? 'bg-primary-500 animate-pulse' : 'bg-red-500'}`} />
            <span className="text-sm text-gray-300">{connected ? 'Connected' : 'Disconnected'}</span>
            <div className="flex items-center gap-4 text-sm">
              <span className="text-gray-400">FPS:</span>
              <span className="text-primary-400 font-mono">{fps}</span>
              <span className="text-gray-400">Latency:</span>
              <span className="text-yellow-400 font-mono">{latency}ms</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-full mx-auto">
          {/* Video Feed Panel */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-dark-900 rounded-xl border border-gray-800 overflow-hidden">
              <div className="p-4 border-b border-gray-800 flex items-center justify-between">
                <h2 className="text-lg font-semibold">Live Camera Feed</h2>
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                  <span>LIVE</span>
                </div>
              </div>
              <div className="relative aspect-video bg-black">
                <video
                  ref={handleVideoRef}
                  className="w-full h-full object-contain"
                  muted
                  playsInline
                />
                <LiveCanvasOverlay
                  videoElement={videoElement}
                  boxes={boxes}
                  width={videoElement?.videoWidth || 1280}
                  height={videoElement?.videoHeight || 720}
                />
                {!videoElement && (
                  <div className="absolute inset-0 flex items-center justify-center text-gray-500">
                    <div className="text-center">
                      <svg className="w-16 h-16 mx-auto mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                      <p>Connecting to camera stream...</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Event Feed */}
            <div className="bg-dark-900 rounded-xl border border-gray-800 overflow-hidden">
              <div className="p-4 border-b border-gray-800">
                <h2 className="text-lg font-semibold">Recent Events</h2>
              </div>
              <EventFeed events={events} />
            </div>
          </div>

          {/* Sidebar - Metrics & Controls */}
          <div className="space-y-6">
            <MetricsDashboard metrics={metrics} />

            {/* Camera Controls */}
            <div className="bg-dark-900 rounded-xl border border-gray-800 p-4">
              <h3 className="text-lg font-semibold mb-4">Camera Controls</h3>
              <div className="space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input type="checkbox" className="w-4 h-4 rounded border-gray-700 bg-dark-800 text-primary-500 focus:ring-primary-500" />
                  <span className="text-sm">Show Bounding Boxes</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input type="checkbox" className="w-4 h-4 rounded border-gray-700 bg-dark-800 text-primary-500 focus:ring-primary-500" checked />
                  <span className="text-sm">Show Confidence Scores</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input type="checkbox" className="w-4 h-4 rounded border-gray-700 bg-dark-800 text-primary-500 focus:ring-primary-500" />
                  <span className="text-sm">Show Anomaly Alerts</span>
                </label>
                <div className="pt-2 border-t border-gray-800">
                  <label className="block text-sm text-gray-400 mb-2">Confidence Threshold</label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value="0.5"
                    className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-primary-500"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;