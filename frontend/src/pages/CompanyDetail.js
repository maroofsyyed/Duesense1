import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getCompany, rerunScoring } from '../api';
import {
  ArrowLeft, Building2, Globe, MapPin, Calendar, Users, TrendingUp,
  Shield, Target, DollarSign, FileText, AlertTriangle, CheckCircle,
  ExternalLink, Loader2, Newspaper, Code, BookOpen, Zap,
  Monitor, ShieldCheck, Briefcase, BarChart3, Eye
} from 'lucide-react';
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell
} from 'recharts';

const TABS = [
  { key: 'overview', label: 'Overview', icon: Building2 },
  { key: 'website_intel', label: 'Website Intel', icon: Monitor },
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

  const loadCompany = useCallback(async () => {
    try {
      const res = await getCompany(id);
      setData(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadCompany();
    const interval = setInterval(loadCompany, 5000);
    return () => clearInterval(interval);
  }, [loadCompany]);

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center h-full" data-testid="company-loading">
        <Loader2 size={32} className="animate-spin text-primary" />
      </div>
    );
  }

  const { company, pitch_decks, founders, enrichments, score, competitors, memo } = data;
  const extracted = pitch_decks?.[0]?.extracted_data || {};
  const websiteIntel = enrichments?.find(e => e.source_type === 'website_intelligence')?.data || null;

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
            <div className="flex items-center gap-4 mt-2 text-sm text-text-secondary flex-wrap">
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
              <div className={`text-xs font-mono uppercase mt-1 ${score.tier === 'TIER_1' ? 'text-success' : score.tier === 'TIER_2' ? 'text-primary' :
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
          <span className="text-sm text-primary font-medium capitalize">{company.status?.replace('_', ' ')}...</span>
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
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${activeTab === tab.key
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
      <div className="animate-fade-in" key={activeTab}>
        {activeTab === 'overview' && <OverviewTab extracted={extracted} founders={founders} score={score} />}
        {activeTab === 'website_intel' && <WebsiteIntelTab data={websiteIntel} score={score} />}
        {activeTab === 'enrichment' && <EnrichmentTab enrichments={enrichments} />}
        {activeTab === 'scoring' && <ScoringTab score={score} companyId={company.id} onRefresh={loadCompany} />}
        {activeTab === 'memo' && <MemoTab memo={memo} />}
        {activeTab === 'competitors' && <CompetitorsTab competitors={competitors} enrichments={enrichments} />}
      </div>
    </div>
  );
}

// ============ WEBSITE INTELLIGENCE TAB ============
function WebsiteIntelTab({ data, score }) {
  if (!data) {
    return <EmptyState message="Website intelligence not yet available. Deep crawl may still be in progress." />;
  }

  const summary = data.intelligence_summary || {};
  const crawlMeta = data.crawl_meta || {};
  const techStack = data.tech_stack || {};
  const salesSignals = data.sales_signals || {};
  const productIntel = data.product_intel || {};
  const revenueModel = data.revenue_model || {};
  const customerValidation = data.customer_validation || {};
  const teamIntel = data.team_intel || {};
  const technicalDepth = data.technical_depth || {};
  const tractionSignals = data.traction_signals || {};
  const compliance = data.compliance || {};

  const overallScore = summary.overall_score || 0;
  const scoreBreakdown = summary.score_breakdown || {};

  const breakdownData = [
    { name: 'Design/UX', score: scoreBreakdown.design_ux || 0, max: 20, fill: '#6366f1' },
    { name: 'Content', score: scoreBreakdown.content_quality || 0, max: 20, fill: '#3b82f6' },
    { name: 'Technical', score: scoreBreakdown.technical_execution || 0, max: 20, fill: '#8b5cf6' },
    { name: 'Traction', score: scoreBreakdown.traction_signals || 0, max: 20, fill: '#10b981' },
    { name: 'Trust', score: scoreBreakdown.trust_signals || 0, max: 20, fill: '#f59e0b' },
  ];

  return (
    <div className="space-y-6" data-testid="website-intel-tab">
      {/* Header with overall score */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card title="Website Quality Score" icon={Monitor} testId="wi-overall-score" className="lg:col-span-1">
          <div className="flex flex-col items-center py-4">
            <div className="relative w-32 h-32">
              <svg className="w-32 h-32 transform -rotate-90" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="52" stroke="#27272a" strokeWidth="8" fill="none" />
                <circle cx="60" cy="60" r="52" stroke={overallScore >= 70 ? '#10b981' : overallScore >= 50 ? '#f59e0b' : '#ef4444'}
                  strokeWidth="8" fill="none" strokeDasharray={`${(overallScore / 100) * 327} 327`} strokeLinecap="round" />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="font-mono text-3xl font-bold text-text-primary">{overallScore}</span>
              </div>
            </div>
            <p className="text-sm text-text-secondary mt-3 text-center">{summary.one_line_verdict || 'Analysis complete'}</p>
          </div>
          <div className="text-xs text-text-muted mt-2 text-center">
            {crawlMeta.pages_crawled || 0}/{crawlMeta.pages_attempted || 0} pages analyzed
          </div>
        </Card>

        {/* Score Breakdown Bar */}
        <Card title="Score Breakdown" icon={BarChart3} testId="wi-breakdown" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={breakdownData} layout="vertical">
              <XAxis type="number" domain={[0, 20]} tick={{ fill: '#a1a1aa', fontSize: 11 }} axisLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fill: '#a1a1aa', fontSize: 11 }} axisLine={false} width={70} />
              <Tooltip
                contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '2px', color: '#fafafa' }}
                formatter={(val, name, props) => [`${val}/${props.payload.max}`, 'Score']}
              />
              <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                {breakdownData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Red/Green Flags */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Green Flags" icon={CheckCircle} testId="wi-green-flags">
          <div className="space-y-2">
            {(summary.green_flags || []).length > 0 ? (
              summary.green_flags.map((f, i) => (
                <div key={i} className="flex items-start gap-2 p-2 rounded-sm bg-success/5 border border-success/10">
                  <CheckCircle size={14} className="text-success mt-0.5 shrink-0" />
                  <span className="text-sm text-text-secondary">{f}</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-text-muted">No green flags detected</p>
            )}
          </div>
        </Card>

        <Card title="Red Flags" icon={AlertTriangle} testId="wi-red-flags">
          <div className="space-y-2">
            {(summary.red_flags || []).length > 0 ? (
              summary.red_flags.map((f, i) => (
                <div key={i} className="flex items-start gap-2 p-2 rounded-sm bg-destructive/5 border border-destructive/10">
                  <AlertTriangle size={14} className="text-destructive mt-0.5 shrink-0" />
                  <span className="text-sm text-text-secondary">{f}</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-text-muted">No red flags detected</p>
            )}
          </div>
        </Card>
      </div>

      {/* GTM Motion & Revenue Model */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Go-To-Market Motion" icon={Briefcase} testId="wi-gtm">
          <div className="space-y-3">
            <MetricRow label="Sales Motion" value={summary.gtm_motion?.type || revenueModel.sales_motion} />
            <MetricRow label="Target Segment" value={summary.gtm_motion?.target || (revenueModel.target_segments || []).join(', ')} />
            <MetricRow label="Pricing Transparency" value={summary.gtm_motion?.pricing_transparency || revenueModel.pricing_transparency} />
            <MetricRow label="Pricing Model" value={revenueModel.pricing_model} />
            <MetricRow label="Free Trial" value={revenueModel.free_trial ? 'Yes' : revenueModel.free_trial === false ? 'No' : 'N/A'} />
            {(revenueModel.price_points || []).length > 0 && (
              <div>
                <span className="text-[10px] text-text-muted uppercase tracking-widest">Price Points</span>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {revenueModel.price_points.map((p, i) => (
                    <span key={i} className="px-2 py-0.5 text-[11px] bg-success/10 text-success border border-success/20 rounded-sm">{p}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>

        <Card title="Sales Signals" icon={DollarSign} testId="wi-sales-signals">
          <div className="grid grid-cols-2 gap-2">
            <SignalPill label="Contact Form" active={salesSignals.has_contact_form} />
            <SignalPill label="Demo CTA" active={salesSignals.has_demo_cta} />
            <SignalPill label="Talk to Sales" active={salesSignals.has_talk_to_sales} />
            <SignalPill label="Free Trial" active={salesSignals.has_free_trial} />
            <SignalPill label="Phone Number" active={salesSignals.has_phone_number} />
            <SignalPill label="Live Chat" active={salesSignals.has_live_chat} />
            <SignalPill label="Calendly" active={salesSignals.has_calendly} />
            <SignalPill label="Newsletter" active={salesSignals.has_newsletter} />
          </div>
          {salesSignals.sales_motion && (
            <div className="mt-3 pt-3 border-t border-border">
              <span className="text-[10px] text-text-muted uppercase tracking-widest">Detected Motion</span>
              <div className="text-sm font-medium text-primary mt-1">{salesSignals.sales_motion}</div>
            </div>
          )}
        </Card>
      </div>

      {/* Tech Stack */}
      <Card title="Detected Technology Stack" icon={Code} testId="wi-tech-stack">
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          {Object.entries(techStack).map(([category, tools]) => (
            <div key={category}>
              <span className="text-[10px] text-text-muted uppercase tracking-widest">{category}</span>
              <div className="space-y-1 mt-2">
                {(tools || []).length > 0 ? tools.map((t, i) => (
                  <div key={i} className="px-2 py-1 text-xs bg-surface-hl text-text-secondary rounded-sm border border-border">{t}</div>
                )) : (
                  <div className="text-xs text-text-muted">None detected</div>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Agent Details Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Product Intelligence */}
        <Card title="Product Intelligence" icon={Zap} testId="wi-product">
          {productIntel.extracted !== false ? (
            <div className="space-y-3">
              {productIntel.product_positioning && (
                <div>
                  <span className="text-[10px] text-text-muted uppercase tracking-widest">Positioning</span>
                  <p className="text-sm text-text-secondary mt-1">{productIntel.product_positioning}</p>
                </div>
              )}
              {(productIntel.value_propositions || []).length > 0 && (
                <div>
                  <span className="text-[10px] text-text-muted uppercase tracking-widest">Value Props</span>
                  <ul className="mt-1 space-y-1">
                    {productIntel.value_propositions.map((v, i) => (
                      <li key={i} className="text-xs text-text-secondary flex items-start gap-1">
                        <CheckCircle size={10} className="text-primary mt-0.5 shrink-0" /> {v}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {(productIntel.key_features || []).length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {productIntel.key_features.slice(0, 8).map((f, i) => (
                    <span key={i} className="px-2 py-0.5 text-[11px] bg-primary/10 text-primary border border-primary/20 rounded-sm">{f}</span>
                  ))}
                </div>
              )}
              <ScoreIndicator label="Product Maturity" score={productIntel.product_maturity_score} max={10} />
            </div>
          ) : (
            <p className="text-sm text-text-muted">No product pages found</p>
          )}
        </Card>

        {/* Customer Validation */}
        <Card title="Customer Validation" icon={Users} testId="wi-customers">
          {customerValidation.extracted !== false ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <MetricBox label="Customer Logos" value={customerValidation.customer_logo_count} />
                <MetricBox label="Case Studies" value={customerValidation.case_study_count} />
              </div>
              {(customerValidation.notable_customers || []).length > 0 && (
                <div>
                  <span className="text-[10px] text-text-muted uppercase tracking-widest">Notable Customers</span>
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {customerValidation.notable_customers.map((c, i) => (
                      <span key={i} className="px-2 py-0.5 text-[11px] bg-success/10 text-success border border-success/20 rounded-sm">{c}</span>
                    ))}
                  </div>
                </div>
              )}
              {(customerValidation.industry_verticals || []).length > 0 && (
                <div>
                  <span className="text-[10px] text-text-muted uppercase tracking-widest">Industry Verticals</span>
                  <p className="text-xs text-text-secondary mt-1">{customerValidation.industry_verticals.join(', ')}</p>
                </div>
              )}
              <ScoreIndicator label="Customer Validation" score={customerValidation.customer_validation_score} max={10} />
            </div>
          ) : (
            <p className="text-sm text-text-muted">No customer pages found</p>
          )}
        </Card>

        {/* Team Intelligence */}
        <Card title="Team & Hiring Intelligence" icon={Users} testId="wi-team">
          {teamIntel.extracted !== false ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <MetricBox label="Team Size Est." value={teamIntel.team_size_estimate} />
                <MetricBox label="Open Positions" value={teamIntel.open_positions_count} />
                <MetricBox label="Eng Roles" value={teamIntel.engineering_roles_count} />
                <MetricBox label="Hiring Velocity" value={teamIntel.hiring_velocity} />
              </div>
              {(teamIntel.office_locations || []).length > 0 && (
                <div className="text-xs text-text-secondary">
                  <MapPin size={10} className="inline mr-1" />
                  {teamIntel.office_locations.join(', ')}
                </div>
              )}
              {teamIntel.remote_friendly && (
                <span className="text-xs text-success">Remote Friendly</span>
              )}
              <ScoreIndicator label="Team Quality" score={teamIntel.team_quality_score} max={10} />
            </div>
          ) : (
            <p className="text-sm text-text-muted">No team pages found</p>
          )}
        </Card>

        {/* Technical Depth */}
        <Card title="Technical Credibility" icon={Shield} testId="wi-technical">
          {technicalDepth.extracted !== false ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <SignalPill label="API Available" active={technicalDepth.api_available} />
                <SignalPill label="Tech Blog Active" active={technicalDepth.tech_blog_active} />
                <SignalPill label="Open Source" active={technicalDepth.open_source_mentions} />
              </div>
              {technicalDepth.api_type && <MetricRow label="API Type" value={technicalDepth.api_type} />}
              {technicalDepth.documentation_quality && <MetricRow label="Docs Quality" value={technicalDepth.documentation_quality} />}
              {(technicalDepth.security_certifications || []).length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {technicalDepth.security_certifications.map((c, i) => (
                    <span key={i} className="px-2 py-0.5 text-[11px] bg-success/10 text-success border border-success/20 rounded-sm flex items-center gap-1">
                      <ShieldCheck size={10} /> {c}
                    </span>
                  ))}
                </div>
              )}
              <ScoreIndicator label="Technical Credibility" score={technicalDepth.technical_credibility_score} max={10} />
            </div>
          ) : (
            <p className="text-sm text-text-muted">No technical pages found</p>
          )}
        </Card>

        {/* Traction Signals */}
        <Card title="Traction Signals" icon={TrendingUp} testId="wi-traction">
          {tractionSignals.extracted !== false ? (
            <div className="space-y-3">
              <MetricRow label="Content Freshness" value={tractionSignals.content_freshness} />
              <MetricRow label="Blog Frequency" value={tractionSignals.blog_post_frequency} />
              <MetricRow label="Latest Content" value={tractionSignals.latest_content_date} />
              {(tractionSignals.press_mentions || []).length > 0 && (
                <div>
                  <span className="text-[10px] text-text-muted uppercase tracking-widest">Press Mentions</span>
                  <p className="text-xs text-text-secondary mt-1">{tractionSignals.press_mentions.join(', ')}</p>
                </div>
              )}
              {tractionSignals.user_volume_claims && (
                <MetricRow label="Volume Claims" value={tractionSignals.user_volume_claims} />
              )}
              <ScoreIndicator label="Traction Signals" score={tractionSignals.traction_signals_score} max={10} />
            </div>
          ) : (
            <p className="text-sm text-text-muted">No traction pages found</p>
          )}
        </Card>

        {/* Compliance */}
        <Card title="Compliance & Trust" icon={ShieldCheck} testId="wi-compliance">
          {compliance.extracted !== false ? (
            <div className="space-y-3">
              {(compliance.security_certifications || []).length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {compliance.security_certifications.map((c, i) => (
                    <span key={i} className="px-2 py-0.5 text-[11px] bg-success/10 text-success border border-success/20 rounded-sm">{c}</span>
                  ))}
                </div>
              )}
              {(compliance.compliance_standards || []).length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {compliance.compliance_standards.map((c, i) => (
                    <span key={i} className="px-2 py-0.5 text-[11px] bg-primary/10 text-primary border border-primary/20 rounded-sm">{c}</span>
                  ))}
                </div>
              )}
              <MetricRow label="Privacy Policy" value={compliance.privacy_policy_quality} />
              <MetricRow label="Uptime SLA" value={compliance.uptime_sla} />
              <div className="grid grid-cols-2 gap-2">
                <SignalPill label="Data Residency" active={compliance.data_residency_options} />
                <SignalPill label="Bug Bounty" active={compliance.bug_bounty} />
              </div>
              <ScoreIndicator label="Trust Score" score={compliance.trust_score} max={10} />
            </div>
          ) : (
            <p className="text-sm text-text-muted">No compliance pages found</p>
          )}
        </Card>
      </div>

      {/* Market Positioning */}
      {summary.market_positioning && (
        <Card title="Market Positioning" icon={Eye} testId="wi-positioning">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div>
              <span className="text-[10px] text-text-muted uppercase tracking-widest">Category</span>
              <p className="text-sm text-text-primary mt-1 font-medium">{summary.market_positioning.category || 'N/A'}</p>
            </div>
            <div>
              <span className="text-[10px] text-text-muted uppercase tracking-widest">Positioning</span>
              <p className="text-sm text-text-secondary mt-1">{summary.market_positioning.positioning || 'N/A'}</p>
            </div>
            <div>
              <span className="text-[10px] text-text-muted uppercase tracking-widest">Unique Angle</span>
              <p className="text-sm text-text-secondary mt-1">{summary.market_positioning.unique_angle || 'N/A'}</p>
            </div>
          </div>
          {(summary.market_positioning.competitors_mentioned || []).length > 0 && (
            <div className="mt-4 pt-4 border-t border-border">
              <span className="text-[10px] text-text-muted uppercase tracking-widest">Competitors Mentioned on Website</span>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {summary.market_positioning.competitors_mentioned.map((c, i) => (
                  <span key={i} className="px-2 py-0.5 text-[11px] bg-warning/10 text-warning border border-warning/20 rounded-sm">{c}</span>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Revenue Model Assessment */}
      {summary.revenue_model_assessment && (
        <Card title="Revenue Model Assessment" icon={DollarSign} testId="wi-revenue-assessment">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <span className="text-[10px] text-text-muted uppercase tracking-widest">Model</span>
              <p className="text-sm text-text-primary mt-1 font-medium">{summary.revenue_model_assessment.model || 'N/A'}</p>
            </div>
            <div>
              <span className="text-[10px] text-text-muted uppercase tracking-widest">Strategy</span>
              <p className="text-sm text-text-secondary mt-1">{summary.revenue_model_assessment.pricing_strategy || 'N/A'}</p>
            </div>
            <div>
              <span className="text-[10px] text-text-muted uppercase tracking-widest">Est. Deal Size</span>
              <p className="text-sm text-text-secondary mt-1">{summary.revenue_model_assessment.deal_size_estimate || 'N/A'}</p>
            </div>
            <div>
              <span className="text-[10px] text-text-muted uppercase tracking-widest">Sales Complexity</span>
              <p className="text-sm text-text-secondary mt-1">{summary.revenue_model_assessment.sales_complexity || 'N/A'}</p>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

// ============ OVERVIEW TAB ============
function OverviewTab({ extracted, founders, score }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Problem" icon={AlertTriangle} testId="problem-card">
        <p className="text-sm text-text-secondary leading-relaxed">{extracted?.problem?.statement || 'Not extracted'}</p>
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
        <p className="text-sm text-text-secondary leading-relaxed">{extracted?.solution?.product_description || 'Not extracted'}</p>
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

      <Card title="Market Opportunity" icon={TrendingUp} testId="market-card">
        <div className="grid grid-cols-3 gap-3">
          <MetricBox label="TAM" value={extracted?.market?.tam} />
          <MetricBox label="SAM" value={extracted?.market?.sam} />
          <MetricBox label="SOM" value={extracted?.market?.som} />
        </div>
        {extracted?.market?.growth_rate && <p className="text-xs text-text-muted mt-3">Growth: {extracted.market.growth_rate}</p>}
      </Card>

      <Card title="Traction" icon={DollarSign} testId="traction-card">
        <div className="grid grid-cols-2 gap-3">
          <MetricBox label="Revenue" value={extracted?.traction?.revenue} />
          <MetricBox label="Customers" value={extracted?.traction?.customers} />
          <MetricBox label="Growth" value={extracted?.traction?.growth_rate} />
          <MetricBox label="MRR" value={extracted?.traction?.mrr} />
        </div>
      </Card>

      <Card title="Founders" icon={Users} testId="founders-card" className="lg:col-span-2">
        {founders?.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {founders.map((f, i) => (
              <div key={i} className="bg-bg p-4 rounded-sm border border-border">
                <div className="font-medium text-text-primary text-sm">{f.name}</div>
                <div className="text-xs text-primary mt-0.5">{f.role}</div>
                {f.previous_companies?.length > 0 && (
                  <div className="text-xs text-text-muted mt-2">Previous: {f.previous_companies.join(', ')}</div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-text-muted">No founder data extracted</p>
        )}
      </Card>

      <Card title="Funding" icon={DollarSign} testId="funding-card">
        <div className="space-y-2">
          <MetricBox label="Seeking" value={extracted?.funding?.seeking} />
          <MetricBox label="Total Raised" value={extracted?.funding?.total_raised} />
          <MetricBox label="Valuation" value={extracted?.funding?.valuation} />
        </div>
      </Card>

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

      {/* Website Due Diligence Card */}
      {score?.website_dd_score !== undefined && (
        <Card title="Website Due Diligence" icon={Eye} testId="website-dd-card" className="lg:col-span-2">
          <WebsiteDDCard score={score} />
        </Card>
      )}
    </div>
  );
}

// ============ ENRICHMENT TAB ============
function EnrichmentTab({ enrichments }) {
  if (!enrichments || enrichments.length === 0) {
    return <EmptyState message="No enrichment data yet." />;
  }

  return (
    <div className="space-y-6">
      {enrichments.filter(e => e.source_type !== 'website_intelligence').map((e, i) => (
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

// ============ SCORING TAB ============
function ScoringTab({ score, companyId, onRefresh }) {
  const [rerunning, setRerunning] = useState(false);
  const [rerunTriggered, setRerunTriggered] = useState(false);

  const handleRerunScoring = async () => {
    try {
      setRerunning(true);
      await rerunScoring(companyId);
      setRerunTriggered(true);
      // Start polling for score
      setTimeout(() => onRefresh?.(), 3000);
    } catch (e) {
      console.error('Failed to trigger re-scoring:', e);
    } finally {
      setRerunning(false);
    }
  };

  if (!score) return (
    <div className="flex flex-col items-center justify-center py-16 text-center" data-testid="scoring-empty">
      <Target size={48} className="text-text-muted mb-4" />
      <p className="text-text-muted text-sm mb-4">
        {rerunTriggered ? 'Scoring in progress — this page will auto-refresh...' : 'Scoring not yet complete.'}
      </p>
      {!rerunTriggered ? (
        <button
          onClick={handleRerunScoring}
          disabled={rerunning}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-sm text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
          data-testid="rerun-scoring-btn"
        >
          {rerunning ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
          {rerunning ? 'Triggering...' : 'Run Scoring'}
        </button>
      ) : (
        <Loader2 size={24} className="animate-spin text-primary" />
      )}
    </div>
  );

  const radarData = [
    { subject: 'Founders', value: (score.founder_score / 25) * 100, fullMark: 100 },
    { subject: 'Market', value: (score.market_score / 20) * 100, fullMark: 100 },
    { subject: 'Moat', value: (score.moat_score / 20) * 100, fullMark: 100 },
    { subject: 'Traction', value: (score.traction_score / 15) * 100, fullMark: 100 },
    { subject: 'Model', value: (score.model_score / 10) * 100, fullMark: 100 },
    { subject: 'Website', value: ((score.website_score || 0) / 10) * 100, fullMark: 100 },
  ];

  const barData = [
    { name: 'Founders', score: score.founder_score, max: 25, fill: '#6366f1' },
    { name: 'Market', score: score.market_score, max: 20, fill: '#3b82f6' },
    { name: 'Moat', score: score.moat_score, max: 20, fill: '#8b5cf6' },
    { name: 'Traction', score: score.traction_score, max: 15, fill: '#10b981' },
    { name: 'Model', score: score.model_score, max: 10, fill: '#f59e0b' },
    { name: 'Website', score: score.website_score || 0, max: 10, fill: '#ec4899' },
  ];

  return (
    <div className="space-y-6" data-testid="scoring-tab-content">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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

        <Card title="Score Breakdown" icon={TrendingUp} testId="score-breakdown">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={barData} layout="vertical">
              <XAxis type="number" domain={[0, 25]} tick={{ fill: '#a1a1aa', fontSize: 11 }} axisLine={false} />
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

      <Card title="Investment Thesis" icon={BookOpen} testId="investment-thesis">
        <div className="flex items-center gap-3 mb-4">
          <span className={`px-3 py-1 text-sm font-mono font-bold rounded-sm ${score.recommendation === 'STRONG BUY' ? 'bg-success/10 text-success border border-success/20' :
              score.recommendation === 'BUY' ? 'bg-primary/10 text-primary border border-primary/20' :
                score.recommendation === 'HOLD' ? 'bg-warning/10 text-warning border border-warning/20' :
                  'bg-destructive/10 text-destructive border border-destructive/20'
            }`} data-testid="recommendation-badge">
            {score.recommendation}
          </span>
          {score.expected_return && <span className="text-sm text-text-secondary">Expected: {score.expected_return}</span>}
        </div>
        <p className="text-sm text-text-secondary leading-relaxed">{score.investment_thesis}</p>
      </Card>

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

      {score.agent_details && (
        <Card title="Agent Analysis Details" icon={Shield} testId="agent-details">
          <div className="space-y-4">
            {Object.entries(score.agent_details).map(([key, detail]) => (
              <div key={key} className="bg-bg p-4 rounded-sm border border-border">
                <h4 className="text-sm font-medium text-text-primary capitalize mb-2">{key.replace(/_/g, ' ')} Agent</h4>
                <p className="text-xs text-text-secondary">{detail?.reasoning || detail?.one_line_verdict || 'No reasoning provided'}</p>
                <span className="text-[10px] text-text-muted mt-2 block">Confidence: {detail?.confidence || 'N/A'}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

// ============ MEMO TAB ============
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

// ============ COMPETITORS TAB ============
function CompetitorsTab({ competitors, enrichments }) {
  const compData = enrichments?.find(e => e.source_type === 'competitors')?.data;
  if ((!competitors || competitors.length === 0) && !compData) {
    return <EmptyState message="Competitor data not yet available." />;
  }
  const items = competitors?.length > 0 ? competitors : (compData?.competitors || []);
  return (
    <div className="space-y-4" data-testid="competitors-tab-content">
      <h3 className="font-heading font-bold text-lg text-text-primary">Discovered Competitors ({items.length})</h3>
      {items.map((c, i) => (
        <div key={i} className="bg-surface border border-border rounded-sm p-4 hover:border-primary/20 transition-colors" data-testid={`competitor-${i}`}>
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h4 className="text-sm font-medium text-text-primary">{c.name || c.title}</h4>
              <p className="text-xs text-text-secondary mt-1 line-clamp-2">{c.description || c.snippet}</p>
            </div>
            {c.url && (
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


// ============ WEBSITE DD CARD ============
function WebsiteDDCard({ score }) {
  const ddDetails = score?.agent_details?.website_due_diligence || {};
  const ddScore = score?.website_dd_score || 0;
  const breakdown = ddDetails?.breakdown || {};
  const redFlags = ddDetails?.red_flags || [];
  const greenFlags = ddDetails?.green_flags || [];
  const pagesAnalyzed = ddDetails?.pages_analyzed || 0;

  if (!ddDetails || ddScore === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-text-muted">Website due diligence not available or website was not provided during upload.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Score Display */}
      <div className="flex flex-col items-center justify-center py-4">
        <div className="relative w-24 h-24">
          <svg className="w-24 h-24 transform -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="42" stroke="#27272a" strokeWidth="6" fill="none" />
            <circle
              cx="50" cy="50" r="42"
              stroke={ddScore >= 7 ? '#10b981' : ddScore >= 5 ? '#f59e0b' : '#ef4444'}
              strokeWidth="6"
              fill="none"
              strokeDasharray={`${(ddScore / 10) * 264} 264`}
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="font-mono text-2xl font-bold text-text-primary">{ddScore}</span>
          </div>
        </div>
        <p className="text-xs text-text-muted mt-2 text-center">{pagesAnalyzed} pages analyzed</p>
        <p className="text-[10px] text-text-muted mt-1">Confidence: {ddDetails?.confidence || 'N/A'}</p>
      </div>

      {/* Score Breakdown */}
      <div className="space-y-2">
        <h4 className="text-xs font-medium text-text-primary uppercase tracking-widest mb-3">Score Breakdown</h4>
        <ScoreBar label="Product Clarity" score={breakdown.product_clarity || 0} max={3} />
        <ScoreBar label="Pricing & GTM" score={breakdown.pricing_gtm_clarity || 0} max={2} />
        <ScoreBar label="Customer Proof" score={breakdown.customer_proof || 0} max={2} />
        <ScoreBar label="Tech Credibility" score={breakdown.technical_credibility || 0} max={2} />
        <ScoreBar label="Trust & Compliance" score={breakdown.trust_compliance || 0} max={1} />
      </div>

      {/* Flags */}
      <div className="space-y-4">
        {/* Green Flags */}
        <div>
          <h4 className="text-xs font-medium text-success uppercase tracking-widest mb-2 flex items-center gap-1">
            <CheckCircle size={12} /> Green Flags
          </h4>
          <div className="space-y-1.5">
            {greenFlags.length > 0 ? (
              greenFlags.slice(0, 4).map((flag, i) => (
                <div key={i} className="flex items-start gap-2 text-xs text-text-secondary">
                  <div className="w-1 h-1 rounded-full bg-success mt-1.5 shrink-0" />
                  <span className="line-clamp-2" title={flag}>{flag}</span>
                </div>
              ))
            ) : (
              <p className="text-xs text-text-muted">None detected</p>
            )}
          </div>
        </div>

        {/* Red Flags */}
        <div>
          <h4 className="text-xs font-medium text-destructive uppercase tracking-widest mb-2 flex items-center gap-1">
            <AlertTriangle size={12} /> Red Flags
          </h4>
          <div className="space-y-1.5">
            {redFlags.length > 0 ? (
              redFlags.slice(0, 4).map((flag, i) => (
                <div key={i} className="flex items-start gap-2 text-xs text-text-secondary">
                  <div className="w-1 h-1 rounded-full bg-destructive mt-1.5 shrink-0" />
                  <span className="line-clamp-2" title={flag}>{flag}</span>
                </div>
              ))
            ) : (
              <p className="text-xs text-text-muted">None detected</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ScoreBar({ label, score, max }) {
  const percentage = (score / max) * 100;
  const color = percentage >= 70 ? 'bg-success' : percentage >= 40 ? 'bg-warning' : 'bg-destructive';

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-text-muted uppercase tracking-widest">{label}</span>
        <span className="text-xs font-mono text-text-primary">{score}/{max}</span>
      </div>
      <div className="w-full h-1.5 bg-bg rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-500`} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}

