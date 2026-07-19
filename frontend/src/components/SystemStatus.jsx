import React, { useState, useEffect } from 'react';
import { getHealth } from '../api/system';
import { Database, HardDrive, Cpu } from 'lucide-react';

/**
 * Fetches /api/system/health and shows only the 4 real fields:
 *   status, database, redis, models_exist
 * Skips rendering entirely while loading or on fetch error.
 */
export default function SystemStatus() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => {}); // silently hide if endpoint is unreachable
  }, []);

  // Don't render until we have a response
  if (!health) return null;

  const dot = (ok) =>
    ok
      ? 'bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.7)]'
      : 'bg-red-400 shadow-[0_0_6px_rgba(248,113,113,0.7)]';

  const items = [
    {
      label: 'Database',
      ok: health.database === 'healthy',
      icon: <Database size={12} />,
    },
    {
      label: 'Cache',
      ok: health.redis === 'healthy',
      icon: <HardDrive size={12} />,
    },
    {
      label: 'Models',
      ok: health.models_exist === true,
      icon: <Cpu size={12} />,
    },
  ];

  return (
    <div className="px-4 pb-4">
      <div className="bg-black/20 border border-white/10 rounded-xl p-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-semibold text-text-secondary uppercase tracking-widest">
            System
          </span>
          <span
            className={`text-[10px] font-bold uppercase ${
              health.status === 'healthy' ? 'text-green-400' : 'text-yellow-400'
            }`}
          >
            {health.status}
          </span>
        </div>
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full shrink-0 ${dot(item.ok)}`} />
            <span className="text-text-secondary">{item.icon}</span>
            <span className="text-xs text-text-secondary flex-1">{item.label}</span>
            <span
              className={`text-[10px] font-medium ${
                item.ok ? 'text-green-400' : 'text-red-400'
              }`}
            >
              {item.ok ? 'OK' : 'DOWN'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
