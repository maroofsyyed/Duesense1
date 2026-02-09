import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getCompanies, deleteCompany } from '../api';
import { Building2, Trash2, ExternalLink, CheckCircle, AlertCircle, Loader2, Search } from 'lucide-react';

const STATUS_MAP = {
  processing: { color: 'text-warning', icon: Loader2, label: 'Processing' },
  extracting: { color: 'text-warning', icon: Loader2, label: 'Extracting' },
  enriching: { color: 'text-secondary', icon: Loader2, label: 'Enriching' },
  scoring: { color: 'text-accent', icon: Loader2, label: 'Scoring' },
  generating_memo: { color: 'text-primary', icon: Loader2, label: 'Memo Gen' },
  completed: { color: 'text-success', icon: CheckCircle, label: 'Completed' },
  failed: { color: 'text-destructive', icon: AlertCircle, label: 'Failed' },
};

export default function Companies() {
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    loadCompanies();
    const interval = setInterval(loadCompanies, 8000);
    return () => clearInterval(interval);
  }, []);

  const loadCompanies = async () => {
    try {
      const res = await getCompanies();
      setCompanies(res.data.companies || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete ${name}?`)) return;
    try {
      await deleteCompany(id);
      setCompanies(prev => prev.filter(c => c.id !== id));
    } catch (e) {
      console.error(e);
    }
  };

  const filtered = companies.filter(c =>
    c.name?.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full" data-testid="companies-loading">
        <Loader2 size={32} className="animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-[1600px] mx-auto" data-testid="companies-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-heading font-black text-3xl text-text-primary tracking-tight">Companies</h1>
          <p className="text-text-secondary text-sm mt-1">{companies.length} companies analyzed</p>
        </div>
        <Link
          to="/upload"
          className="px-4 py-2 bg-primary text-white rounded-sm text-sm font-medium hover:bg-primary-hover transition-colors"
          data-testid="add-company-btn"
        >
          + Upload Deck
        </Link>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
        <input
          type="text"
          placeholder="Search companies..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          data-testid="search-input"
          className="w-full bg-bg border border-border rounded-sm pl-10 pr-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-colors"
        />
      </div>

      {/* Companies List */}
      {filtered.length > 0 ? (
        <div className="space-y-3">
          {filtered.map((c, i) => {
            const status = STATUS_MAP[c.status] || STATUS_MAP.processing;
            const StatusIcon = status.icon;
            return (
              <div
                key={c.id}
                className="bg-surface border border-border rounded-sm p-4 hover:border-primary/20 transition-all duration-200 animate-fade-in"
                style={{ animationDelay: `${i * 50}ms` }}
                data-testid={`company-card-${i}`}
              >
                <div className="flex items-center justify-between">
                  <Link to={`/companies/${c.id}`} className="flex items-center gap-4 flex-1">
                    <div className="w-10 h-10 rounded-sm bg-primary/10 flex items-center justify-center shrink-0">
                      <Building2 size={20} className="text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-medium text-text-primary truncate">{c.name}</h3>
                        <span className={`flex items-center gap-1 text-[10px] font-mono uppercase ${status.color}`}>
                          <StatusIcon size={12} className={c.status !== 'completed' && c.status !== 'failed' ? 'animate-spin' : ''} />
                          {status.label}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-text-muted mt-1">
                        {c.stage && <span>{c.stage}</span>}
                        {c.hq_location && <span>{c.hq_location}</span>}
                        {c.website && (
                          <a href={c.website} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-secondary hover:underline" onClick={e => e.stopPropagation()}>
                            <ExternalLink size={10} /> Website
                          </a>
                        )}
                      </div>
                    </div>
                  </Link>

                  <div className="flex items-center gap-4">
                    {c.score && (
                      <div className="text-right">
                        <div className="font-mono text-xl font-bold text-text-primary">{c.score.total_score}</div>
                        <div className={`text-[10px] font-mono uppercase ${
                          c.score.tier === 'TIER_1' ? 'text-success' :
                          c.score.tier === 'TIER_2' ? 'text-primary' :
                          c.score.tier === 'TIER_3' ? 'text-warning' : 'text-destructive'
                        }`}>{c.score.tier?.replace('_', ' ')}</div>
                      </div>
                    )}
                    <button
                      onClick={() => handleDelete(c.id, c.name)}
                      data-testid={`delete-company-${i}`}
                      className="p-2 text-text-muted hover:text-destructive hover:bg-destructive/10 rounded-sm transition-colors"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-20">
          <Building2 size={48} className="mx-auto text-text-muted mb-4" />
          <p className="text-text-secondary">No companies found</p>
        </div>
      )}
    </div>
  );
}
