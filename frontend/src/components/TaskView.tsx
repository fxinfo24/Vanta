// TaskView Component - Premium Glass UI
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '@/services/api';
import {
  ArrowLeftIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ArrowPathIcon,
  StopCircleIcon,
} from '@heroicons/react/24/outline';

interface Task {
  id: number;
  platform: string;
  profile_id: string;
  status: string;
  progress: number;
  message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  duration?: number;
  error?: string;
}

const TaskView: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadTask = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.getTask(Number(id));
      setTask(response.data);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load task');
    } finally {
      setLoading(false);
    }
  }, [id]);

  // Poll only while the run can still change. 4s instead of 3s: progress is
  // reported per stage, so a faster poll only adds load to the single backend
  // worker without showing anything new.
  const status = task?.status;
  useEffect(() => {
    loadTask();
    const interval = setInterval(() => {
      if (status === 'pending' || status === 'processing') loadTask();
    }, 4000);
    return () => clearInterval(interval);
  }, [loadTask, status]);

  const handleRetry = async () => {
    try {
      await api.retryTask(Number(id));
      loadTask();
    } catch (err) {
      console.error('Failed to retry task:', err);
    }
  };

  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel this task?')) return;
    try {
      await api.cancelTask(Number(id));
      loadTask();
    } catch (err) {
      console.error('Failed to cancel task:', err);
    }
  };

  if (loading && !task) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="relative">
          <div className="absolute inset-0 bg-primary-500/20 blur-xl rounded-full"></div>
          <div className="relative animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
        </div>
      </div>
    );
  }

  if (error || !task) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-center">
        <div className="glass-panel p-8 rounded-2xl border-rose-500/20 max-w-md w-full">
          <XCircleIcon className="w-16 h-16 text-rose-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-white mb-2">Error Loading Task</h2>
          <p className="text-white/60 mb-6">{error || 'Task not found'}</p>
          <Link
            to="/tasks"
            className="glass-button bg-white/5 hover:bg-white/10 text-white inline-flex items-center"
          >
            <ArrowLeftIcon className="w-4 h-4 mr-2" />
            Back to Tasks
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Breadcrumb & Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-2">
          <nav className="flex items-center space-x-2 text-sm text-white/40">
            <Link to="/tasks" className="hover:text-primary-400 transition-colors">Tasks</Link>
            <span>/</span>
            <span className="text-white/80">Task #{task.id}</span>
          </nav>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <span className="capitalize">{task.platform} Analysis</span>
            <span className="text-lg font-normal text-white/40">#{task.id}</span>
          </h1>
        </div>

        <div className="flex items-center gap-3">
          {task.status === 'completed' && (
            <Link
              to={`/tasks/${task.id}/results`}
              className="glass-button bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border-emerald-500/30 flex items-center"
            >
              <CheckCircleIcon className="w-5 h-5 mr-2" />
              View Results
            </Link>
          )}
          {(task.status === 'pending' || task.status === 'failed') && (
            <button
              onClick={handleRetry}
              className="glass-button bg-amber-600/20 hover:bg-amber-600/30 text-amber-400 border-amber-500/30 flex items-center"
            >
              <ArrowPathIcon className="w-5 h-5 mr-2" />
              Retry Task
            </button>
          )}
          {(task.status === 'pending' || task.status === 'processing') && (
            <button
              onClick={handleCancel}
              className="glass-button bg-rose-600/20 hover:bg-rose-600/30 text-rose-400 border-rose-500/30 flex items-center"
            >
              <StopCircleIcon className="w-5 h-5 mr-2" />
              Cancel Analysis
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Status Card */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-primary-500/5 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none"></div>

          <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
            <ClockIcon className="w-5 h-5 text-primary-400" />
            Live Status
          </h3>

          <div className="space-y-8">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`
                  w-12 h-12 rounded-xl flex items-center justify-center
                  ${task.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400' :
                    task.status === 'processing' ? 'bg-blue-500/20 text-blue-400 animate-pulse' :
                      task.status === 'failed' ? 'bg-rose-500/20 text-rose-400' :
                        'bg-amber-500/20 text-amber-400'}
                `}>
                  {task.status === 'completed' ? <CheckCircleIcon className="w-6 h-6" /> :
                    task.status === 'failed' ? <XCircleIcon className="w-6 h-6" /> :
                      <ArrowPathIcon className={`w-6 h-6 ${task.status === 'processing' ? 'animate-spin' : ''}`} />}
                </div>
                <div>
                  <div className="text-2xl font-bold text-white capitalize">{task.status}</div>
                  <div className="text-white/40 text-sm">
                    {task.message || (task.status === 'completed' ? 'Analysis finished successfully' : 'Waiting for system...')}
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-b from-white to-white/40">
                  {task.progress}%
                </div>
                <div className="text-white/40 text-xs uppercase tracking-wide">Completion</div>
              </div>
            </div>

            <div className="relative h-2 bg-white/5 rounded-full overflow-hidden">
              <div
                className={`absolute top-0 left-0 h-full rounded-full transition-all duration-700
                  ${task.status === 'completed' ? 'bg-emerald-500' :
                    task.status === 'failed' ? 'bg-rose-500' :
                      'bg-gradient-to-r from-primary-600 to-secondary-500'}
                `}
                style={{ width: `${task.progress}%` }}
              >
                {task.status === 'processing' && (
                  <div className="absolute inset-0 bg-white/20 animate-shimmer" style={{ backgroundSize: '20px 20px', backgroundImage: 'linear-gradient(45deg,rgba(255,255,255,.15) 25%,transparent 25%,transparent 50%,rgba(255,255,255,.15) 50%,rgba(255,255,255,.15) 75%,transparent 75%,transparent)' }}></div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Details Card */}
        <div className="glass-panel p-6 rounded-2xl">
          <h3 className="text-lg font-semibold text-white mb-6">Task Details</h3>
          <dl className="space-y-4">
            {[
              { label: 'Profile ID', value: task.profile_id },
              { label: 'Platform', value: task.platform },
              { label: 'Created', value: new Date(task.created_at).toLocaleString() },
              { label: 'Duration', value: task.duration ? `${task.duration.toFixed(1)}s` : '-' },
            ].map((item, idx) => (
              <div key={idx} className="flex justify-between items-center py-2 border-b border-white/5 last:border-0">
                <dt className="text-white/40 text-sm">{item.label}</dt>
                <dd className="text-white font-mono text-sm">{item.value}</dd>
              </div>
            ))}
          </dl>

          {task.error && (
            <div className="mt-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm">
              <span className="font-bold block mb-1">Error Report:</span>
              {task.error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TaskView;
