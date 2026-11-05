(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  // Toasts: dismiss on click, auto-hide after 6 seconds
  function closeToast(t) { t.classList.add('out'); setTimeout(function () { t.remove(); }, 300); }
  $$('.toast').forEach(function (t) {
    $('.toast-x', t).addEventListener('click', function () { closeToast(t); });
    setTimeout(function () { closeToast(t); }, 6000);
  });

  // Live clock (shows the time the entry will be stamped; local device time is only a preview)
  var clock = $('#liveClock');
  if (clock) {
    var tick = function () {
      clock.textContent = new Date().toLocaleString('en-GB', {
        weekday: 'short', day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      });
    };
    tick(); setInterval(tick, 1000);
  }

  // Instant filter of the list already on the page, with highlighted count
  var filter = $('#liveFilter');
  if (filter) {
    var entries = $$('.entry[data-search]');
    var count = $('#filterCount');
    filter.addEventListener('input', function () {
      var q = filter.value.trim().toLowerCase(), shown = 0;
      entries.forEach(function (e) {
        var hit = !q || e.getAttribute('data-search').toLowerCase().indexOf(q) !== -1;
        e.hidden = !hit; if (hit) shown++;
      });
      count.hidden = !q;
      count.textContent = shown + ' of ' + entries.length + ' shown';
    });
  }

  // Manager live refresh (remembered in this browser only)
  var auto = $('#autoRefresh'), timer = null;
  if (auto) {
    var set = function (on) {
      clearInterval(timer);
      if (on) timer = setInterval(function () {
        // do not interrupt someone who is typing a search
        if (!/INPUT|TEXTAREA/.test(document.activeElement.tagName)) location.reload();
      }, 30000);
    };
    try { auto.checked = localStorage.getItem('loobAuto') === '1'; } catch (e) {}
    set(auto.checked);
    auto.addEventListener('change', function () {
      try { localStorage.setItem('loobAuto', auto.checked ? '1' : '0'); } catch (e) {}
      set(auto.checked);
    });
  }

  // Character counters
  $$('.counter').forEach(function (c) {
    var ta = document.getElementById(c.getAttribute('data-for'));
    if (!ta) return;
    var upd = function () { c.textContent = ta.value.length + ' characters'; };
    ta.addEventListener('input', upd); upd();
  });

  // Show/hide password
  $$('.pw-toggle').forEach(function (b) {
    b.addEventListener('click', function () {
      var i = document.getElementById(b.getAttribute('data-target'));
      i.type = i.type === 'password' ? 'text' : 'password';
      b.textContent = i.type === 'password' ? 'Show' : 'Hide';
    });
  });

  // Prevent double submission of forms (important for an occurrence book)
  $$('form.js-once').forEach(function (f) {
    f.addEventListener('submit', function () {
      var btn = $('button[type=submit]', f);
      if (btn) setTimeout(function () { btn.disabled = true; btn.textContent = 'Saving…'; }, 0);
    });
  });
})();
