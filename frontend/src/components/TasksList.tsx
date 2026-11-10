// TasksList Component - Premium Glass UI
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '@/services/api';
import AnalysisForm from '@/components/AnalysisForm';
import {
  FunnelIcon,
  MagnifyingGlassIcon,
  ArrowRightIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';

interface Task {
  id: number;
  platform: string;
  profile_id: string;
  status: string;
  progress: number;
  created_at: string;
  message?: string;
  // When the stored data was collected (not when the run was requested) and
  // how many snapshots exist for this subject.
  last_collected_at?: string | null;
  history_depth?: number;
}

const TasksList: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ platform: '', status: '' });
  const [showNewAnalysis, setShowNewAnalysis] = useState(false);

  const hasActiveTasks = tasks.some(t => ['pending', 'processing'].includes(t.status));

  // Load once per filter change.
  useEffect(() => {
    loadTasks(true);
  }, [filter.platform, filter.status]);

  // Poll only while something is actually moving. A finished list needs no
  // traffic, and 4s is still responsive for stage-level progress on a
  // single-worker backend. Previously the interval read a stale `tasks`
  // snapshot, so it could keep polling a list that had already settled.
  useEffect(() => {
    const shouldPoll =
      hasActiveTasks || filter.status === 'processing' || filter.status === 'pending';
    if (!shouldPoll) return;
    const intervalId = setInterval(() => loadTasks(false), 4000);
    return () => clearInterval(intervalId);
  }, [hasActiveTasks, filter.status]);

  // Optimize loadTasks to handle silent updates
  const loadTasks = async (isManual = false) => {
    try {
      if (isManual) setLoading(true);
      const params = new URLSearchParams();
      if (filter.platform) params.append('platform', filter.platform);
      if (filter.status) params.append('status', filter.status);

      const response = await api.getTasks(params.toString());
      setTasks(response.data.tasks || []);
    } catch (error) {
      console.error('Failed to load tasks:', error);
    } finally {
      if (isManual) setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircleIcon className="w-3 h-3" />
            <span>Completed</span>
          </span>
        );
      case 'processing':
        return (
          <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20 animate-pulse">
            <div className="w-2 h-2 rounded-full bg-blue-400 animate-ping" />
            <span>Processing</span>
          </span>
        );
      case 'failed':
        return (
          <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <XCircleIcon className="w-3 h-3" />
            <span>Failed</span>
          </span>
        );
      default:
        return (
          <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <ClockIcon className="w-3 h-3" />
            <span>Pending</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60 font-display">
            Analysis Tasks
          </h1>
          <p className="mt-1 text-primary-200 text-sm">
            Manage and monitor your intelligence gathering operations.
          </p>
        </div>
        <button
          onClick={() => setShowNewAnalysis(true)}
          className="glass-button bg-primary-600 hover:bg-primary-500 text-white flex items-center justify-center space-x-2 shadow-[0_0_20px_rgba(99,102,241,0.3)]"
        >
          <MagnifyingGlassIcon className="h-4 w-4" />
          <span>New Analysis</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar Filters */}
        <div className="lg:col-span-1 space-y-4">
          <div className="glass-panel p-5 rounded-xl sticky top-24">
            <div className="flex items-center space-x-2 text-white/90 mb-6 border-b border-white/10 pb-4">
              <FunnelIcon className="h-5 w-5 text-primary-400" />
              <h3 className="font-semibold">Filters</h3>
            </div>

            <div className="space-y-6">
              {/* Platform */}
              <div>
                <label className="block text-xs font-medium text-white/50 uppercase tracking-wider mb-3">Platform</label>
                <div className="space-y-2 max-h-[60vh] overflow-y-auto custom-scrollbar pr-2">
                  <button
                    onClick={() => setFilter({ ...filter, platform: '' })}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all ${filter.platform === ''
                      ? 'bg-primary-500/20 text-white border border-primary-500/30'
                      : 'text-white/60 hover:text-white hover:bg-white/5'
                      }`}
                  >
                    All Platforms
                  </button>
                  {[
                    // Social
                    { id: 'twitter', label: 'Twitter/X' },
                    { id: 'instagram', label: 'Instagram' },
                    { id: 'facebook', label: 'Facebook' },
                    { id: 'threads', label: 'Threads' },
                    { id: 'bluesky', label: 'Bluesky' },
                    { id: 'reddit', label: 'Reddit' },
                    { id: 'pinterest', label: 'Pinterest' },
                    { id: 'snapchat', label: 'Snapchat' },
                    // Video
                    { id: 'tiktok', label: 'TikTok' },
                    { id: 'youtube', label: 'YouTube' },
                    { id: 'twitch', label: 'Twitch' },
                    { id: 'kick', label: 'Kick' },
                    // Professional
                    { id: 'linkedin', label: 'LinkedIn' },
                    { id: 'github', label: 'GitHub' },
                    { id: 'google', label: 'Google' },
                    // Commerce
                    { id: 'tiktok_shop', label: 'TikTok Shop' },
                    { id: 'amazon_shop', label: 'Amazon Shop' },
                    // Link In Bio
                    { id: 'linktree', label: 'Linktree' },
                    { id: 'komi', label: 'Komi' },
                    { id: 'pillar', label: 'Pillar' },
                    { id: 'linkbio', label: 'Linkbio' },
                  ].map((opt) => (
                    <button
                      key={opt.id}
                      onClick={() => setFilter({ ...filter, platform: opt.id })}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all ${filter.platform === opt.id
                        ? 'bg-primary-500/20 text-white border border-primary-500/30'
                        : 'text-white/60 hover:text-white hover:bg-white/5'
                        }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Status */}
              <div>
                <label className="block text-xs font-medium text-white/50 uppercase tracking-wider mb-3">Status</label>
                <div className="space-y-2">
                  {[
                    { id: '', label: 'All Statuses' },
                    { id: 'completed', label: 'Completed' },
                    { id: 'processing', label: 'Processing' },
                    { id: 'failed', label: 'Failed' },
                  ].map((opt) => (
                    <button
                      key={opt.id}
                      onClick={() => setFilter({ ...filter, status: opt.id })}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all ${filter.status === opt.id
                        ? 'bg-secondary-500/20 text-white border border-secondary-500/30'
                        : 'text-white/60 hover:text-white hover:bg-white/5'
                        }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Tasks Grid/List */}
        <div className="lg:col-span-3">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <div className="relative">
                <div className="absolute inset-0 bg-primary-500/20 blur-xl rounded-full"></div>
                <div className="relative animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
              </div>
            </div>
          ) : tasks.length === 0 ? (
            <div className="glass-panel rounded-xl p-12 text-center flex flex-col items-center justify-center border border-dashed border-white/10">
              <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4">
                <MagnifyingGlassIcon className="h-8 w-8 text-white/20" />
              </div>
              <h3 className="text-lg font-medium text-white">No tasks found</h3>
              <p className="text-white/40 mt-1 max-w-sm">
                Try adjusting your filters or start a new analysis to generate data.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  className="glass-card p-4 rounded-xl flex flex-col sm:flex-row items-center justify-between group gap-4"
                >
                  <div className="flex items-center gap-4 w-full sm:w-auto">
                    <div className={`
                      w-12 h-12 rounded-lg flex items-center justify-center text-xl
                      ${task.platform === 'twitter' ? 'bg-black/40 text-white' :
                        task.platform === 'instagram' ? 'bg-gradient-to-tr from-yellow-500 via-red-500 to-purple-500 text-white' :
                          task.platform === 'linkedin' ? 'bg-blue-600 text-white' :
                            'bg-gray-700 text-white'}
                    `}>
                      {task.platform === 'twitter' ? '𝕏' : task.platform.charAt(0).toUpperCase()}
                    </div>

                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-semibold text-white">{task.profile_id}</h4>
                        <span className="text-white/30 text-xs">#{task.id}</span>
                      </div>
                      <div className="text-sm text-white/50 flex flex-wrap items-center gap-2">
                        <span className="capitalize">{task.platform}</span>
                        <span>•</span>
                        <span title="When this run was requested">
                          requested {new Date(task.created_at).toLocaleDateString()}
                        </span>
                        <span>•</span>
                        <span
                          title="When the data behind these numbers was collected"
                          className={task.last_collected_at ? '' : 'text-amber-400/80'}
                        >
                          {task.last_collected_at
                            ? `data collected ${new Date(task.last_collected_at).toLocaleDateString()}`
                            : 'no collected data'}
                        </span>
                        <span>•</span>
                        <span title="Stored snapshots for this subject; trends need two">
                          {!task.history_depth
                            ? 'no snapshots yet'
                            : task.history_depth === 1
                              ? '1 snapshot — no trend yet'
                              : `${task.history_depth} snapshots`}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6 w-full sm:w-auto justify-between sm:justify-end">
                    <div className="flex flex-col items-end gap-1 min-w-[100px]">
                      {getStatusBadge(task.status)}
                      {task.status === 'processing' && (
                        <div className="w-24 h-1 bg-white/10 rounded-full mt-1 overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full transition-all duration-500"
                            style={{ width: `${task.progress}%` }}
                          />
                        </div>
                      )}
                    </div>

                    <Link
                      to={`/tasks/${task.id}`}
                      className="p-2 rounded-lg hover:bg-white/10 text-white/40 hover:text-white transition-colors"
                    >
                      <ArrowRightIcon className="w-5 h-5" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {showNewAnalysis && (
        <AnalysisForm
          onAnalysisCreated={() => {
            setShowNewAnalysis(false);
            loadTasks(true);
          }}
          onClose={() => setShowNewAnalysis(false)}
        />
      )}
    </div>
  );
};

export default TasksList;
