import React from 'react';

interface EventFeedProps {
  events: any[];
}

const EventFeed: React.FC<EventFeedProps> = ({ events }) => {
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-400 bg-red-500/20 border-red-500/30';
      case 'high': return 'text-orange-400 bg-orange-500/20 border-orange-500/30';
      case 'medium': return 'text-yellow-400 bg-yellow-500/20 border-yellow-500/30';
      case 'low': return 'text-blue-400 bg-blue-500/20 border-blue-500/30';
      default: return 'text-gray-400 bg-gray-500/20 border-gray-500/30';
    }
  };

  const getIcon = (type: string) => {
    switch (type) {
      case 'detection_event':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      case 'alert':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        );
      default:
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
    }
  };

  if (events.length === 0) {
    return (
      <div className="p-8 text-center text-gray-500">
        <svg className="w-12 h-12 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="text-sm">No events yet</p>
        <p className="text-xs mt-1">Events will appear here when detected</p>
      </div>
    );
  }

  return (
    <div className="max-h-80 overflow-y-auto scrollbar-hide">
      {events
        .slice()
        .reverse()
        .map((event, index) => (
          <div
            key={`${event.type}-${event.alert_id || event.detection_id || event.frame_id}-${index}`}
            className="border-b border-gray-800 last:border-0 p-3 hover:bg-gray-800/50 transition-colors"
          >
            <div className="flex items-start gap-3">
              <div className={`flex items-center justify-center w-8 h-8 rounded-lg border ${getSeverityColor(event.severity || 'info')}`}>
                {getIcon(event.type)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <h4 className="text-sm font-medium text-white truncate">
                    {event.title || event.class_name || event.alert_type || 'Event'}
                  </h4>
                  <span className={`px-2 py-0.5 text-xs rounded-full border ${getSeverityColor(event.severity || 'info')}`}>
                    {event.severity || event.type}
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-1 truncate">
                  {event.message || `Confidence: ${event.confidence ? (event.confidence * 100).toFixed(0) : 'N/A'}%`}
                </p>
                <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                  <span>{event.camera_id?.slice(0, 8)}...</span>
                  <span>•</span>
                  <span>{event.timestamp || new Date().toLocaleTimeString()}</span>
                  {event.inference_time_ms && (
                    <>
                      <span>•</span>
                      <span>{event.inference_time_ms.toFixed(1)}ms</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
    </div>
  );
};

export default EventFeed;