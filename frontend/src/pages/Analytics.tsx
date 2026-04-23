import React from 'react';

const Analytics: React.FC = () => {
  return (
    <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg">
      <h3 className="text-2xl font-bold text-white mb-4">Performance Analytics</h3>
      <p className="text-gray-400">System-wide metrics and performance tracking.</p>
      <div className="mt-8 flex items-center justify-center h-64 border-2 border-dashed border-gray-700 rounded-lg text-gray-500">
        Analytics Module coming soon (TASK-023)
      </div>
    </div>
  );
};

export default Analytics;