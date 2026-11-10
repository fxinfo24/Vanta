// Main App Component for Vanta
import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, Link } from 'react-router-dom';
import Layout from '@/components/Layout';

// The heavy views pull in the charting library, which is most of the bundle.
// They are loaded per route so signing in no longer downloads them upfront;
// Layout is static, so the shell (nav, header) still paints immediately.
const Dashboard = React.lazy(() => import('@/components/Dashboard'));
const TasksList = React.lazy(() => import('@/components/TasksList'));
const TaskView = React.lazy(() => import('@/components/TaskView'));
const ResultView = React.lazy(() => import('@/components/ResultView'));
import { apiService } from '@/services/api';

const TOKEN_KEY = 'vanta_token';

// ---------------------------------------------------------------------------
// Login / Register view (rendered when no token is present)
// ---------------------------------------------------------------------------

const LoginView: React.FC<{ onSuccess: () => void }> = ({ onSuccess }) => {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const res =
        mode === 'login'
          ? await apiService.login(email, password)
          : await apiService.register(email, password, username || undefined);
      if (res.success && res.data?.token) {
        localStorage.setItem(TOKEN_KEY, res.data.token);
        onSuccess();
        navigate('/dashboard', { replace: true });
      } else {
        setError(res.error || 'Authentication failed');
      }
    } catch {
      setError('Network error — is the backend reachable?');
    } finally {
      setBusy(false);
    }
  };

  const inputCls =
    'w-full rounded-xl bg-black/30 border border-white/10 px-4 py-2.5 text-sm text-white placeholder-white/40 outline-none focus:border-primary-500/60 focus:ring-1 focus:ring-primary-500/40';

  return (
    <div className="min-h-screen flex items-center justify-center px-4 font-sans text-white relative overflow-hidden">
      <div className="fixed top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary-500/20 rounded-full blur-[120px] animate-pulse-slow" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-secondary-500/20 rounded-full blur-[120px] animate-pulse-slow" style={{ animationDelay: '1.5s' }} />
      </div>
      <div className="glass-panel rounded-2xl p-8 w-full max-w-md">
        <div className="flex items-center justify-center mb-6">
          <img src="/logo.png" alt="Vanta" className="h-14 w-14 rounded-full object-cover border border-white/10 shadow-lg" />
        </div>
        <h1 className="text-2xl font-bold text-center font-display tracking-tight">Vanta</h1>
        <p className="text-sm text-white/60 text-center mt-1 mb-6">
          {mode === 'login' ? 'Sign in to your account' : 'Create your account'}
        </p>

        {error && (
          <div className="mb-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-200 text-sm px-4 py-2.5">
            {error}
          </div>
        )}

        <form onSubmit={submit} className="space-y-4">
          <input
            type="email"
            required
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputCls}
            autoComplete="email"
          />
          {mode === 'register' && (
            <input
              type="text"
              placeholder="Username (optional)"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={inputCls}
              autoComplete="username"
            />
          )}
          <input
            type="password"
            required
            placeholder={mode === 'register' ? 'Password (min 8 characters)' : 'Password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputCls}
            autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
          />
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-gradient-to-r from-primary-500 to-secondary-500 py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        {mode === 'login' && (
          <p className="text-center text-sm mt-3">
            <button
              type="button"
              onClick={() => navigate('/forgot-password')}
              className="text-white/50 hover:text-white/80"
            >
              Forgot your password?
            </button>
          </p>
        )}

        <p className="text-center text-sm text-white/60 mt-5">
          {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
          <button
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}
            className="text-primary-300 hover:text-primary-200 font-medium"
          >
            {mode === 'login' ? 'Sign up' : 'Sign in'}
          </button>
        </p>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Password reset: request a link, then redeem the token from that link.
// Both screens are public and reuse the login shell.
// ---------------------------------------------------------------------------

const authCardCls = 'glass-panel rounded-2xl p-8 w-full max-w-md';
const authInputCls =
  'w-full rounded-xl bg-black/30 border border-white/10 px-4 py-2.5 text-sm text-white placeholder-white/40 outline-none focus:border-primary-500/60 focus:ring-1 focus:ring-primary-500/40';
const authButtonCls =
  'w-full rounded-xl bg-gradient-to-r from-primary-500 to-secondary-500 py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 transition-opacity';

const AuthShell: React.FC<{ title: string; subtitle: string; children: React.ReactNode }> = ({ title, subtitle, children }) => (
  <div className="min-h-screen flex items-center justify-center px-4 font-sans text-white relative overflow-hidden">
    <div className="fixed top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary-500/20 rounded-full blur-[120px] animate-pulse-slow" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-secondary-500/20 rounded-full blur-[120px] animate-pulse-slow" style={{ animationDelay: '1.5s' }} />
    </div>
    <div className={authCardCls}>
      <div className="flex items-center justify-center mb-6">
        <img src="/logo.png" alt="Vanta" className="h-14 w-14 rounded-full object-cover border border-white/10 shadow-lg" />
      </div>
      <h1 className="text-2xl font-bold text-center font-display tracking-tight">{title}</h1>
      <p className="text-sm text-white/60 text-center mt-1 mb-6">{subtitle}</p>
      {children}
    </div>
  </div>
);

const ForgotPasswordView: React.FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setBusy(true);
    try {
      const res = await apiService.forgotPassword(email);
      if (res.success) {
        setMessage(res.data?.message || 'If that address has an account, a reset link has been sent.');
      } else {
        setError(res.error || 'Could not request a reset link');
      }
    } catch {
      setError('Network error — is the backend reachable?');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Reset your password" subtitle="We'll email you a one-time link">
      {error && (
        <div className="mb-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-200 text-sm px-4 py-2.5">
          {error}
        </div>
      )}
      {message && (
        <div className="mb-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-200 text-sm px-4 py-2.5">
          {message}
        </div>
      )}
      <form onSubmit={submit} className="space-y-4">
        <input
          type="email"
          required
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={authInputCls}
          autoComplete="email"
        />
        <button type="submit" disabled={busy} className={authButtonCls}>
          {busy ? 'Sending…' : 'Send reset link'}
        </button>
      </form>
      <p className="text-center text-sm text-white/60 mt-5">
        <button onClick={() => navigate('/login')} className="text-primary-300 hover:text-primary-200 font-medium">
          Back to sign in
        </button>
      </p>
    </AuthShell>
  );
};

