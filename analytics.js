(() => {
  'use strict';

  const measurementId = 'G-7FMXD7RCJZ';
  const preferenceKey = 'leonelki-analytics-consent';
  const production = ['leonelki.com', 'www.leonelki.com'].includes(location.hostname);
  const japanese = document.documentElement.lang === 'ja';
  const readPreference = () => {
    try { return localStorage.getItem(preferenceKey); } catch { return null; }
  };
  const savePreference = (value) => {
    try { localStorage.setItem(preferenceKey, value); } catch { /* This visit only. */ }
  };

  const startAnalytics = () => {
    if (!production || document.getElementById('google-analytics-tag')) return;
    window[`ga-disable-${measurementId}`] = false;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag('consent', 'default', {
      analytics_storage: 'granted',
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied'
    });
    window.gtag('js', new Date());
    window.gtag('config', measurementId, {
      allow_google_signals: false,
      allow_ad_personalization_signals: false
    });
    const script = document.createElement('script');
    script.id = 'google-analytics-tag';
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${measurementId}`;
    document.head.append(script);
  };

  const declineAnalytics = () => {
    window[`ga-disable-${measurementId}`] = true;
    if (window.gtag) window.gtag('consent', 'update', { analytics_storage: 'denied' });
    // Remove only this property's first-party Analytics cookies after withdrawal.
    ['_ga', `_ga_${measurementId.slice(2).replace(/-/g, '')}`].forEach((name) => {
      ['', location.hostname, '.leonelki.com'].forEach((domain) => {
        document.cookie = `${name}=; Max-Age=0; Path=/; SameSite=Lax${domain ? `; Domain=${domain}` : ''}`;
      });
    });
  };

  const style = document.createElement('style');
  style.textContent = `
    #analytics-choice { position:fixed; inset:auto 16px 16px; z-index:10000;
      max-width:720px; margin:auto; padding:16px; background:#f7f4ed; color:#171717;
      border:1px solid #171717; box-shadow:0 4px 24px #0002;
      font:14px/1.5 system-ui,sans-serif; text-align:left; box-sizing:border-box; }
    #analytics-choice p { margin:0 0 12px; color:inherit; font:inherit; }
    #analytics-choice a { color:inherit; text-decoration:underline; }
    #analytics-choice .analytics-actions { display:flex; flex-wrap:wrap; gap:8px; }
    #analytics-choice button { padding:8px 16px; border:1px solid #171717;
      border-radius:0; background:transparent; color:inherit; cursor:pointer; font:inherit; }
    #analytics-choice button:focus-visible { outline:3px solid #315bba; outline-offset:2px; }
  `;
  document.head.append(style);

  const showChoice = () => {
    if (document.getElementById('analytics-choice')) return;
    const banner = document.createElement('section');
    banner.id = 'analytics-choice';
    banner.setAttribute('aria-label', japanese ? 'アクセス解析の設定' : 'Visitor analytics');
    banner.innerHTML = japanese
      ? '<p>Google アナリティクスを使ったアクセス解析を許可しますか？許可した場合のみ Cookie を使用して、閲覧されたページや訪問元を集計します。<a href="/privacy.html">プライバシーポリシー（英語）</a></p><div class="analytics-actions"><button type="button" data-analytics-accept>許可する</button><button type="button" data-analytics-decline>許可しない</button></div>'
      : '<p>Allow visitor analytics? I use Google Analytics cookies to understand which pages people visit and how they find the site. <a href="/privacy.html">Privacy policy</a></p><div class="analytics-actions"><button type="button" data-analytics-accept>Accept</button><button type="button" data-analytics-decline>Decline</button></div>';
    banner.querySelector('[data-analytics-accept]').addEventListener('click', () => {
      savePreference('accepted');
      // Reload after a previous withdrawal so Google's loaded tag starts cleanly.
      const needsReload = document.getElementById('google-analytics-tag')
        && window[`ga-disable-${measurementId}`];
      needsReload ? location.reload() : startAnalytics();
      banner.remove();
    });
    banner.querySelector('[data-analytics-decline]').addEventListener('click', () => {
      savePreference('declined');
      declineAnalytics();
      banner.remove();
    });
    document.body.append(banner);
  };

  document.querySelectorAll('[data-analytics-settings]').forEach((button) => {
    button.addEventListener('click', () => {
      showChoice();
      document.querySelector('[data-analytics-accept]').focus();
    });
  });
  const preference = readPreference();
  preference === 'accepted' ? startAnalytics()
    : preference === 'declined' ? declineAnalytics() : showChoice();
})();
