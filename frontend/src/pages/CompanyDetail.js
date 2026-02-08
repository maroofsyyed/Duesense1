import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getCompany } from '../api';
import {
  ArrowLeft, Building2, Globe, MapPin, Calendar, Users, TrendingUp,
  Shield, Target, DollarSign, FileText, AlertTriangle, CheckCircle,
  ExternalLink, Loader2, Newspaper, Code, BookOpen
} from 'lucide-react';
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell
} from 'recharts';

const TABS = [
  { key: 'overview', label: 'Overview', icon: Building2 },
  { key: 'enrichment', label: 'Enrichment', icon: Globe },
  { key: 'scoring', label: 'Scoring', icon: Target },
  { key: 'memo', label: 'Memo', icon: FileText },
  { key: 'competitors', label: 'Competitors', icon: Users },
];

export default function CompanyDetail() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    loadCompany();
    const interval = setInterval(loadCompany, 5000);
    return () => clearInterval(interval);
  }, [id]);

  const loadCompany = async () => {
    try {
      const res = await getCompany(id);
      setData(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center h-full" data-testid="company-loading">
        <Loader2 size={32} className="animate-spin text-primary" />
      </div>
    );
  }

  const { company, pitch_decks, founders, enrichments, score, competitors, memo } = data;
  const extracted = pitch_decks?.[0]?.extracted_data || {};

  return (
    <div className="p-6 lg:p-8 max-w-[1600px] mx-auto" data-testid="company-detail">
      {/* Header */}
      <div className="mb-6">
        <Link to="/companies" className="text-text-muted text-sm flex items-center gap-1 hover:text-primary mb-4" data-testid="back-link">
          <ArrowLeft size={14} /> Back to Companies
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="font-heading font-black text-3xl text-text-primary tracking-tight" data-testid="company-name">
              {company.name}
            </h1>
            <div className="flex items-center gap-4 mt-2 text-sm text-text-secondary">
              {company.stage && <span className="flex items-center gap-1"><TrendingUp size={14} /> {company.stage}</span>}
              {company.hq_location && <span className="flex items-center gap-1"><MapPin size={14} /> {company.hq_location}</span>}
              {company.founded_year && <span className="flex items-center gap-1"><Calendar size={14} /> Founded {company.founded_year}</span>}
              {company.website && (
                <a href={company.website} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-secondary hover:underline">
                  <Globe size={14} /> Website <ExternalLink size={10} />
                </a>
              )}
            </div>
            {company.tagline && <p className="text-text-muted text-sm mt-2">{company.tagline}</p>}
          </div>
          {score && (
            <div className="text-right bg-surface border border-border rounded-sm p-4" data-testid="score-badge">
              <div className="font-mono text-4xl font-bold text-text-primary">{score.total_score}</div>
              <div className={`text-xs font-mono uppercase mt-1 ${
                score.tier === 'TIER_1' ? 'text-success' : score.tier === 'TIER_2' ? 'text-primary' :
                score.tier === 'TIER_3' ? 'text-warning' : 'text-destructive'
              }`}>{score.tier_label || score.tier?.replace('_', ' ')}</div>
              <div className="text-[10px] text-text-muted mt-1">{score.confidence_level} confidence</div>
            </div>
          )}
        </div>
      </div>

      {/* Status Bar */}
      {company.status !== 'completed' && company.status !== 'failed' && (
        <div className="bg-primary/10 border border-primary/20 rounded-sm p-3 mb-6 flex items-center gap-3" data-testid="status-bar">
          <Loader2 size={16} className="animate-spin text-primary" />
          <span className="text-sm text-primary font-medium capitalize">
            {company.status?.replace('_', ' ')}...
          </span>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-border mb-6 flex gap-1 overflow-x-auto" data-testid="tabs">
        {TABS.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              data-testid={`tab-${tab.key}`}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                activeTab === tab.key
                  ? 'border-primary text-primary'
                  : 'border-transparent text-text-muted hover:text-text-secondary'
              }`}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="animate-fade-in">
        {activeTab === 'overview' && <OverviewTab extracted={extracted} founders={founders} score={score} />}
        {activeTab === 'enrichment' && <EnrichmentTab enrichments={enrichments} />}
        {activeTab === 'scoring' && <ScoringTab score={score} />}
        {activeTab === 'memo' && <MemoTab memo={memo} />}
        {activeTab === 'competitors' && <CompetitorsTab competitors={competitors} enrichments={enrichments} />}
      </div>
    </div>
  );
}

function OverviewTab({ extracted, founders, score }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Problem & Solution */}
      <Card title="Problem" icon={AlertTriangle} testId="problem-card">
        <p className="text-sm text-text-secondary leading-relaxed">
          {extracted?.problem?.statement || 'Not extracted'}
        </p>
        {extracted?.problem?.current_solutions?.length > 0 && (
          <div className="mt-3">
            <span className="text-xs text-text-muted uppercase tracking-widest">Current Solutions</span>
            <ul className="mt-1 space-y-1">
              {extracted.problem.current_solutions.map((s, i) => (
                <li key={i} className="text-xs text-text-secondary">&bull; {s}</li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      <Card title="Solution" icon={CheckCircle} testId="solution-card">
        <p className="text-sm text-text-secondary leading-relaxed">
          {extracted?.solution?.product_description || 'Not extracted'}
        </p>
        {extracted?.solution?.key_features?.length > 0 && (
          <div className="mt-3">
            <span className="text-xs text-text-muted uppercase tracking-widest">Key Features</span>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {extracted.solution.key_features.map((f, i) => (
                <span key={i} className="px-2 py-0.5 text-[11px] bg-primary/10 text-primary border border-primary/20 rounded-sm">{f}</span>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* Market */}
      <Card title="Market Opportunity" icon={TrendingUp} testId="market-card">
        <div className="grid grid-cols-3 gap-3">
          <MetricBox label="TAM" value={extracted?.market?.tam} />
          <MetricBox label="SAM" value={extracted?.market?.sam} />
          <MetricBox label="SOM" value={extracted?.market?.som} />
        </div>
        {extracted?.market?.growth_rate && (
          <p className="text-xs text-text-muted mt-3">Growth: {extracted.market.growth_rate}</p>
        )}
      </Card>

      {/* Traction */}
      <Card title="Traction" icon={DollarSign} testId="traction-card">
        <div className="grid grid-cols-2 gap-3">
          <MetricBox label="Revenue" value={extracted?.traction?.revenue} />
          <MetricBox label="Customers" value={extracted?.traction?.customers} />
          <MetricBox label="Growth" value={extracted?.traction?.growth_rate} />
          <MetricBox label="MRR" value={extracted?.traction?.mrr} />
        </div>
      </Card>

      {/* Founders */}
      <Card title="Founders" icon={Users} testId="founders-card" className="lg:col-span-2">
        {founders?.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {founders.map((f, i) => (
              <div key={i} className="bg-bg p-4 rounded-sm border border-border">
                <div className="font-medium text-text-primary text-sm">{f.name}</div>
                <div className="text-xs text-primary mt-0.5">{f.role}</div>
                {f.previous_companies?.length > 0 && (
                  <div className="text-xs text-text-muted mt-2">
                    Previous: {f.previous_companies.join(', ')}
                  </div>
                )}
                <div className="flex gap-2 mt-2">
                  {f.linkedin_url && f.linkedin_url !== 'not_mentioned' && (
                    <a href={f.linkedin_url} target="_blank" rel="noreferrer" className="text-[10px] text-secondary hover:underline">LinkedIn</a>
                  )}
                  {f.github_url && f.github_url !== 'not_mentioned' && (
                    <a href={f.github_url} target="_blank" rel="noreferrer" className="text-[10px] text-secondary hover:underline">GitHub</a>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-text-muted">No founder data extracted</p>
        )}
      </Card>

      {/* Funding */}
      <Card title="Funding" icon={DollarSign} testId="funding-card">
        <div className="space-y-2">
          <MetricBox label="Seeking" value={extracted?.funding?.seeking} />
          <MetricBox label="Total Raised" value={extracted?.funding?.total_raised} />
          <MetricBox label="Valuation" value={extracted?.funding?.valuation} />
        </div>
      </Card>

      {/* AI/Tech */}
      <Card title="Technology" icon={Code} testId="tech-card">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted">AI Core:</span>
            <span className={`text-xs font-mono ${extracted?.solution?.ai_usage?.is_ai_core ? 'text-success' : 'text-text-secondary'}`}>
              {extracted?.solution?.ai_usage?.is_ai_core ? 'Yes' : 'No'}
            </span>
          </div>
          {extracted?.solution?.technology_stack?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {extracted.solution.technology_stack.map((t, i) => (
                <span key={i} className="px-2 py-0.5 text-[11px] bg-surface-hl text-text-secondary rounded-sm">{t}</span>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

function EnrichmentTab({ enrichments }) {
  if (!enrichments || enrichments.length === 0) {
    return <EmptyState message="No enrichment data yet. Processing may still be in progress." />;
  }

  return (
    <div className="space-y-6">
      {enrichments.map((e, i) => (
        <Card key={i} title={e.source_type?.replace('_', ' ')} icon={getSourceIcon(e.source_type)} testId={`enrichment-${e.source_type}`}>
          <div className="flex items-center gap-2 mb-3">
            {e.source_url && (
              <a href={e.source_url} target="_blank" rel="noreferrer" className="text-xs text-secondary flex items-center gap-1 hover:underline">
                <ExternalLink size={10} /> {e.source_url}
              </a>
            )}
            <span className="text-[10px] text-text-muted">{e.fetched_at ? new Date(e.fetched_at).toLocaleString() : ''}</span>
          </div>
          <div className="bg-bg p-4 rounded-sm border border-border max-h-[400px] overflow-y-auto">
            <pre className="text-xs text-text-secondary font-mono whitespace-pre-wrap">
              {JSON.stringify(e.data, null, 2)}
            </pre>
          </div>
        </Card>
      ))}
    </div>
  );
}

function ScoringTab({ score }) {
  if (!score) return <EmptyState message="Scoring not yet complete." />;

  const radarData = [
    { subject: 'Founders', value: (score.founder_score / 30) * 100, fullMark: 100 },
    { subject: 'Market', value: (score.market_score / 20) * 100, fullMark: 100 },
    { subject: 'Moat', value: (score.moat_score / 20) * 100, fullMark: 100 },
    { subject: 'Traction', value: (score.traction_score / 20) * 100, fullMark: 100 },
    { subject: 'Model', value: (score.model_score / 10) * 100, fullMark: 100 },
  ];

  const barData = [
    { name: 'Founders', score: score.founder_score, max: 30, fill: '#6366f1' },
    { name: 'Market', score: score.market_score, max: 20, fill: '#3b82f6' },
    { name: 'Moat', score: score.moat_score, max: 20, fill: '#8b5cf6' },
    { name: 'Traction', score: score.traction_score, max: 20, fill: '#10b981' },
    { name: 'Model', score: score.model_score, max: 10, fill: '#f59e0b' },
  ];

  return (
    <div className="space-y-6" data-testid="scoring-tab-content">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Radar Chart */}
        <Card title="Score Profile" icon={Target} testId="radar-chart">
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#27272a" />
              <PolarAngleAxis dataKey="subject" tick={{ fill: '#a1a1aa', fontSize: 12 }} />
              <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
              <Radar dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} strokeWidth={2} />
            </RadarChart>
          </ResponsiveContainer>
        </Card>

        {/* Bar Chart */}
        <Card title="Score Breakdown" icon={TrendingUp} testId="score-breakdown">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={barData} layout="vertical">
              <XAxis type="number" domain={[0, 30]} tick={{ fill: '#a1a1aa', fontSize: 11 }} axisLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fill: '#a1a1aa', fontSize: 11 }} axisLine={false} width={80} />
              <Tooltip
                contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '2px', color: '#fafafa' }}
                formatter={(val, name, props) => [`${val}/${props.payload.max}`, 'Score']}
              />
              <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                {barData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Thesis & Recommendation */}
      <Card title="Investment Thesis" icon={BookOpen} testId="investment-thesis">
        <div className="flex items-center gap-3 mb-4">
          <span className={`px-3 py-1 text-sm font-mono font-bold rounded-sm ${
            score.recommendation === 'STRONG BUY' ? 'bg-success/10 text-success border border-success/20' :
            score.recommendation === 'BUY' ? 'bg-primary/10 text-primary border border-primary/20' :
            score.recommendation === 'HOLD' ? 'bg-warning/10 text-warning border border-warning/20' :
            'bg-destructive/10 text-destructive border border-destructive/20'
          }`} data-testid="recommendation-badge">
            {score.recommendation}
          </span>
          {score.expected_return && (
            <span className="text-sm text-text-secondary">Expected: {score.expected_return}</span>
          )}
        </div>
        <p className="text-sm text-text-secondary leading-relaxed">{score.investment_thesis}</p>
      </Card>

      {/* Reasons & Risks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Top Reasons to Invest" icon={CheckCircle} testId="top-reasons">
          <div className="space-y-3">
            {(score.top_reasons || []).map((r, i) => (
              <div key={i} className="flex gap-3">
                <span className="text-success font-mono text-sm font-bold">{i + 1}.</span>
                <p className="text-sm text-text-secondary">{r}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Top Risks" icon={AlertTriangle} testId="top-risks">
          <div className="space-y-3">
            {(score.top_risks || []).map((r, i) => (
              <div key={i} className="flex gap-3">
                <span className="text-destructive font-mono text-sm font-bold">{i + 1}.</span>
                <p className="text-sm text-text-secondary">{r}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Agent Details */}
      {score.agent_details && (
        <Card title="Agent Analysis Details" icon={Shield} testId="agent-details">
          <div className="space-y-4">
            {Object.entries(score.agent_details).map(([key, detail]) => (
              <div key={key} className="bg-bg p-4 rounded-sm border border-border">
                <h4 className="text-sm font-medium text-text-primary capitalize mb-2">{key.replace('_', ' ')} Agent</h4>
                <p className="text-xs text-text-secondary">{detail?.reasoning || 'No reasoning provided'}</p>
                <span className="text-[10px] text-text-muted mt-2 block">
                  Confidence: {detail?.confidence || 'N/A'}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function MemoTab({ memo }) {
  if (!memo || !memo.sections) return <EmptyState message="Investment memo not yet generated." />;

  return (
    <div className="space-y-6" data-testid="memo-tab-content">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-heading font-bold text-xl text-text-primary">{memo.title}</h2>
          <p className="text-xs text-text-muted mt-1">{memo.date}</p>
        </div>
      </div>

      {memo.sections.map((section, i) => (
        <div key={i} className="bg-surface border border-border rounded-sm p-6 animate-fade-in" style={{ animationDelay: `${i * 60}ms` }} data-testid={`memo-section-${i}`}>
          <h3 className="font-heading font-bold text-lg text-text-primary mb-3">{section.title}</h3>
          <div className="text-sm text-text-secondary leading-relaxed whitespace-pre-wrap">{section.content}</div>
        </div>
      ))}
    </div>
  );
}

function CompetitorsTab({ competitors, enrichments }) {
  const compData = enrichments?.find(e => e.source_type === 'competitors')?.data;

  if ((!competitors || competitors.length === 0) && !compData) {
    return <EmptyState message="Competitor data not yet available." />;
  }

  const items = competitors?.length > 0 ? competitors : (compData?.competitors || []);

  return (
    <div className="space-y-4" data-testid="competitors-tab-content">
      <h3 className="font-heading font-bold text-lg text-text-primary">
        Discovered Competitors ({items.length})
      </h3>
      {items.map((c, i) => (
        <div key={i} className="bg-surface border border-border rounded-sm p-4 hover:border-primary/20 transition-colors" data-testid={`competitor-${i}`}>
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h4 className="text-sm font-medium text-text-primary">{c.name || c.title}</h4>
              <p className="text-xs text-text-secondary mt-1 line-clamp-2">{c.description || c.snippet}</p>
            </div>
            {(c.url || c.url) && (
              <a href={c.url} target="_blank" rel="noreferrer" className="text-secondary hover:underline shrink-0 ml-4">
                <ExternalLink size={14} />
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// Shared Components
function Card({ title, icon: Icon, children, testId, className = '' }) {
  return (
    <div className={`bg-surface border border-border rounded-sm p-6 ${className}`} data-testid={testId}>
      <div className="flex items-center gap-2 mb-4">
        {Icon && <Icon size={18} className="text-primary" />}
        <h3 className="font-heading font-bold text-base text-text-primary">{title}</h3>
      </div>
      {children}
    </div>
  );
}

function MetricBox({ label, value }) {
  const displayVal = value && value !== 'not_mentioned' && value !== 'null' ? value : 'N/A';
  return (
    <div className="bg-bg p-3 rounded-sm border border-border">
      <div className="text-[10px] text-text-muted uppercase tracking-widest">{label}</div>
      <div className="text-sm font-mono font-medium text-text-primary mt-1">{String(displayVal)}</div>
    </div>
  );
}

function EmptyState({ message }) {
  return (
    <div className="text-center py-16" data-testid="empty-state">
      <FileText size={40} className="mx-auto text-text-muted mb-3" />
      <p className="text-text-secondary text-sm">{message}</p>
    </div>
  );
}

function getSourceIcon(type) {
  const map = { github: Code, news: Newspaper, website: Globe, competitors: Users, market_research: TrendingUp };
  return map[type] || Globe;
}