const ResetPasswordView: React.FC = () => {
  const navigate = useNavigate();
  const token = new URLSearchParams(window.location.search).get('token') || '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');
    if (password !== confirm) {
      setError('The two passwords do not match');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    setBusy(true);
    try {
      const res = await apiService.resetPassword(token, password);
      if (res.success) {
        setMessage(res.data?.message || 'Password updated. You can sign in now.');
        setTimeout(() => navigate('/login'), 1500);
      } else {
        setError(res.error || 'This reset link is invalid or has expired');
      }
    } catch {
      setError('Network error — is the backend reachable?');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Choose a new password" subtitle="This link can only be used once">
      {!token && (
        <div className="mb-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 text-sm px-4 py-2.5">
          This link is missing its token. Request a new reset email.
        </div>
      )}
      {error && (
        <div className="mb-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-200 text-sm px-4 py-2.5">
          {error}
        </div>
      )}
      {message && (
        <div className="mb-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-200 text-sm px-4 py-2.5">
          {message}
        </div>
      )}
      <form onSubmit={submit} className="space-y-4">
        <input
          type="password"
          required
          placeholder="New password (min 8 characters)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={authInputCls}
          autoComplete="new-password"
        />
        <input
          type="password"
          required
          placeholder="Confirm new password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          className={authInputCls}
          autoComplete="new-password"
        />
        <button type="submit" disabled={busy || !token} className={authButtonCls}>
          {busy ? 'Updating…' : 'Set new password'}
        </button>
      </form>
      <p className="text-center text-sm text-white/60 mt-5">
        <button onClick={() => navigate('/forgot-password')} className="text-primary-300 hover:text-primary-200 font-medium">
          Request a new link
        </button>
      </p>
    </AuthShell>
  );
};

// ---------------------------------------------------------------------------
// Settings view (profile, preferences, security, BYOK)
// ---------------------------------------------------------------------------

interface ByokStatus {
  label: string;
  configured: boolean;
  source: 'user' | 'server' | 'none';
  hint: string;
}

const sourceText = (s: ByokStatus) =>
  s.source === 'user' ? `Your key ${s.hint}` : s.source === 'server' ? 'Using server key' : 'Not set';