// ============ SHARED COMPONENTS ============
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
  const displayVal = value && value !== 'not_mentioned' && value !== 'null' && value !== null ? value : 'N/A';
  return (
    <div className="bg-bg p-3 rounded-sm border border-border">
      <div className="text-[10px] text-text-muted uppercase tracking-widest">{label}</div>
      <div className="text-sm font-mono font-medium text-text-primary mt-1">{String(displayVal)}</div>
    </div>
  );
}

function MetricRow({ label, value }) {
  const displayVal = value && value !== 'null' && value !== null ? value : 'N/A';
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-xs text-text-muted">{label}</span>
      <span className="text-xs font-mono text-text-primary">{String(displayVal)}</span>
    </div>
  );
}

function SignalPill({ label, active }) {
  return (
    <div className={`flex items-center gap-1.5 px-2 py-1.5 rounded-sm text-xs border ${active ? 'bg-success/5 border-success/20 text-success' : 'bg-bg border-border text-text-muted'
      }`}>
      <div className={`w-1.5 h-1.5 rounded-full ${active ? 'bg-success' : 'bg-text-muted'}`} />
      {label}
    </div>
  );
}

function ScoreIndicator({ label, score, max }) {
  const numScore = Number(score) || 0;
  const pct = (numScore / max) * 100;
  const color = pct >= 70 ? 'bg-success' : pct >= 40 ? 'bg-warning' : 'bg-destructive';
  return (
    <div className="mt-2 pt-2 border-t border-border">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-text-muted uppercase tracking-widest">{label}</span>
        <span className="text-xs font-mono text-text-primary">{numScore}/{max}</span>
      </div>
      <div className="w-full h-1.5 bg-bg rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
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
