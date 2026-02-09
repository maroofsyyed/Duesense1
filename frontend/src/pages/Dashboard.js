import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getDashboardStats } from '../api';
import { Building2, AlertCircle, CheckCircle, Clock, ArrowRight, Zap } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';

const TIER_COLORS = { tier_1: '#10b981', tier_2: '#6366f1', tier_3: '#f59e0b', pass: '#ef4444' };
const TIER_LABELS = { tier_1: 'Tier 1', tier_2: 'Tier 2', tier_3: 'Tier 3', pass: 'Pass' };

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
    const interval = setInterval(loadStats, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadStats = async () => {
    try {
      const res = await getDashboardStats();
      setStats(res.data);
    } catch (e) {
      console.error('Failed to load stats', e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full" data-testid="dashboard-loading">
        <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  const tierData = stats?.tiers
    ? Object.entries(stats.tiers).filter(([, v]) => v > 0).map(([k, v]) => ({ name: TIER_LABELS[k], value: v, color: TIER_COLORS[k] }))
    : [];

  const scoreData = (stats?.recent_companies || [])
    .filter(c => c.score?.total_score)
    .map(c => ({ name: c.name?.substring(0, 12), score: c.score.total_score }));

  return (
    <div className="p-6 lg:p-8 max-w-[1600px] mx-auto" data-testid="dashboard">
      <div className="mb-8">
        <h1 className="font-heading font-black text-3xl text-text-primary tracking-tight">Deal Pipeline</h1>
        <p className="text-text-secondary text-sm mt-1">AI-powered venture capital intelligence at a glance</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard icon={Building2} label="Total Companies" value={stats?.total_companies || 0} color="text-primary" testId="stat-total" />
        <StatCard icon={Clock} label="Processing" value={stats?.processing || 0} color="text-warning" testId="stat-processing" />
        <StatCard icon={CheckCircle} label="Completed" value={stats?.completed || 0} color="text-success" testId="stat-completed" />
        <StatCard icon={AlertCircle} label="Failed" value={stats?.failed || 0} color="text-destructive" testId="stat-failed" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Tier Distribution */}
        <div className="bg-surface border border-border rounded-sm p-6" data-testid="tier-distribution">
          <h3 className="font-heading font-bold text-lg text-text-primary mb-4">Tier Distribution</h3>
          {tierData.length > 0 ? (
            <div className="flex items-center gap-6">
              <ResponsiveContainer width={140} height={140}>
                <PieChart>
                  <Pie data={tierData} cx="50%" cy="50%" innerRadius={40} outerRadius={60} dataKey="value" strokeWidth={0}>
                    {tierData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2">
                {tierData.map((t, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: t.color }} />
                    <span className="text-text-secondary">{t.name}</span>
                    <span className="font-mono text-text-primary font-medium">{t.value}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-text-muted text-sm">No scored companies yet. Upload a pitch deck to get started.</p>
          )}
        </div>

        {/* Score Chart */}
        <div className="bg-surface border border-border rounded-sm p-6 lg:col-span-2" data-testid="score-chart">
          <h3 className="font-heading font-bold text-lg text-text-primary mb-4">Recent Scores</h3>
          {scoreData.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={scoreData}>
                <XAxis dataKey="name" tick={{ fill: '#a1a1aa', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: '#a1a1aa', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '2px', color: '#fafafa' }} />
                <Bar dataKey="score" fill="#6366f1" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-text-muted text-sm">No scores available yet.</p>
          )}
        </div>
      </div>

      {/* Recent Companies */}
      <div className="bg-surface border border-border rounded-sm p-6" data-testid="recent-companies">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-heading font-bold text-lg text-text-primary">Recent Analyses</h3>
          <Link to="/companies" className="text-primary text-sm flex items-center gap-1 hover:underline" data-testid="view-all-link">
            View All <ArrowRight size={14} />
          </Link>
        </div>
        {(stats?.recent_companies || []).length > 0 ? (
          <div className="space-y-3">
            {stats.recent_companies.map((c, i) => (
              <Link
                key={c.id}
                to={`/companies/${c.id}`}
                className="flex items-center justify-between p-3 rounded-sm border border-border hover:border-primary/30 hover:bg-surface-hl transition-all duration-200 animate-fade-in"
                style={{ animationDelay: `${i * 80}ms` }}
                data-testid={`recent-company-${i}`}
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-sm bg-primary/10 flex items-center justify-center">
                    <Building2 size={16} className="text-primary" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-text-primary">{c.name}</div>
                    <div className="text-xs text-text-muted">{c.stage || 'N/A'} &middot; {c.hq_location || 'N/A'}</div>
                  </div>
                </div>
                {c.score && (
                  <div className="flex items-center gap-3">
                    <TierBadge tier={c.score.tier} />
                    <span className="font-mono text-lg font-bold text-text-primary">{c.score.total_score}</span>
                  </div>
                )}
              </Link>
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <Zap size={40} className="mx-auto text-text-muted mb-3" />
            <p className="text-text-secondary text-sm">No analyses yet</p>
            <Link to="/upload" className="mt-3 inline-flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-sm text-sm hover:bg-primary-hover transition-colors" data-testid="cta-upload">
              <Upload size={16} /> Upload First Deck
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color, testId }) {
  return (
    <div className="bg-surface border border-border rounded-sm p-5 hover:border-primary/20 transition-colors" data-testid={testId}>
      <div className="flex items-center justify-between mb-3">
        <Icon size={20} className={color} />
      </div>
      <div className="font-mono text-2xl font-bold text-text-primary">{value}</div>
      <div className="text-xs text-text-muted uppercase tracking-widest mt-1">{label}</div>
    </div>
  );
}

function TierBadge({ tier }) {
  const styles = {
    TIER_1: 'bg-success/10 text-success border-success/20',
    TIER_2: 'bg-primary/10 text-primary border-primary/20',
    TIER_3: 'bg-warning/10 text-warning border-warning/20',
    PASS: 'bg-destructive/10 text-destructive border-destructive/20',
  };
  return (
    <span className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider border rounded-sm ${styles[tier] || styles.PASS}`}>
      {tier?.replace('_', ' ')}
    </span>
  );
}

function Upload({ size }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}
