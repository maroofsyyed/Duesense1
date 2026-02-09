import React, { useEffect, useState } from 'react';
import { getHealth } from '../api';
import { AlertCircle, CheckCircle, Loader2 } from 'lucide-react';

export const HealthCheck = () => {
  const [health, setHealth] = useState({ status: 'checking' });
  const [isVisible, setIsVisible] = useState(false);

  const checkHealth = async () => {
    // Note: Empty REACT_APP_BACKEND_URL means same-origin deployment (valid configuration)
    // Only show warning if frontend is deployed separately without backend URL configured
    
    try {
      const response = await getHealth();
      if (response.status === 200) {
        const data = response.data;
        setHealth({
          status: 'healthy',
          message: data.message || 'Backend is connected',
          lastChecked: new Date(),
        });
        // Hide banner after 3 seconds if healthy
        setTimeout(() => setIsVisible(false), 3000);
      } else {
        setHealth({
          status: 'unhealthy',
          message: 'Backend is not responding',
          lastChecked: new Date(),
        });
        setIsVisible(true);
      }
    } catch (error) {
      const errorMessage = error.response?.status === 503
        ? 'Backend service is unavailable. Please try again later.'
        : error.message?.includes('Network Error') || error.code === 'ECONNABORTED'
        ? 'Cannot connect to backend. Please check your connection.'
        : error.message || 'Backend connection error';
      
      setHealth({
        status: 'unhealthy',
        message: errorMessage,
        lastChecked: new Date(),
      });
      setIsVisible(true);
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Check every 30s
    return () => clearInterval(interval);
  }, []);

  // Only show if unhealthy or checking (for initial load)
  if (!isVisible && health.status === 'healthy') return null;

  const statusClasses = {
    checking: 'bg-warning/20 border-warning/40 text-warning',
    healthy: 'bg-success/20 border-success/40 text-success',
    unhealthy: 'bg-destructive/20 border-destructive/40 text-destructive',
  };

  return (
    <div
      className={`fixed top-0 left-0 right-0 px-4 py-3 flex items-center gap-3 text-sm z-[1000] border-b transition-all duration-300 ${
        statusClasses[health.status] || statusClasses.checking
      }`}
      data-testid="health-check-banner"
    >
      <div className="flex items-center gap-2 flex-1">
        {health.status === 'checking' && <Loader2 size={16} className="animate-spin" />}
        {health.status === 'healthy' && <CheckCircle size={16} />}
        {health.status === 'unhealthy' && <AlertCircle size={16} />}
        <span className="font-medium">{health.message}</span>
      </div>
      {health.lastChecked && (
        <span className="text-xs opacity-80">
          {health.lastChecked.toLocaleTimeString()}
        </span>
      )}
      {health.status === 'unhealthy' && (
        <button
          onClick={checkHealth}
          className="text-xs underline hover:no-underline opacity-80 hover:opacity-100"
          data-testid="retry-health-check"
        >
          Retry
        </button>
      )}
    </div>
  );
};

export default HealthCheck;

