import { useState, useRef } from "react";
import type { FormEvent, MouseEvent } from "react";
import { 
  Eye, 
  EyeOff, 
  Shield, 
  Activity, 
  GitCommit, 
  FileText, 
  AlertCircle,
  User,
  Lock,
  ArrowRight,
  ShieldCheck,
  Check
} from "lucide-react";
import "./LoginView.css";

type LoginViewProps = {
  error?: string;
  onSubmit: (username: string, password: string) => Promise<void>;
};

export function LoginView({ error, onSubmit }: LoginViewProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const cardRef = useRef<HTMLDivElement>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!username || !password) return;
    setSubmitting(true);
    try {
      await onSubmit(username, password);
    } finally {
      setSubmitting(false);
    }
  };

  // Subtle pointer tracking for glass card hover effect
  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setMousePos({ x, y });
  };

  return (
    <main className="login-container">
      {/* Background Environment */}
      <div className="cyber-background">
        <div className="cyber-grid" />
        <div className="cyber-map" />
        {/* Animated decorative nodes */}
        <div className="cyber-node" style={{ top: "25%", left: "30%", animationDelay: "0s" }} />
        <div className="cyber-node" style={{ top: "65%", left: "15%", animationDelay: "1s" }} />
        <div className="cyber-node" style={{ top: "45%", left: "70%", animationDelay: "0.5s" }} />
        <div className="cyber-node" style={{ top: "80%", left: "55%", animationDelay: "1.5s" }} />
        <div className="cyber-node" style={{ top: "15%", left: "85%", animationDelay: "2s" }} />
        <div className="cyber-line" style={{ top: "25%", left: "30%", width: "150px", transform: "rotate(45deg)" }} />
        <div className="cyber-line" style={{ top: "65%", left: "15%", width: "200px", transform: "rotate(-20deg)" }} />
      </div>

      {/* Left Pane - Branding & Info */}
      <div className="login-left-pane">
        <div className="brand-header">
          <div className="brand-logo-container">
            <ShieldCheck size={28} color="var(--sat-cyan)" strokeWidth={2.5} />
          </div>
          <div className="brand-text-container">
            <h1>SAT-SA</h1>
            <p className="brand-subtitle">EVIDENCE | ANALYSIS | SUPERVISION</p>
          </div>
        </div>

        <div className="hero-section">
          <h2 className="hero-headline">
            <span className="headline-white">TURN SOC DATA</span>
            <span className="headline-blue">INTO ACTIONABLE</span>
            <span className="headline-blue">SUPERVISION</span>
          </h2>
          <p className="hero-description">
            Evidence-driven supervisory analytics for a more transparent, accountable and resilient cyber security ecosystem.
          </p>

          <div className="feature-cards-container">
            <div className="feature-card">
              <div className="feature-icon-wrapper">
                <Activity size={20} />
              </div>
              <span className="feature-title">Alert Analysis</span>
            </div>
            
            <div className="feature-card">
              <div className="feature-icon-wrapper">
                <Shield size={20} />
              </div>
              <span className="feature-title">Missing Evidence Detection</span>
            </div>
            
            <div className="feature-card">
              <div className="feature-icon-wrapper">
                <GitCommit size={20} />
              </div>
              <span className="feature-title">Contextual Correlation</span>
            </div>
            
            <div className="feature-card">
              <div className="feature-icon-wrapper">
                <FileText size={20} />
              </div>
              <span className="feature-title">Explainable Findings</span>
            </div>
          </div>
        </div>
      </div>

      {/* Right Pane - Login Form */}
      <div className="login-right-pane">
        <div className="login-panel-container">
          <div 
            ref={cardRef}
            className="login-glass-card"
            onMouseMove={handleMouseMove}
            style={{
              background: `radial-gradient(circle 400px at ${mousePos.x}px ${mousePos.y}px, rgba(0, 216, 246, 0.05), transparent 40%), var(--sat-panel)`
            }}
          >
            <div className="login-header">
              <div className="login-brand">
                <div className="login-brand-logo">
                  <ShieldCheck size={20} strokeWidth={2.5} />
                </div>
                <h2 className="login-brand-text">SAT-SA</h2>
              </div>
              <h3 className="login-welcome">Welcome Back</h3>
              <p className="login-subtext">Login to access your workspace</p>
            </div>

            <form className="login-form" onSubmit={submit}>
              <div className="input-group">
                <div className="input-wrapper">
                  <input
                    id="username"
                    type="text"
                    className="login-input"
                    placeholder="Username or Email"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="username"
                    required
                    disabled={submitting}
                  />
                  <User size={18} className="input-icon" />
                </div>
              </div>

              <div className="input-group">
                <div className="input-wrapper">
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    className="login-input"
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    required
                    disabled={submitting}
                  />
                  <Lock size={18} className="input-icon" />
                  <button 
                    type="button" 
                    className="password-toggle"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div className="form-options">
                <label className="remember-me">
                  <input type="checkbox" className="sr-only" style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }} />
                  <div className="checkbox-custom">
                    <Check size={12} color="#030611" style={{ opacity: 0 /* handle check via css */ }} />
                  </div>
                  Remember me
                </label>
                <a href="#" className="forgot-password" onClick={(e) => e.preventDefault()}>
                  Forgot password?
                </a>
              </div>

              {error && (
                <div className="error-message" role="alert">
                  <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
                  <span>{error}</span>
                </div>
              )}

              <button 
                type="submit" 
                className="login-btn"
                disabled={submitting || !username || !password}
              >
                {submitting ? (
                  <>
                    <span className="spin"><Activity size={18} /></span>
                    Authenticating...
                  </>
                ) : (
                  <>
                    Login <ArrowRight size={18} />
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      </div>
    </main>
  );
}
