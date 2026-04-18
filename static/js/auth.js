/**
 * Fridge Observer — Auth Page
 * auth.js: Login, signup, and OTP verification
 */

// ── State ─────────────────────────────────────────────────────
let _pendingEmail = '';
let _pendingPassword = '';  // stored temporarily to auto-login after OTP
let _resendTimer = null;

// ── Tab switching ─────────────────────────────────────────────

const tabLogin  = document.getElementById('tab-login');
const tabSignup = document.getElementById('tab-signup');
const panelLogin  = document.getElementById('panel-login');
const panelSignup = document.getElementById('panel-signup');
const panelVerify = document.getElementById('panel-verify');

function showTab(tab) {
  const isLogin  = tab === 'login';
  const isSignup = tab === 'signup';
  const isVerify = tab === 'verify';

  tabLogin.classList.toggle('active', isLogin);
  tabSignup.classList.toggle('active', isSignup);
  tabLogin.setAttribute('aria-selected', String(isLogin));
  tabSignup.setAttribute('aria-selected', String(isSignup));

  document.querySelector('.auth-tabs').style.display = isVerify ? 'none' : '';

  panelLogin.classList.toggle('active', isLogin);
  panelSignup.classList.toggle('active', isSignup);

  if (panelVerify) {
    panelVerify.style.display = isVerify ? 'block' : 'none';
    panelVerify.classList.toggle('active', isVerify);
  }

  clearErrors();
}

tabLogin.addEventListener('click',  () => showTab('login'));
tabSignup.addEventListener('click', () => showTab('signup'));
document.getElementById('go-signup').addEventListener('click', () => showTab('signup'));
document.getElementById('go-login').addEventListener('click',  () => showTab('login'));
document.getElementById('back-to-signup').addEventListener('click', () => showTab('signup'));

if (location.hash === '#signup') showTab('signup');

// ── Password visibility toggle ────────────────────────────────

document.querySelectorAll('.auth-toggle-pw').forEach(btn => {
  btn.addEventListener('click', () => {
    const input = document.getElementById(btn.dataset.target);
    if (!input) return;
    const isText = input.type === 'text';
    input.type = isText ? 'password' : 'text';
    btn.textContent = isText ? '👁' : '🙈';
  });
});

// ── Password strength meter ───────────────────────────────────

const pwInput    = document.getElementById('signup-password');
const pwStrength = document.getElementById('pw-strength');

function getStrength(pw) {
  let score = 0;
  if (pw.length >= 8)  score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (/\d/.test(pw))   score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  return Math.min(score, 4);
}

const STRENGTH_LABELS  = ['', 'Weak', 'Fair', 'Good', 'Strong'];
const STRENGTH_CLASSES = ['', 'filled-weak', 'filled-fair', 'filled-good', 'filled-strong'];

pwInput.addEventListener('input', () => {
  const pw = pwInput.value;
  if (!pw) { pwStrength.innerHTML = ''; return; }
  const score = getStrength(pw);
  const bars = [1,2,3,4].map(i => {
    const cls = i <= score ? STRENGTH_CLASSES[score] : '';
    return `<div class="pw-bar ${cls}"></div>`;
  }).join('');
  pwStrength.innerHTML = `<div class="pw-bars">${bars}</div><span class="pw-label">${STRENGTH_LABELS[score]}</span>`;
});

// ── OTP input — digits only ───────────────────────────────────

const otpInput = document.getElementById('otp-input');
otpInput.addEventListener('input', () => {
  otpInput.value = otpInput.value.replace(/\D/g, '').slice(0, 6);
});

// ── Error helpers ─────────────────────────────────────────────

function setFieldError(fieldId, msg) {
  const el = document.getElementById(fieldId);
  if (el) el.textContent = msg;
  const inputId = fieldId.replace('-error', '');
  const input = document.getElementById(inputId);
  if (input) input.classList.toggle('error', !!msg);
}

function setBannerError(bannerId, msg) {
  const el = document.getElementById(bannerId);
  if (!el) return;
  el.textContent = msg;
  el.classList.toggle('visible', !!msg);
}

