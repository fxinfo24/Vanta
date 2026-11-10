
import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import api from '@/services/api';
import {
  ArrowDownTrayIcon, UserIcon, ShieldCheckIcon,
  GlobeAmericasIcon, ShoppingBagIcon, SparklesIcon,
  DocumentMagnifyingGlassIcon, HeartIcon, BriefcaseIcon, BoltIcon,
  ShareIcon
} from '@heroicons/react/24/outline';
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, LineChart, Line, CartesianGrid
} from 'recharts';
import NetworkGraph from './NetworkGraph';

// The executive summary arrives as Markdown ("**Subject Overview:**", "- item")
// and was printed literally, so readers saw asterisks where headings belong.
// Only the shapes the model actually emits are handled - bold, bullets,
// headings, paragraphs - and anything else stays visible as plain text rather
// than being silently dropped.
const _inline = (text: string, keyBase: string): React.ReactNode[] =>
  text
    .split(/(\*\*[^*]+\*\*)/g)
    .filter((part) => part !== '')
    .map((part, i) =>
      part.startsWith('**') && part.endsWith('**') && part.length > 4 ? (
        <strong key={`${keyBase}-${i}`} className="font-semibold text-white/85">
          {part.slice(2, -2)}
        </strong>
      ) : (
        <React.Fragment key={`${keyBase}-${i}`}>{part}</React.Fragment>
      ),
    );

