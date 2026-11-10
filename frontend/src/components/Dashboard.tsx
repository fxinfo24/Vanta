// Dashboard Component for Vanta
// Shows recent tasks and platform breakdown
import React, { useEffect, useState } from 'react';
import {
  ChartBarIcon,
  CheckCircleIcon,
  ClockIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { apiService } from '@/services/api';
import AnalysisForm from '@/components/AnalysisForm';

// Neon Palette for Charts
const COLORS = ['#6366f1', '#8b5cf6', '#d946ef', '#06b6d4', '#10b981'];

type Task = {
  id: number;
  platform: string;
  profile_id?: string;
  profileId?: string;
  status: string;
  progress?: number;
  message?: string;
  created_at?: string;
  createdAt?: string;
  last_collected_at?: string | null;
  history_depth?: number;
};

type VerificationClaim = { id: string; text: string; type?: string; checkworthiness?: number; post_id?: string };
type VerificationResult = { id: string; claim_id: string; status?: string; confidence?: number; composite?: number; fact_check_verdict?: string; evidence_chain_layers?: string[] };

const verdictColor = (s?: string) => {
  const v = (s || '').toLowerCase();
  if (v.includes('verified_true') || v === 'true') return 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400';
  if (v.includes('verified_false') || v === 'false' || v.includes('misleading')) return 'bg-rose-500/10 border-rose-500/20 text-rose-400';
  if (v.includes('unverifiable') || v.includes('unverified') || v.includes('insufficient')) return 'bg-amber-500/10 border-amber-500/20 text-amber-400';
  return 'bg-white/5 border-white/10 text-white/60';
};

const Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [showNewAnalysis, setShowNewAnalysis] = useState(false);

  const [tasks, setTasks] = useState<Task[]>([]);
  const [platformDist, setPlatformDist] = useState<Array<{ platform: string; count: number }>>([]);
  const [completionRate, setCompletionRate] = useState<{ total: number; completed: number; failed: number; completion_rate: number } | null>(null);
  const [vClaims, setVClaims] = useState<VerificationClaim[]>([]);
  const [vResults, setVResults] = useState<VerificationResult[]>([]);
  const [vRunning, setVRunning] = useState(false);

  const [hoveredCard, setHoveredCard] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [tasksResp, distResp, rateResp, claimsResp, resultsResp] = await Promise.all([
        apiService.listTasks({ limit: 10, offset: 0 }),
        apiService.getPlatformDistribution(),
        apiService.getCompletionRate(),
        apiService.listVerificationClaims(20).catch(() => ({ success: false, data: null }) as any),
        apiService.listVerificationResults(20).catch(() => ({ success: false, data: null }) as any),
      ]);

      if (tasksResp.success && tasksResp.data?.tasks) {
        setTasks(tasksResp.data.tasks);
      }
      if (distResp.success && Array.isArray(distResp.data)) {
        setPlatformDist(distResp.data);
      }
      if (rateResp.success && rateResp.data) {
        setCompletionRate(rateResp.data);
      }
      if ((claimsResp as any).success && (claimsResp as any).data?.claims) setVClaims((claimsResp as any).data.claims);
      if ((resultsResp as any).success && (resultsResp as any).data?.results) setVResults((resultsResp as any).data.results);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="relative">
          <div className="absolute inset-0 bg-primary-500/20 blur-xl rounded-full"></div>
          <div className="relative animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-primary-500"></div>
        </div>
      </div>
    );
  }

  const pieData = platformDist.map((p) => ({ name: p.platform, value: p.count }));

  return (
    <div className="space-y-8 animate-fade-in-up">
      {/* Header Section */}
      <div className="glass-panel rounded-2xl p-8 relative overflow-hidden group">
        <div className="absolute top-0 right-0 w-64 h-64 bg-primary-500/10 rounded-full blur-3xl -mr-16 -mt-16 transition-all duration-700 group-hover:bg-primary-500/20"></div>

        <div className="relative z-10 md:flex md:items-center md:justify-between">
          <div className="flex-1 min-w-0">
            <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60 font-display">
              Analysis Dashboard
            </h1>
            <p className="mt-2 text-primary-200">
              Overview of your social media intelligence operations.
            </p>
          </div>
          <div className="mt-6 md:mt-0 md:ml-4">
            <button
              onClick={() => setShowNewAnalysis(true)}
              className="group glass-button flex items-center space-x-2 text-white bg-primary-600/20 hover:bg-primary-600/40 border-primary-500/30 hover:border-primary-500/60"
            >
              <SparklesIcon className="h-5 w-5 text-primary-300 group-hover:text-white transition-colors" />
              <span>New Analysis</span>
            </button>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { icon: ChartBarIcon, label: 'Total Tasks', value: completionRate?.total ?? tasks.length, color: 'text-blue-400', bg: 'bg-blue-500/10' },
          { icon: CheckCircleIcon, label: 'Completed', value: completionRate?.completed ?? 0, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
          { icon: ClockIcon, label: 'Success Rate', value: `${(completionRate?.completion_rate ?? 0).toFixed(1)}%`, color: 'text-amber-400', bg: 'bg-amber-500/10' },
          { icon: ChartBarIcon, label: 'Failed', value: completionRate?.failed ?? 0, color: 'text-rose-400', bg: 'bg-rose-500/10' },
        ].map((item, index) => (
          <div
            key={item.label}
            className="glass-card p-6 relative overflow-hidden group"
            onMouseEnter={() => setHoveredCard(index)}
            onMouseLeave={() => setHoveredCard(null)}
          >
            <div className={`absolute -right-4 -top-4 w-24 h-24 rounded-full ${item.bg} blur-2xl transition-all duration-500 ${hoveredCard === index ? 'opacity-100 scale-125' : 'opacity-0 scale-100'}`} />

            <div className="relative z-10 flex items-center">
              <div className={`p-3 rounded-lg ${item.bg} border border-white/5`}>
                <item.icon className={`h-6 w-6 ${item.color}`} />
              </div>
              <div className="ml-4">
                <div className="text-sm font-medium text-white/50">{item.label}</div>
                <div className="text-2xl font-bold text-white tracking-tight">{item.value}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Charts & Lists */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Platform Breakdown */}
        <div className="glass-card p-6 h-[400px] flex flex-col">
          <h3 className="text-lg font-semibold text-white mb-6 flex items-center">
            <span className="w-1.5 h-6 bg-primary-500 rounded-full mr-3"></span>
            Platform Distribution
          </h3>
          <div className="flex-1 w-full min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                  nameKey="name"
                  stroke="none"
                >
                  {pieData.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={COLORS[index % COLORS.length]}
                      className="transition-all duration-300 hover:opacity-80 cursor-pointer"
                      filter="url(#glow)"
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                  itemStyle={{ color: '#fff' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent Tasks */}
        <div className="glass-card flex flex-col h-[400px]">
          <div className="px-6 py-5 border-b border-white/5 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-white flex items-center">
              <span className="w-1.5 h-6 bg-secondary-500 rounded-full mr-3"></span>
              Recent Tasks
            </h3>
            <button className="text-xs text-primary-400 hover:text-primary-300 transition-colors">View All</button>
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar p-2">
            {tasks.length ? (
              <div className="space-y-2">
                {tasks.map((t) => (
                  <div key={t.id} className="p-4 rounded-lg bg-white/5 hover:bg-white/10 transition-colors border border-transparent hover:border-white/5 group cursor-pointer">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className={`w-2 h-2 rounded-full ${t.status === 'completed' ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]' : t.status === 'failed' ? 'bg-rose-400' : 'bg-amber-400 animate-pulse'}`} />
                        <div>
                          <div className="text-sm font-medium text-white group-hover:text-primary-300 transition-colors">
                            {t.platform}
                          </div>
                          <div className="text-xs text-white/40">
                            ID: {(t.profile_id ?? t.profileId) || 'N/A'}
                          </div>
                          <div className="text-xs text-white/30">
                            {t.last_collected_at
                              ? `collected ${new Date(t.last_collected_at).toLocaleDateString()}`
                              : 'no data collected'}
                            {t.history_depth && t.history_depth > 1
                              ? ` · ${t.history_depth} snapshots`
                              : ''}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className={`text-xs px-2 py-1 rounded-full border ${t.status === 'completed' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' :
                          t.status === 'failed' ? 'bg-rose-500/10 border-rose-500/20 text-rose-400' :
                            'bg-amber-500/10 border-amber-500/20 text-amber-400'
                          }`}>
                          {t.status}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-6">
                <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4">
                  <ChartBarIcon className="h-8 w-8 text-white/20" />
                </div>
                <h3 className="text-white font-medium">No tasks yet</h3>
                <p className="text-sm text-white/40 mt-1">Start a new analysis to see data.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Verification (Product B) */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white flex items-center">
            <span className="w-1.5 h-6 bg-emerald-500 rounded-full mr-3"></span>
            Verification — Claims, Verdicts & Confidence
          </h3>
          <button disabled={vRunning} onClick={async () => { setVRunning(true); await apiService.runVerificationPipeline({}); await load(); setVRunning(false); }} className="glass-button text-xs bg-emerald-600/20 hover:bg-emerald-600/40 border-emerald-500/30 text-emerald-300 disabled:opacity-50">
            {vRunning ? 'Running…' : 'Run Pipeline'}
          </button>
        </div>
        {vClaims.length ? (
          <div className="space-y-2">
            {vClaims.map((c) => {
              const vr = vResults.find((r) => r.claim_id === c.id);
              const conf = vr?.composite ?? vr?.confidence;
              return (
                <div key={c.id} className="p-4 rounded-lg bg-white/5 border border-white/5">
                  <p className="text-sm text-white/90">{c.text}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-3">
                    <span className={`text-xs px-2 py-1 rounded-full border ${verdictColor(vr?.status)}`}>{vr?.status || 'pending'}</span>
                    {vr?.fact_check_verdict && <span className="text-xs text-white/50">fact-check: {vr.fact_check_verdict}</span>}
                    {conf != null && (
                      <span className="flex items-center gap-2 text-xs text-white/60">confidence {Math.round(conf * 100)}%
                        <span className="inline-block w-24 h-1.5 bg-white/10 rounded-full overflow-hidden"><span className="block h-full bg-emerald-400" style={{ width: `${Math.round(conf * 100)}%` }} /></span>
                      </span>
                    )}
                    {vr?.evidence_chain_layers?.length ? <span className="text-xs text-white/40">layers: {vr.evidence_chain_layers.join(', ')}</span> : null}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-white/40">No verified claims yet. Create a post via <code>/api/verification/post</code> or verify a task, then run the pipeline.</p>
        )}
      </div>

      {showNewAnalysis && (
        <AnalysisForm
          onAnalysisCreated={() => {
            setShowNewAnalysis(false);
            load();
          }}
          onClose={() => setShowNewAnalysis(false)}
        />
      )}
    </div>
  );
};

export default Dashboard;