function clearErrors() {
  document.querySelectorAll('.auth-field-error').forEach(el => el.textContent = '');
  document.querySelectorAll('.auth-input').forEach(el => el.classList.remove('error'));
  document.querySelectorAll('.auth-error-banner').forEach(el => {
    el.textContent = '';
    el.classList.remove('visible');
  });
}

// ── Loading state ─────────────────────────────────────────────

function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.disabled = loading;
  btn.classList.toggle('loading', loading);
}

// ── API helper ────────────────────────────────────────────────

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include',
  });
  let data = {};
  try { data = await res.json(); } catch {}
  return { ok: res.ok, status: res.status, data };
}

// ── Resend countdown ──────────────────────────────────────────

function startResendCountdown(seconds = 60) {
  const btn = document.getElementById('resend-otp-btn');
  const countdown = document.getElementById('resend-countdown');
  if (!btn || !countdown) return;

  btn.style.display = 'none';
  countdown.style.display = 'inline';
  let remaining = seconds;
  countdown.textContent = `Resend in ${remaining}s`;

  if (_resendTimer) clearInterval(_resendTimer);
  _resendTimer = setInterval(() => {
    remaining--;
    if (remaining <= 0) {
      clearInterval(_resendTimer);
      btn.style.display = 'inline';
      countdown.style.display = 'none';
    } else {
      countdown.textContent = `Resend in ${remaining}s`;
    }
  }, 1000);
}

// ── Show OTP screen ───────────────────────────────────────────

function showVerifyScreen(email) {
  _pendingEmail = email;
  document.getElementById('verify-email-display').textContent = email;
  document.getElementById('otp-input').value = '';
  showTab('verify');
  startResendCountdown(60);
  setTimeout(() => document.getElementById('otp-input').focus(), 100);
}

// ── Signup form ───────────────────────────────────────────────

document.getElementById('signup-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  clearErrors();

  const name     = document.getElementById('signup-name').value.trim();
  const email    = document.getElementById('signup-email').value.trim();
  const password = document.getElementById('signup-password').value;
  const confirm  = document.getElementById('signup-confirm').value;

  let valid = true;
  if (!name)  { setFieldError('signup-name-error', 'Name is required'); valid = false; }
  if (!email) { setFieldError('signup-email-error', 'Email is required'); valid = false; }
  else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    setFieldError('signup-email-error', 'Enter a valid email address'); valid = false;
  }
  if (!password) { setFieldError('signup-password-error', 'Password is required'); valid = false; }
  else if (password.length < 8) {
    setFieldError('signup-password-error', 'Password must be at least 8 characters'); valid = false;
  }
  if (password !== confirm) {
    setFieldError('signup-confirm-error', 'Passwords do not match'); valid = false;
  }
  if (!valid) return;

  setLoading('signup-submit', true);
  const { ok, status, data } = await apiPost('/auth/signup', {
    email, display_name: name, password,
  });
  setLoading('signup-submit', false);

  if (ok) {
    _pendingPassword = password; // store for auto-login after OTP
    showVerifyScreen(email);
  } else {
    const msg = data.detail || 'Something went wrong. Please try again.';
    if (status === 409) {
      setFieldError('signup-email-error', 'An account with this email already exists');
    } else {
      setBannerError('signup-error', msg);
    }
  }
});

// ── OTP verification form ─────────────────────────────────────