const SummaryText: React.FC<{ text: string }> = ({ text }) => {
  const blocks: React.ReactNode[] = [];
  let paragraph: string[] = [];
  let bullets: string[] = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const key = `p-${blocks.length}`;
    blocks.push(
      <p key={key} className="mb-3 last:mb-0 leading-relaxed">
        {_inline(paragraph.join(' '), key)}
      </p>,
    );
    paragraph = [];
  };
  const flushBullets = () => {
    if (!bullets.length) return;
    const key = `ul-${blocks.length}`;
    blocks.push(
      <ul key={key} className="mb-3 last:mb-0 list-disc pl-5 space-y-1">
        {bullets.map((item, i) => (
          <li key={`${key}-${i}`}>{_inline(item, `${key}-${i}`)}</li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) {
      flushParagraph();
      flushBullets();
      continue;
    }
    if (/^[*-]\s+/.test(line)) {
      flushParagraph();
      bullets.push(line.replace(/^[*-]\s+/, ''));
      continue;
    }
    if (/^#{1,6}\s+/.test(line)) {
      flushParagraph();
      flushBullets();
      const key = `h-${blocks.length}`;
      blocks.push(
        <h4 key={key} className="text-white/85 font-semibold mt-2 mb-1">
          {_inline(line.replace(/^#{1,6}\s+/, ''), key)}
        </h4>,
      );
      continue;
    }
    flushBullets();
    paragraph.push(line);
  }
  flushParagraph();
  flushBullets();

  return <>{blocks}</>;
};

interface AnalysisResult {
  profile_info: any;
  sentiment: any;
  content_analysis: any;
  authenticity: any;
  belief_system?: any;
  consumer_profile?: any;
  behavioral_profile?: any;
  executive_summary?: string;
  metadata?: any;
  connected_accounts?: any[];
  raw_dossier?: any;
  data_coverage?: any;
}

const ResultView: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [task, setTask] = useState<any>(null);
  const [results, setResults] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  const loadResults = useCallback(async () => {
    try {
      setLoading(true);
      const taskRes = await api.getTask(Number(id));
      setTask(taskRes.data);
      if (taskRes.data.status === 'completed') {
        const resRes = await api.getTaskResults(Number(id));
        setResults(resRes.data);
      }
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [id]);

  useEffect(() => { loadResults(); }, [loadResults]);

  // A bare window.open() to /api/... cannot carry the Bearer token, so the
  // auth guard answered 401 and the new tab showed a raw JSON error. Fetch
  // the file through the authenticated API client (token attached), then
  // open the resulting blob: html renders in a tab for printing, json is
  // saved as a file download.
  const handleExport = async (format: string) => {
    try {
      const blob = await api.downloadTaskResults(Number(id), format);
      const url = URL.createObjectURL(blob);
      if (format === 'html' || format === 'pdf') {
        window.open(url, '_blank');
      } else {
        const a = document.createElement('a');
        a.href = url;
        a.download = `dossier_${format}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      console.error('Export failed:', err);
    }
  };

  if (loading) return (
    <div className="flex justify-center items-center h-[60vh]">
      <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-primary-500"></div>
    </div>
  );

  if (!results) return <div>No data found.</div>;

  // Prepare Chart Data
  // Backend stores Big 5 scores under `personality_traits`; the old
  // `psychological_profile` key never existed in stored results.
  const psychData = Object.entries(
    results.content_analysis?.personality_traits ||
    results.content_analysis?.psychological_profile || {}
  )
    .filter(([, val]) => typeof val === 'number')
    .map(([key, val]) => ({ subject: key.charAt(0).toUpperCase() + key.slice(1), A: (val as number) * 100, fullMark: 100 }));

  // Backend keys use underscores (SOCIAL_VALUES); keep the spaced variant
  // as a fallback for older stored results.
  const beliefData = Object.entries(
    results.belief_system?.SOCIAL_VALUES || results.belief_system?.['SOCIAL VALUES'] || {}
  )
    .map(([key, val]) => ({ name: key.replace('_', ' '), value: val, fullMark: 10 }));

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview': return <OverviewTab results={results} task={task} />;
      case 'beliefs': return <BeliefsTab results={results} beliefData={beliefData} />;
      case 'consumer': return <ConsumerTab results={results} />;
      case 'psych': return <PsychTab results={results} psychData={psychData} />;
      case 'lifestyle': return <LifestyleTab results={results} />;
      case 'network': return <NetworkTab results={results} />;
      default: return <OverviewTab results={results} task={task} />;
    }
  };

  return (
    <div className="space-y-8 animate-fade-in-up pb-12">
      {/* Header */}
      {/* Header */}
      <div className="glass-panel p-6 md:p-8 rounded-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-primary-500/10 rounded-full blur-[100px] pointer-events-none"></div>
        <div className="relative z-10 flex flex-col md:flex-row justify-between items-start gap-6">
          <div className="flex-1">
            <div className="flex items-center gap-2 text-white/40 text-sm mb-2">
              <span className="uppercase tracking-wider">Intelligence Dossier</span>
              <span className="px-2 py-0.5 rounded bg-primary-500/20 text-primary-300 text-xs">
                {results.metadata?.collection_mode === 'deep' ? 'DEEP SCAN' : 'QUICK SCAN'}
              </span>
            </div>
            <h1 className="text-3xl md:text-4xl font-bold text-white font-display mb-2 break-all">
              {results.profile_info?.display_name || `@${results.profile_info?.username}`}
            </h1>
            {results.profile_info?.username && (
              <div className="text-sm text-white/40 mb-2 break-all">
                {/^\d{6,}$/.test(String(results.profile_info.username))
                  ? `Platform id ${results.profile_info.username}`
                  : `@${results.profile_info.username}`}
              </div>
            )}
            <div className="text-base md:text-lg text-white/60 max-w-2xl">
              <SummaryText text={results.executive_summary || results.profile_info?.bio || "No summary available."} />
            </div>
          </div>
          <div className="flex gap-3 w-full md:w-auto">
            <button onClick={() => handleExport('html')} className="glass-button bg-primary-600 hover:bg-primary-500 text-white flex items-center justify-center flex-1 md:flex-initial shadow-[0_0_15px_rgba(79,70,229,0.4)] transition-all">
              <DocumentMagnifyingGlassIcon className="h-4 w-4 mr-2" /> Print (PDF)
            </button>
            <button onClick={() => handleExport('json')} className="glass-button bg-white/5 hover:bg-white/10 text-white flex items-center justify-center flex-1 md:flex-initial">
              <ArrowDownTrayIcon className="h-4 w-4 mr-2" /> JSON
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex gap-6 mt-8 border-b border-white/10 overflow-x-auto no-scrollbar pb-1">
          {[
            { id: 'overview', label: 'Overview', icon: UserIcon },
            { id: 'network', label: 'Network', icon: ShareIcon },
            { id: 'beliefs', label: 'Worldview', icon: GlobeAmericasIcon },
            { id: 'consumer', label: 'Consumer', icon: ShoppingBagIcon },
            { id: 'psych', label: 'Psychology', icon: SparklesIcon },
            { id: 'lifestyle', label: 'Lifestyle', icon: HeartIcon },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-3 flex items-center gap-2 transition-all whitespace-nowrap ${activeTab === tab.id
                ? 'text-primary-400 border-b-2 border-primary-500'
                : 'text-white/50 hover:text-white'
                }`}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {results.data_coverage && <CoverageStrip coverage={results.data_coverage} />}

      {renderTabContent()}

    </div>
  );
};

// What every tab below was actually computed from. Shown once, above the tabs,
// because a section with no inputs should not read like a finding.
const CoverageStrip = ({ coverage }: { coverage: any }) => {
  const measured: any[] = coverage.measured || [];
  const missing: any[] = coverage.not_measured || [];
  const gaps: string[] = coverage.missing_inputs || [];
  const errors: string[] = coverage.collection_errors || [];
  const counts = coverage.counts || {};
  // A cached run reads the dossier collected earlier, so its numbers describe
  // that moment, not now. Saying so is the difference between a stale figure
  // and a wrong one.
  const fromCache = coverage.dossier_source === 'cache';
  return (
    <div className="glass-card rounded-2xl p-4 mt-6">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="uppercase tracking-wider text-white/40 mr-1">Evidence coverage</span>
        {measured.map((m: any) => (
          <span key={m.section} title={m.basis} className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-200 border border-emerald-500/20">
            {m.section}
          </span>
        ))}
        {missing.map((m: any) => (
          <span key={m.section} title={m.basis} className="px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-200 border border-rose-500/20">
            {m.section} — not measured
          </span>
        ))}
      </div>
      <div className="text-[11px] text-white/40 mt-2">
        Based on {counts.posts ?? 0} posts ({counts.posts_with_engagement ?? 0} with engagement metrics),{' '}
        {counts.comments ?? 0} comments
        {gaps.length > 0 && <> · not collected: {gaps.join(', ')}</>}
        {fromCache && (
          <> · reused the dossier collected {(coverage.dossier_collected_at || '').slice(0, 16).replace('T', ' ')} UTC (0 credits)</>
        )}
      </div>
      {errors.length > 0 && (
        <div className="text-[11px] text-rose-300/90 mt-1 break-words">
          Collection failed: {errors.join(' · ')}
        </div>
      )}
    </div>
  );
};

// --- Sub-Components ---

const NetworkTab = ({ results }: { results: AnalysisResult }) => {
  // Transform data for the graph
  const nodes: any[] = [];
  const links: any[] = [];

  // Center node
  const centerId = results.profile_info?.username || 'Target';
  nodes.push({ id: centerId, group: 1, radius: 20 });

  // Connected Accounts
  results.connected_accounts?.forEach((acc: any) => {
    const nodeId = `${acc.platform}:${acc.username}`;
    nodes.push({ id: nodeId, group: 2, radius: 15 });
    links.push({ source: centerId, target: nodeId, value: 1 });
  });

  // Social Graph (if available) from raw_dossier
  const social = results.raw_dossier?.social_graph || {};

  social.followers_sample?.forEach((f: any) => {
    const id = f.username || f.handle || 'Follower';
    if (!nodes.find(n => n.id === id)) {
      nodes.push({ id, group: 3, radius: 10 });
      links.push({ source: id, target: centerId, value: 0.5 });
    }
  });

  // No mock fallback: when no network data exists, say so honestly
  // instead of fabricating peers/interests.
  const hasNetwork = nodes.length > 1;

  return (
    <div className="glass-card p-6 rounded-2xl h-[600px] flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xl font-bold text-white flex items-center gap-2">
          <ShareIcon className="h-5 w-5 text-blue-400" /> Influence Network
        </h3>
        <div className="text-xs text-white/40">
          <span className="mr-3"><span className="text-blue-400">●</span> Target</span>
          <span className="mr-3"><span className="text-emerald-400">●</span> Connected Accounts</span>
          <span><span className="text-white/40">●</span> Peers/Followers</span>
        </div>
      </div>
      {hasNetwork ? (
        <div className="flex-1 bg-black/20 rounded-xl overflow-hidden border border-white/5 relative">
          <NetworkGraph data={{ nodes, links }} width={800} height={500} />
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-white/40 italic p-6 text-center">
          No network data available for this profile.
        </div>
      )}
    </div>
  );
};

const _historyDate = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString() : '—');
const _delta = (v: any, suffix = '') => {
  if (!v || v.change == null) return <span className="text-white/40">no comparable data</span>;
  const up = v.change > 0;
  const flat = v.change === 0;
  return (
    <span className={flat ? 'text-white/50' : up ? 'text-emerald-300' : 'text-rose-300'}>
      {flat ? 'unchanged' : `${up ? '+' : ''}${v.change}${suffix}`}
      {!flat && v.change_percent != null && <span className="text-white/40"> ({v.change_percent > 0 ? '+' : ''}{v.change_percent}%)</span>}
    </span>
  );
};

const HistoryPanel = ({ results }: { results: AnalysisResult }) => {
  const history = (results as any).history;
  const changes = (results as any).changes;
  const alertReport = (results as any).alerts;
  if (!history || !history.count || history.count < 2) return null;

  const rows: Array<[string, any]> = [
    ['Followers', changes?.followers],
    ['Engagement rate', changes?.engagement_rate_percent],
    ['Posts / week', changes?.posts_per_week],
    ['Bot likelihood', changes?.bot_likelihood],
    ['Trust score', changes?.trust_score],
  ];
  const alerts: any[] = alertReport?.alerts || [];
  const skipped: any[] = alertReport?.not_evaluated || [];

  return (
    <div className="glass-card p-6 rounded-2xl md:col-span-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-1">
        <h3 className="text-xl font-bold text-white">History &amp; changes</h3>
        <span className="text-xs text-white/40">
          {history.count} runs · {_historyDate(history.first_collected_at)} → {_historyDate(history.latest_collected_at)}
        </span>
      </div>
      <p className="text-xs text-white/40 mb-4">
        Compared with the previous run{changes?.from_task_id ? ` (task #${changes.from_task_id})` : ''}.
      </p>

      {history.snapshots?.length >= 2 && (
        <div className="h-48 mb-5">
          <ResponsiveContainer width="100%" height={192}>
            <LineChart
              data={history.snapshots.map((s: any, i: number) => ({
                // A date is what the reader needs (all backfilled runs share
                // today's date, so fall back to the run index when it repeats).
                run: s.collected_at
                  ? new Date(s.collected_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
                    + (i > 0 && String(s.collected_at).slice(0, 10)
                        === String(history.snapshots[i - 1]?.collected_at).slice(0, 10)
                        ? ` #${i + 1}` : '')
                  : `#${i + 1}`,
                engagement: s.engagement_rate_percent ?? null,
                bot: typeof s.bot_likelihood === 'number' ? Math.round(s.bot_likelihood * 100) : null,
              }))}
              margin={{ top: 5, right: 10, left: -20, bottom: 0 }}
            >
              <CartesianGrid stroke="#ffffff10" />
              <XAxis dataKey="run" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#1e293b', border: 'none', color: '#fff' }} />
              <Line type="monotone" dataKey="engagement" name="Engagement %" stroke="#22d3ee" strokeWidth={2} dot={{ r: 3 }} connectNulls />
              <Line type="monotone" dataKey="bot" name="Bot likelihood %" stroke="#f43f5e" strokeWidth={2} dot={{ r: 3 }} connectNulls />
            </LineChart>
          </ResponsiveContainer>
          <div className="text-[11px] text-white/40 mt-1">
            <span className="text-cyan-300">— engagement rate %</span> · <span className="text-rose-300">— bot likelihood %</span>
            {' '}across {history.snapshots.length} runs
          </div>
        </div>
      )}

      {changes ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {rows.map(([label, value]) => (
            <div key={String(label)} className="rounded-xl bg-white/5 border border-white/10 p-3">
              <div className="text-[11px] uppercase tracking-wider text-white/40">{label}</div>
              <div className="text-sm mt-1 text-white/85">
                {value?.current != null ? value.current : '—'} <span className="text-xs">{_delta(value)}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-sm text-white/50">First recorded run — nothing to compare yet.</div>
      )}

      {changes && (
        <div className="mt-4 space-y-1 text-xs">
          {changes.risk && (
            <div className="text-white/60">
              Risk: <span className="text-white/85">{changes.risk.previous ?? 'unknown'}</span>
              {' → '}<span className="text-white/85">{changes.risk.current ?? 'unknown'}</span>
              {changes.risk.changed ? '' : ' (unchanged)'}
            </div>
          )}
          {changes.political_label?.changed && (
            <div className="text-amber-200/80">
              Political label changed: {changes.political_label.previous} → {changes.political_label.current}
              <span className="text-white/40"> — labels depend on the sample, so treat a shift between runs as provisional.</span>
            </div>
          )}
          {changes.content?.coverage_note && (
            <div className="text-amber-200/80">{changes.content.coverage_note}</div>
          )}
          {changes.content?.comparable && (
            <div className="text-white/60">
              Posts: {changes.content.new_count} new · {changes.content.removed_count} no longer present ·{' '}
              {changes.content.retained_count} retained
            </div>
          )}
        </div>
      )}

      {/* Threshold alerts: every one names the rule and both numbers, so the
          reader can recompute it from the same snapshot. */}
      {(alerts.length > 0 || skipped.length > 0) && (
        <div className="mt-5 border-t border-white/10 pt-4">
          <div className="text-[11px] uppercase tracking-wider text-white/40 mb-2">
            Alerts {alerts.length > 0 ? `· ${alerts.length}` : '· none triggered'}
          </div>
          {alerts.map((a: any, i: number) => (
            <div key={i} className="flex items-start gap-2 text-xs mb-1.5">
              <span className={
                a.severity === 'critical' ? 'px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-200 shrink-0'
                : a.severity === 'warning' ? 'px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-200 shrink-0'
                : 'px-1.5 py-0.5 rounded bg-white/10 text-white/60 shrink-0'
              }>{a.severity}</span>
              <span className="text-white/80">
                {a.message} <span className="text-white/35">({a.basis})</span>
              </span>
            </div>
          ))}
          {skipped.length > 0 && (
            <div className="text-[11px] text-white/35 mt-2">
              Not evaluated: {skipped.map((s: any) => `${s.rule} — ${s.reason}`).join('; ')}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const OverviewTab = ({ results }: { results: AnalysisResult; task: any }) => (
  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
    <div className="glass-card p-6 rounded-2xl md:col-span-2">
      <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
        <ShieldCheckIcon className="h-5 w-5 text-emerald-400" /> Authenticity & Risk
      </h3>
      <div className="grid grid-cols-3 gap-4">
        <StatBox label="Risk Level" value={results.authenticity?.risk_assessment || 'Unknown'} color={
          ['critical', 'high'].includes(String(results.authenticity?.risk_assessment || '').toLowerCase()) ? 'text-red-400' :
            String(results.authenticity?.risk_assessment || '').toLowerCase() === 'medium' ? 'text-yellow-400' :
              String(results.authenticity?.risk_assessment || '').toLowerCase() === 'low' ? 'text-emerald-400' : 'text-slate-400'
        } />
        <StatBox label="Bot Probability" value={typeof results.authenticity?.bot_likelihood === 'number' ? `${Math.round(results.authenticity.bot_likelihood * 100)}%` : 'Unknown'} />
        <StatBox label="Trust Score" value={typeof results.authenticity?.overall_authenticity?.score === 'number' ? `${Math.round(results.authenticity.overall_authenticity.score * 100)}%` : 'Unknown'} />
      </div>
      {(results.authenticity?.engagement_metrics || results.authenticity?.risk_basis) && (
        <div className="text-[11px] text-white/40 mt-3 space-y-1">
          {results.authenticity?.engagement_metrics && (
            <div>
              Measured engagement {results.authenticity.engagement_metrics.rate_percent}% —{' '}
              {results.authenticity.engagement_metrics.reactions} reactions +{' '}
              {results.authenticity.engagement_metrics.comments} comments +{' '}
              {results.authenticity.engagement_metrics.shares} shares over{' '}
              {results.authenticity.engagement_metrics.posts_measured} posts ÷{' '}
              {results.authenticity.engagement_metrics.followers?.toLocaleString?.() ?? results.authenticity.engagement_metrics.followers} followers
            </div>
          )}
          {results.authenticity?.risk_basis && <div>Risk basis: {results.authenticity.risk_basis}</div>}
        </div>
      )}
      <div className="mt-6 space-y-2">
        {results.authenticity?.red_flags?.map((flag: string, i: number) => (
          <div key={i} className="flex items-center gap-2 text-red-200 bg-red-500/10 p-2 rounded">
            <span className="w-1.5 h-1.5 rounded-full bg-red-400"></span> {flag}
          </div>
        ))}
        {(results.authenticity?.data_gaps || []).length > 0 && (
          <div className="mt-3">
            <div className="text-[11px] uppercase tracking-wider text-white/40 mb-1">
              Data gaps — missing inputs, not evidence of risk
            </div>
            {(results.authenticity.data_gaps as string[]).map((gap, i) => (
              <div key={`gap-${i}`} className="flex items-start gap-2 text-amber-200/80 bg-amber-500/5 p-2 rounded mb-1">
                <span className="w-1.5 h-1.5 mt-2 shrink-0 rounded-full bg-amber-300/70"></span>
                <span>{gap}</span>
              </div>
            ))}
          </div>
        )}
        {results.authenticity?.limitations?.map((note: string, i: number) => (
          <div key={`lim-${i}`} className="flex items-start gap-2 text-slate-300 bg-slate-500/10 p-2 rounded">
            <span className="w-1.5 h-1.5 mt-2 shrink-0 rounded-full bg-slate-400"></span> <span>{note}</span>
          </div>
        ))}
        {results.authenticity?.topical_focus?.primary_topic &&
          results.authenticity.topical_focus.primary_topic !== 'Unknown' && (
            <div className="mt-4 rounded-xl bg-white/5 border border-white/10 p-3">
              <div className="text-[11px] uppercase tracking-wider text-white/50">Topical focus</div>
              <div className="text-sm text-white/85 mt-1">
                {results.authenticity.topical_focus.primary_topic}
                {typeof results.authenticity.topical_focus.political_intensity === 'number' && (
                  <span className="text-white/50">
                    {' '}· {Math.round(results.authenticity.topical_focus.political_intensity * 100)}% political
                  </span>
                )}
              </div>
              {(results.authenticity.topical_focus.evidence || []).map((quote: string, i: number) => (
                <div key={`tf-${i}`} className="text-xs text-white/60 italic mt-2 border-l-2 border-primary-400/40 pl-2">
                  “{quote}”
                </div>
              ))}
              <div className="text-[11px] text-white/40 mt-2">
                Subject matter only — a topic is not evidence of inauthenticity.
              </div>
            </div>
          )}
      </div>
    </div>

    <div className="glass-card p-6 rounded-2xl">
      <h3 className="text-xl font-bold text-white mb-4">Sentiment</h3>
      <div className="space-y-4">
        <ProgressBar label="Positive" value={results.sentiment?.positive} color="bg-emerald-500" />
        <ProgressBar label="Neutral" value={results.sentiment?.neutral} color="bg-gray-500" />
        <ProgressBar label="Negative" value={results.sentiment?.negative} color="bg-red-500" />
      </div>
    </div>

    <HistoryPanel results={results} />

    {/* Digital Footprint / Cross Platform */}
    <div className="glass-card p-6 rounded-2xl md:col-span-3">
      <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
        <GlobeAmericasIcon className="h-5 w-5 text-blue-400" /> Digital Footprint
      </h3>
      {results.connected_accounts && results.connected_accounts.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {results.connected_accounts.map((acc: any, i: number) => (
            <a
              key={i}
              href={acc.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors border border-white/5 hover:border-white/20"
            >
              <div className={`
                w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold
                ${acc.platform === 'twitter' ? 'bg-black text-white' :
                  acc.platform === 'instagram' ? 'bg-gradient-to-tr from-yellow-500 via-red-500 to-purple-500 text-white' :
                    'bg-primary-600 text-white'}
              `}>
                {acc.platform.charAt(0).toUpperCase()}
              </div>
              <div className="overflow-hidden">
                <div className="font-semibold text-white truncate">{acc.username}</div>
                <div className="text-xs text-white/50 capitalize">{acc.platform}</div>
              </div>
            </a>
          ))}
        </div>
      ) : (
        <div className="text-white/40 italic text-center py-8 bg-white/5 rounded-xl border border-dashed border-white/10">
          No linked accounts detected.
        </div>
      )}
    </div>
  </div>
);

const BeliefsTab = ({ results, beliefData }: { results: AnalysisResult; beliefData: any[] }) => {
  // Backend stores `POLITICAL_COMPASS` (underscores); tolerate the old spaced key.
  const compass = results.belief_system?.POLITICAL_COMPASS || results.belief_system?.['POLITICAL COMPASS'] || {};
  // Every belief claim should be traceable to a quoted post.
  const calibration = results.belief_system?.EVIDENCE_AND_CALIBRATION || results.belief_system?.['EVIDENCE AND CALIBRATION'] || {};
  const evidenceAxes = Object.entries(calibration.evidence || {}).filter(
    ([, quotes]: [string, any]) => Array.isArray(quotes) && quotes.length > 0
  ) as [string, string[]][];
  const quoteTotal = evidenceAxes.reduce((n, [, quotes]) => n + quotes.length, 0);

  // Policy-gated sections: the backend did not run the inference at all, so
  // there is nothing to display and no "low confidence" reading to fake.
  if (results.belief_system?.gated) {
    return (
      <div className="glass-card p-6 rounded-2xl">
        <h3 className="text-xl font-bold text-white mb-2">Belief system — not collected</h3>
        <p className="text-sm text-white/60 leading-relaxed">
          {results.belief_system.reason ||
            'Political, religious and social-belief inference is disabled by policy.'}
        </p>
        <p className="text-xs text-white/40 mt-3">
          These are special-category attributes (political opinions, religion) inferred about someone
          who did not consent to being analysed, so Vanta does not produce them by default.
        </p>
      </div>
    );
  }

  return (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
    <div className="glass-card p-6 rounded-2xl">
      <h3 className="text-xl font-bold text-white mb-4">Political Compass</h3>
      <div className="bg-white/5 rounded-xl p-6 relative h-64 flex items-center justify-center border border-white/10">
        {/* Simple Compass Viz */}
        <div className="absolute inset-0 grid grid-cols-2 grid-rows-2">
          <div className="border-r border-b border-white/10 flex items-start justify-start p-2 text-xs text-white/30">Auth Left</div>
          <div className="border-b border-white/10 flex items-start justify-end p-2 text-xs text-white/30">Auth Right</div>
          <div className="border-r border-white/10 flex items-end justify-start p-2 text-xs text-white/30">Lib Left</div>
          <div className="flex items-end justify-end p-2 text-xs text-white/30">Lib Right</div>
        </div>
        <div
          className="absolute w-4 h-4 bg-primary-500 rounded-full shadow-[0_0_15px_rgba(59,130,246,1)] z-10"
          style={{
            left: `${50 + (compass?.economic_axis || 0) * 5}%`,
            top: `${50 - (compass?.social_axis || 0) * 5}%`
          }}
        ></div>
        <div className="absolute bottom-2 text-sm font-bold text-white bg-black/50 px-3 py-1 rounded-full">
          {compass?.label || 'Unknown'}
        </div>
      </div>
    </div>

    <div className="glass-card p-6 rounded-2xl">
      <h3 className="text-xl font-bold text-white mb-4">Core Values</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height={256}>
          <BarChart data={beliefData} layout="vertical" margin={{ left: 40 }}>
            <XAxis type="number" domain={[0, 10]} hide />
            <YAxis dataKey="name" type="category" width={100} tick={{ fill: '#94a3b8', fontSize: 12 }} />
            <Tooltip contentStyle={{ background: '#1e293b', border: 'none' }} />
            <Bar dataKey="value" fill="#8b5cf6" radius={[0, 4, 4, 0]} barSize={20} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>

    {evidenceAxes.length > 0 && (
      <div className="glass-card p-6 rounded-2xl md:col-span-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-xl font-bold text-white">Evidence behind each claim</h3>
          <span className="text-xs text-white/40">
            {calibration.evidence_count ?? quoteTotal} quoted samples · quality{' '}
            <span className="text-white/60">{calibration.evidence_quality || 'unknown'}</span>
          </span>
        </div>
        <p className="text-xs text-white/40 mt-1 mb-4">
          Verbatim from the collected posts — the raw text each position is drawn from.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-96 overflow-y-auto pr-1">
          {evidenceAxes.map(([axis, quotes]) => (
            <div key={axis} className="rounded-xl bg-white/5 border border-white/10 p-3">
              <div className="text-[11px] uppercase tracking-wider text-primary-200 mb-2">
                {axis.replace(/_/g, ' ')}
              </div>
              {quotes.map((quote, i) => (
                <div
                  key={i}
                  className="text-xs text-white/70 italic border-l-2 border-primary-400/30 pl-2 mt-1.5 break-words"
                >
                  {quote}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    )}
  </div>
  );
};

// Receipts shared by the psychology, consumer and lifestyle sections: claim ->
// the verbatim post text it came from. Quotes are checked server-side against
// the collected posts, so anything shown here actually exists in the data.
const Receipts = ({ evidence, rejected, label = 'Receipts' }:
  { evidence?: any[]; rejected?: number; label?: string }) => {
  const rows = (evidence || []).filter((e: any) => e && e.quote);
  if (!rows.length && !rejected) return null;
  return (
    <div className="glass-card p-6 rounded-2xl md:col-span-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-1">
        <h3 className="text-xl font-bold text-white">{label}</h3>
        <span className="text-xs text-white/40">
          {rows.length} verified quote{rows.length === 1 ? '' : 's'}
          {rejected ? ` · ${rejected} rejected` : ''}
        </span>
      </div>
      <p className="text-xs text-white/40 mb-3">
        Verbatim from the collected posts — checked against the source text on the server.
      </p>
      <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
        {rows.map((entry: any, i: number) => (
          <div key={i}>
            <div className="text-[11px] uppercase tracking-wider text-primary-200">{entry.claim || 'claim'}</div>
            <div className="text-xs text-white/70 italic border-l-2 border-primary-400/30 pl-2 mt-1 break-words">
              “{entry.quote}”
            </div>
          </div>
        ))}
        {rejected ? (
          <div className="text-[11px] text-amber-200/80">
            {rejected} suggested quote(s) were rejected because they do not appear in the collected posts.
          </div>
        ) : null}
      </div>
    </div>
  );
};

const ConsumerTab = ({ results }: { results: AnalysisResult }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
    <div className="glass-card p-6 rounded-2xl bg-gradient-to-br from-emerald-500/5 to-transparent">
      <h3 className="text-xl font-bold text-white mb-2">Shopping Persona</h3>
      <div className="text-3xl font-display text-emerald-300 mb-6">
        {results.consumer_profile?.shopping_psychology?.buyer_persona || 'Unknown'}
      </div>
      <div className="space-y-4">
        <h4 className="text-sm font-semibold text-white/60 uppercase">Brand Affinity</h4>
        <div className="flex flex-wrap gap-2">
          {Object.keys(results.consumer_profile?.brand_relationships?.brand_loyalty || {}).map(brand => (
            <span key={brand} className="px-3 py-1 bg-white/5 rounded-full text-sm border border-white/10">{brand}</span>
          ))}
        </div>
      </div>
    </div>

    <div className="glass-card p-6 rounded-2xl">
      <h3 className="text-xl font-bold text-white mb-4">Purchase Forecast (90 Days)</h3>
      <ul className="space-y-3">
        {results.consumer_profile?.forecast_90_day?.predicted_purchases?.map((item: any, i: number) => (
          <li key={i} className="flex gap-3 items-start">
            <span className="text-primary-400 mt-1">➜</span>
            <div>
              <div className="text-white/80">{typeof item === 'string' ? item : item?.product || '—'}</div>
              {item && typeof item !== 'string' && item.confidence != null && (
                <div className="text-white/40 text-xs mt-0.5">Confidence {Math.round(item.confidence * 100)}%</div>
              )}
              {item && typeof item !== 'string' && item.reasoning && (
                <div className="text-white/50 text-xs mt-0.5">{item.reasoning}</div>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>

    <Receipts
      evidence={results.consumer_profile?.evidence}
      rejected={results.consumer_profile?.evidence_rejected}
      label="Consumer receipts"
    />
  </div>
);

const PsychTab = ({ results, psychData }: { results: AnalysisResult, psychData: any[] }) => {
  const ws = results.content_analysis?.writing_style || {};
  const hasStyle = Object.keys(ws).length > 0;
  return (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
    <div className="glass-card p-6 rounded-2xl h-96">
      <h3 className="text-xl font-bold text-white mb-4">Personality (Big 5)</h3>
      <ResponsiveContainer width="100%" height={280}>
        <RadarChart cx="50%" cy="50%" outerRadius="80%" data={psychData}>
          <PolarGrid stroke="#ffffff20" />
          <PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
          <Radar name="Subject" dataKey="A" stroke="#f43f5e" fill="#f43f5e" fillOpacity={0.6} />
          <Tooltip contentStyle={{ background: '#1e293b', border: 'none', color: '#fff' }} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
    <div className="glass-card p-6 rounded-2xl">
      <h3 className="text-xl font-bold text-white mb-4">Communication Style</h3>
      {hasStyle ? (
        <div className="space-y-4">
          <div>
            <div className="text-xs text-white/40 uppercase mb-1">Tone</div>
            <div className="text-lg capitalize text-white">{ws.tone?.replace(/_/g, ' ') || '-'}</div>
          </div>
          <ProgressBar label="Formality" value={Math.round((ws.formality || 0) * 100)} color="bg-blue-500" />
          <ProgressBar label="Humor" value={Math.round((ws.humor_level || 0) * 100)} color="bg-purple-500" />
          <ProgressBar label="Emoji usage" value={Math.round((ws.emoji_usage || 0) * 100)} color="bg-yellow-500" />
          <ProgressBar label="Platform literacy" value={Math.round((ws.platform_literacy || 0) * 100)} color="bg-emerald-500" />
        </div>
      ) : (
        <div className="text-white/40 italic p-4 bg-white/5 rounded-xl">
          No writing-style data in this result.
        </div>
      )}
    </div>

    <Receipts
      evidence={results.content_analysis?.evidence}
      rejected={results.content_analysis?.evidence_rejected}
      label="Psychology receipts"
    />
  </div>
  );
};

const StatBox = ({ label, value, color = 'text-white' }: any) => (
  <div className="bg-white/5 p-4 rounded-xl text-center">
    <div className="text-xs text-white/50 mb-1">{label}</div>
    <div className={`text-xl font-bold ${color}`}>{value || '-'}</div>
  </div>
);

const ProgressBar = ({ label, value, color }: any) => (
  <div>
    <div className="flex justify-between text-sm mb-1 text-white/70">
      <span>{label}</span>
      <span>{value}%</span>
    </div>
    <div className="h-2 bg-white/10 rounded-full overflow-hidden">
      <div className={`h-full ${color}`} style={{ width: `${value}%` }}></div>
    </div>
  </div>
);

const LifestyleTab = ({ results }: { results: AnalysisResult }) => {
  const behavior = results.behavioral_profile || {};
  const interests = behavior.interests || {};
  const pro = behavior.professional || {};
  const rel = behavior.relationships || {};
  const risks = behavior.lifestyle_risks || {};
  const temp = behavior.temperament || {};

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {/* Temperament */}
      <div className="glass-card p-6 rounded-2xl bg-gradient-to-br from-purple-500/10 to-transparent">
        <h3 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
          <BoltIcon className="w-5 h-5 text-yellow-400" /> Temperament
        </h3>
        <div className="text-3xl font-display text-white mb-2">{temp.label || 'Unknown'}</div>
        <p className="text-white/60 text-sm leading-relaxed">{temp.description}</p>
        <div className="mt-4">
          <ProgressBar label="Intensity" value={Math.round((temp.score || 0) * 100)} color="bg-purple-500" />
        </div>
      </div>

      {/* Relationships */}
      <div className="glass-card p-6 rounded-2xl">
        <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
          <HeartIcon className="w-5 h-5 text-pink-400" /> Relationships
        </h3>
        {rel.gated ? (
          <div className="text-sm text-white/50 leading-relaxed">
            <div className="text-amber-200/80 text-xs uppercase tracking-wide mb-1">Not collected</div>
            {rel.reason}
          </div>
        ) : (
        <div className="space-y-4">
          <div>
            <div className="text-xs text-white/40 uppercase">Attachment Style</div>
            <div className="text-lg text-white">{rel.attachment_style || 'Unknown'}</div>
          </div>
          <div>
            <div className="text-xs text-white/40 uppercase">Pattern</div>
            <div className="text-sm text-white/80">{rel.pattern}</div>
          </div>
          <div>
            <div className="text-xs text-white/40 uppercase">Dynamic</div>
            <div className="text-sm text-white/80">
              {rel.relationship_dynamic || rel.sectual_habit_or_dynamic || 'N/A'}
            </div>
          </div>
        </div>
        )}
      </div>

      {/* Professional & Skills */}
      <div className="glass-card p-6 rounded-2xl">
        <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
          <BriefcaseIcon className="w-5 h-5 text-blue-400" /> Professional
        </h3>
        <ul className="space-y-3">
          <li className="flex justify-between">
            <span className="text-white/60">Tech Expert</span>
            <span className={pro.is_tech_expert ? "text-emerald-400" : "text-white/40"}>
              {pro.is_tech_expert ? "Yes" : "No"}
            </span>
          </li>
          <li className="flex justify-between">
            <span className="text-white/60">Skill Level</span>
            <span className="text-white">{pro.tech_skill_level || 'N/A'}</span>
          </li>
          <li className="block">
            <span className="text-white/60 block mb-1">Source</span>
            <span className="text-white text-sm">{pro.earning_source || 'Unknown'}</span>
          </li>
        </ul>
        <div className="mt-4 flex flex-wrap gap-2">
          {pro.personal_skills?.map((s: string, i: number) => (
            <span key={i} className="px-2 py-1 bg-blue-500/20 text-blue-300 text-xs rounded-md">{s}</span>
          ))}
        </div>
      </div>

      {/* Interests & Habits */}
      <div className="glass-card p-6 rounded-2xl md:col-span-2 lg:col-span-3">
        <h3 className="text-xl font-bold text-white mb-4">Interests & Habits</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white/5 p-4 rounded-xl">
            <div className="text-xs text-white/40 uppercase mb-2">Reading Habit</div>
            <div className="text-xl text-white mb-1">{interests.reading_habit || 'Unknown'}</div>
            <div className="text-sm text-white/50">{interests.reading_interests?.join(', ')}</div>
          </div>
          <div className="bg-white/5 p-4 rounded-xl">
            <div className="text-xs text-white/40 uppercase mb-2">Hobbies</div>
            <div className="flex flex-wrap gap-2">
              {interests.hobbies?.map((h: string, i: number) => (
                <span key={i} className="px-2 py-1 bg-white/10 text-white text-xs rounded-full border border-white/10">{h}</span>
              ))}
            </div>
          </div>
          <div className="bg-white/5 p-4 rounded-xl">
            <div className="text-xs text-white/40 uppercase mb-2">Favorites</div>
            <div className="space-y-1">
              <div className="flex gap-2"><span className="text-white/40">Thing:</span> <span className="text-white truncate">{interests.favorites?.thing}</span></div>
              <div className="flex gap-2"><span className="text-white/40">Person:</span> <span className="text-white truncate">{interests.favorites?.person}</span></div>
            </div>
          </div>
        </div>
      </div>

      {/* Resilience & Risk */}
      <div className="glass-card p-6 rounded-2xl md:col-span-2 lg:col-span-3 bg-red-500/5 border border-red-500/10">
        <h3 className="text-xl font-bold text-white mb-2">Risk & Resilience</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div>
            <div className="text-xs text-red-300/60 uppercase mb-1">Resistance Status</div>
            <div className="text-lg text-white mb-2">{behavior.psychological_resilience?.resist_status}</div>
            <p className="text-white/60 text-sm">{behavior.psychological_resilience?.resist_description}</p>
          </div>
          <div>
            <div className="text-xs text-red-300/60 uppercase mb-1">Lifestyle Risk Indicators</div>
            {risks.gated ? (
              <>
                <div className="text-amber-200/80 text-xs uppercase tracking-wide mb-1">Not collected</div>
                <p className="text-white/50 text-sm leading-relaxed">{risks.reason}</p>
              </>
            ) : (
              <>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-white">Substances Indicated:</span>
                  <span className={risks.drug_alcohol_indicated ? "text-red-400 font-bold" : "text-emerald-400"}>
                    {risks.drug_alcohol_indicated ? "YES" : "NO"}
                  </span>
                </div>
                <p className="text-white/60 text-sm">
                  {risks.risk_conclusion || risks.risk_conslusion}
                </p>
              </>
            )}
          </div>
        </div>
      </div>

      <Receipts
        evidence={behavior.evidence}
        rejected={behavior.evidence_rejected}
        label="Lifestyle receipts"
      />

    </div>
  );
};

export default ResultView;