const SettingsView: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  const [profile, setProfile] = useState({ email: '', username: '', first_name: '', last_name: '' });
  const [prefs, setPrefs] = useState({ default_mode: 'deep', preferred_model: '' });
  const [models, setModels] = useState<{ label: string; id: string }[]>([]);
  const [byok, setByok] = useState<Record<string, ByokStatus>>({});
  const [byokInputs, setByokInputs] = useState<Record<string, string>>({});

  const [pw, setPw] = useState({ current: '', next: '', confirm: '' });
  const [pwMsg, setPwMsg] = useState('');
  const [pwErr, setPwErr] = useState('');

  const load = async () => {
    const res = await apiService.getSettings();
    if (!res.success) {
      setErr(res.error || 'Failed to load settings');
      setLoading(false);
      return;
    }
    const d = res.data;
    setProfile({
      email: d.profile?.email || '',
      username: d.profile?.username || '',
      first_name: d.profile?.first_name || '',
      last_name: d.profile?.last_name || '',
    });
    setPrefs({
      default_mode: d.preferences?.default_mode || 'deep',
      preferred_model: d.preferences?.preferred_model || '',
    });
    setModels(d.available_models || []);
    setByok(d.byok || {});
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    setMsg('');
    setErr('');
    const byokPayload: Record<string, string> = {};
    for (const [provider, value] of Object.entries(byokInputs)) {
      if (value !== '') byokPayload[provider] = value;
    }
    const res = await apiService.saveSettings({
      first_name: profile.first_name || null,
      last_name: profile.last_name || null,
      username: profile.username || null,
      default_mode: prefs.default_mode,
      preferred_model: prefs.preferred_model || null,
      ...(Object.keys(byokPayload).length ? { byok: byokPayload } : {}),
    });
    setSaving(false);
    if (!res.success) {
      setErr(res.error || 'Save failed');
      return;
    }
    const d = res.data;
    setByok(d.byok || {});
    setByokInputs({});
    setMsg('Settings saved.');
  };

  const clearKey = async (provider: string) => {
    setErr('');
    setMsg('');
    const res = await apiService.saveSettings({ byok: { [provider]: '' } });
    if (!res.success) {
      setErr(res.error || 'Failed to remove key');
      return;
    }
    setByok(res.data.byok || {});
    setMsg('Key removed.');
  };

  const changePassword = async () => {
    setPwMsg('');
    setPwErr('');
    if (pw.next !== pw.confirm) {
      setPwErr('New passwords do not match');
      return;
    }
    const res = await apiService.changePassword(pw.current, pw.next);
    if (!res.success) {
      setPwErr(res.error || 'Password change failed');
      return;
    }
    setPw({ current: '', next: '', confirm: '' });
    setPwMsg('Password updated.');
  };

  if (loading) return <div className="text-white/60">Loading settings…</div>;

  const inputCls =
    'w-full rounded-xl bg-black/30 border border-white/10 px-4 py-2.5 text-sm text-white placeholder-white/40 outline-none focus:border-primary-500/60 focus:ring-1 focus:ring-primary-500/40';
  const labelCls = 'block text-xs font-medium text-white/60 mb-1.5 uppercase tracking-wide';
  const sectionCls = 'glass-panel rounded-2xl p-6 space-y-4';
  const h2Cls = 'text-lg font-semibold text-white';

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold font-display tracking-tight">Settings</h1>
        <Link to="/dashboard" className="text-sm text-primary-300 hover:text-primary-200">Back to Dashboard</Link>
      </div>

      {err && <div className="rounded-xl bg-red-500/10 border border-red-500/30 text-red-200 text-sm px-4 py-2.5">{err}</div>}
      {msg && <div className="rounded-xl bg-green-500/10 border border-green-500/30 text-green-200 text-sm px-4 py-2.5">{msg}</div>}

      {/* Profile */}
      <section className={sectionCls}>
        <h2 className={h2Cls}>Profile</h2>
        <div>
          <label className={labelCls}>Email</label>
          <input type="email" value={profile.email} disabled className={`${inputCls} opacity-50`} />
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>First name</label>
            <input value={profile.first_name} onChange={(e) => setProfile({ ...profile, first_name: e.target.value })} className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Last name</label>
            <input value={profile.last_name} onChange={(e) => setProfile({ ...profile, last_name: e.target.value })} className={inputCls} />
          </div>
        </div>
        <div>
          <label className={labelCls}>Username</label>
          <input value={profile.username} onChange={(e) => setProfile({ ...profile, username: e.target.value })} className={inputCls} />
        </div>
      </section>

      {/* Preferences */}
      <section className={sectionCls}>
        <h2 className={h2Cls}>Preferences</h2>
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Default analysis mode</label>
            <select
              value={prefs.default_mode}
              onChange={(e) => setPrefs({ ...prefs, default_mode: e.target.value })}
              className={inputCls}
            >
              <option value="quick">Quick scan</option>
              <option value="deep">Deep dossier</option>
            </select>
          </div>
          <div>
            <label className={labelCls}>Preferred LLM model</label>
            <select
              value={prefs.preferred_model}
              onChange={(e) => setPrefs({ ...prefs, preferred_model: e.target.value })}
              className={inputCls}
            >
              <option value="">Server default</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>{m.label} — {m.id}</option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {/* BYOK */}
      <section className={sectionCls}>
        <h2 className={h2Cls}>API Keys (BYOK)</h2>
        <p className="text-sm text-white/50 -mt-2">
          Use your own API keys for your analyses. Keys are stored encrypted and are never shown again —
          only a masked hint. Leave a field blank to keep the current key. When no key of yours is set,
          the server key is used.
        </p>
        <div className="space-y-4">
          {Object.entries(byok).map(([provider, status]) => (
            <div key={provider} className="flex flex-col sm:flex-row sm:items-center gap-2">
              <div className="sm:w-56 shrink-0">
                <div className="text-sm text-white/85">{status.label}</div>
                <div className={`text-xs ${status.source === 'user' ? 'text-green-300' : status.source === 'server' ? 'text-primary-200' : 'text-amber-300'}`}>
                  {sourceText(status)}
                </div>
              </div>
              <input
                type="password"
                placeholder={status.source === 'user' ? 'Enter a new key to replace' : 'Enter your API key'}
                value={byokInputs[provider] || ''}
                onChange={(e) => setByokInputs({ ...byokInputs, [provider]: e.target.value })}
                className={inputCls}
                autoComplete="off"
              />
              {status.source === 'user' && (
                <button
                  onClick={() => clearKey(provider)}
                  className="shrink-0 rounded-xl border border-red-500/30 text-red-300 px-3 py-2 text-xs hover:bg-red-500/10 transition-colors"
                >
                  Remove
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      <button
        onClick={save}
        disabled={saving}
        className="w-full rounded-xl bg-gradient-to-r from-primary-500 to-secondary-500 py-3 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
      >
        {saving ? 'Saving…' : 'Save settings'}
      </button>

      {/* Security */}
      <section className={sectionCls}>
        <h2 className={h2Cls}>Change password</h2>
        {pwErr && <div className="rounded-xl bg-red-500/10 border border-red-500/30 text-red-200 text-sm px-4 py-2.5">{pwErr}</div>}
        {pwMsg && <div className="rounded-xl bg-green-500/10 border border-green-500/30 text-green-200 text-sm px-4 py-2.5">{pwMsg}</div>}
        <div>
          <label className={labelCls}>Current password</label>
          <input type="password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} className={inputCls} autoComplete="current-password" />
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>New password</label>
            <input type="password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} className={inputCls} autoComplete="new-password" />
          </div>
          <div>
            <label className={labelCls}>Confirm new password</label>
            <input type="password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} className={inputCls} autoComplete="new-password" />
          </div>
        </div>
        <button
          onClick={changePassword}
          className="rounded-xl border border-white/15 px-5 py-2.5 text-sm font-semibold text-white hover:bg-white/10 transition-colors"
        >
          Update password
        </button>
      </section>
    </div>
  );
};

// ---------------------------------------------------------------------------

const App: React.FC = () => {
  const [authed, setAuthed] = useState<boolean>(() => !!localStorage.getItem(TOKEN_KEY));

  // The token can be dropped after mount: it expired, or the server rejected
  // it. Without this, the gate stayed open and an expired session rendered the
  // authenticated shell around "Error Loading Task" instead of the sign-in
  // screen — a dead end that looked like a broken app rather than a logout.
  useEffect(() => {
    const onExpired = () => setAuthed(false);
    window.addEventListener('vanta:auth-expired', onExpired);
    return () => window.removeEventListener('vanta:auth-expired', onExpired);
  }, []);

  return (
    <Router>
      <div className="App">
        <Routes>
          <Route
            path="/login"
            element={authed ? <Navigate to="/dashboard" replace /> : <LoginView onSuccess={() => setAuthed(true)} />}
          />
          {/* Public: reachable while signed out, and while signed in (a user
              may be resetting after a locked-out session). */}
          <Route path="/forgot-password" element={<ForgotPasswordView />} />
          <Route path="/reset-password" element={<ResetPasswordView />} />
          <Route path="/" element={authed ? <Layout /> : <Navigate to="/login" replace />}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="tasks" element={<TasksList />} />
            <Route path="tasks/:id" element={<TaskView />} />
            <Route path="tasks/:id/results" element={<ResultView />} />
            <Route path="settings" element={<SettingsView />} />
            <Route path="*" element={<Navigate to="dashboard" replace />} />
          </Route>
        </Routes>
      </div>
    </Router>
  );
};

export default App;