document.getElementById('verify-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  clearErrors();

  const code = document.getElementById('otp-input').value.trim();
  if (!code || code.length !== 6) {
    setFieldError('otp-error', 'Enter the 6-digit code from your email');
    return;
  }

  setLoading('verify-submit', true);

  // Step 1: Verify the OTP
  const { ok, status, data } = await apiPost('/auth/verify-otp-and-login', {
    email: _pendingEmail,
    code,
  });

  if (!ok) {
    setLoading('verify-submit', false);
    const msg = data.detail || 'Invalid code. Please try again.';
    if (status === 409) {
      setBannerError('verify-error', 'This email is already verified. Redirecting to sign in...');
      setTimeout(() => showTab('login'), 2000);
    } else {
      setBannerError('verify-error', msg);
    }
    return;
  }

  // Step 2: Auto-login with stored password
  if (_pendingPassword) {
    const loginResult = await apiPost('/auth/login', {
      email: _pendingEmail,
      password: _pendingPassword,
      remember_me: false,
    });

    setLoading('verify-submit', false);

    if (loginResult.ok) {
      // Show success and redirect to app
      if (panelVerify) {
        panelVerify.innerHTML = `
          <div class="auth-success">
            <div class="auth-success-icon">🎉</div>
            <h3>Email verified!</h3>
            <p>Welcome, ${escapeHtml(data.display_name || '')}! Taking you to your fridge...</p>
          </div>
        `;
      }
      _pendingPassword = '';
      setTimeout(() => { window.location.href = '/'; }, 1500);
    } else {
      // Login failed — redirect to login page with email pre-filled
      if (panelVerify) {
        panelVerify.innerHTML = `
          <div class="auth-success">
            <div class="auth-success-icon">✅</div>
            <h3>Email verified!</h3>
            <p>Please sign in with your password to continue.</p>
          </div>
        `;
      }
      _pendingPassword = '';
      setTimeout(() => {
        showTab('login');
        const emailInput = document.getElementById('login-email');
        if (emailInput) emailInput.value = _pendingEmail;
      }, 2000);
    }
  } else {
    setLoading('verify-submit', false);
    // No stored password — redirect to login
    if (panelVerify) {
      panelVerify.innerHTML = `
        <div class="auth-success">
          <div class="auth-success-icon">✅</div>
          <h3>Email verified!</h3>
          <p>Please sign in with your password to continue.</p>
        </div>
      `;
    }
    setTimeout(() => {
      showTab('login');
      const emailInput = document.getElementById('login-email');
      if (emailInput) emailInput.value = _pendingEmail;
    }, 2000);
  }
});

// ── Resend OTP ────────────────────────────────────────────────

document.getElementById('resend-otp-btn').addEventListener('click', async () => {
  if (!_pendingEmail) return;

  const { ok, status, data } = await apiPost('/auth/resend-otp', { email: _pendingEmail });

  if (ok) {
    setBannerError('verify-error', '');
    const sub = document.getElementById('verify-sub');
    const orig = sub.innerHTML;
    sub.innerHTML = '✅ New code sent! Check your inbox.';
    sub.style.color = 'var(--color-ok)';
    startResendCountdown(60);
    setTimeout(() => { sub.innerHTML = orig; sub.style.color = ''; }, 4000);
  } else {
    const msg = data.detail || 'Could not resend. Please try again.';
    setBannerError('verify-error', msg);
    if (status === 429) startResendCountdown(60);
  }
});

// ── Login form ────────────────────────────────────────────────

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  clearErrors();

  const email      = document.getElementById('login-email').value.trim();
  const password   = document.getElementById('login-password').value;
  const rememberMe = document.getElementById('remember-me').checked;

  let valid = true;
  if (!email)    { setFieldError('login-email-error', 'Email is required'); valid = false; }
  if (!password) { setFieldError('login-password-error', 'Password is required'); valid = false; }
  if (!valid) return;

  setLoading('login-submit', true);
  const { ok, status, data } = await apiPost('/auth/login', {
    email, password, remember_me: rememberMe,
  });
  setLoading('login-submit', false);

  if (ok) {
    window.location.href = '/';
  } else {
    if (status === 403 && data.detail?.includes('verify')) {
      _pendingEmail = email;
      setBannerError('login-error', 'Please verify your email first. Sending a new code...');
      await apiPost('/auth/resend-otp', { email });
      setTimeout(() => showVerifyScreen(email), 1500);
    } else if (status === 401) {
      setBannerError('login-error', 'Incorrect email or password.');
    } else {
      setBannerError('login-error', data.detail || 'Something went wrong.');
    }
  }
});

// ── Forgot password ───────────────────────────────────────────

document.getElementById('forgot-password-btn').addEventListener('click', () => {
  alert('Password reset is not yet available. Please create a new account or contact support.');
});

// ── Utility ───────────────────────────────────────────────────

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
