import React from 'react';

const Candidates: React.FC = () => {
  return (
    <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg">
      <h3 className="text-2xl font-bold text-white mb-4">Candidate Pool</h3>
      <p className="text-gray-400">Search and manage verified candidate profiles.</p>
      <div className="mt-8 flex items-center justify-center h-64 border-2 border-dashed border-gray-700 rounded-lg text-gray-500">
        Candidate Management Module coming soon (TASK-006)
      </div>
    </div>
  );
};

export default Candidates;
