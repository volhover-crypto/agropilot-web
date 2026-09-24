/* ============================================================
   ui-reka.js — Vue-слой на Reka UI для AgroPILOT.
   Заменяет самописные модалки/тосты/палитру Ctrl+K.
   Требует js/vendor/vue-reka.bundle.js (window.VueReka) и css/reka-ui.css.
   Глобальный API (вызывается из app.objects.js / index.html):
     $modal.open({ title, bodyHtml, onSave, saveText, cancelText,
                   wide, noFooter, locked })
     $modal.close(); $modal.isOpen()
     $toast(msg, kind — «ok» | «err» | «info»)
     $palette.open({ placeholder, fetch(q)->items, onPick(item) })
     $palette.close()
     $login.open()
   ============================================================ */
(function () {
  'use strict';
  if (!window.VueReka) { console.error('[ui-reka] vue-reka.bundle.js не загружен'); return; }
  var V = window.VueReka.Vue;
  var C = window.VueReka.components;
  var h = V.h, reactive = V.reactive, nextTick = V.nextTick;

  // ---------- состояние ----------
  var mstate = reactive({
    open: false, title: '', bodyHtml: '', onSave: null,
    saveText: 'Сохранить', cancelText: 'Отмена',
    wide: false, noFooter: false, locked: false,
  });
  var toasts = reactive([]);
  var pstate = reactive({
    open: false, query: '', items: [], active: 0,
    placeholder: 'Поиск…', fetch: null, onPick: null,
  });

  // ---------- модальное окно ----------
  function modalOpen(opts) {
    mstate.title = opts.title || '';
    mstate.bodyHtml = opts.bodyHtml || '';
    mstate.onSave = opts.onSave || null;
    mstate.saveText = opts.saveText || 'Сохранить';
    mstate.cancelText = opts.cancelText || 'Отмена';
    mstate.wide = !!opts.wide;
    mstate.noFooter = !!opts.noFooter;
    mstate.locked = !!opts.locked;
    mstate.open = true;
  }
  function modalClose() { mstate.open = false; }
  window.$modal = { open: modalOpen, close: modalClose, isOpen: function () { return mstate.open; } };

  function modalSave() {
    if (mstate.onSave && mstate.onSave() === false) return;
    modalClose();
  }

  // ---------- тосты ----------
  function toastRemove(id) {
    var i = toasts.findIndex(function (t) { return t.id === id; });
    if (i >= 0) toasts.splice(i, 1);
  }
  window.$toast = function (msg, kind) {
    var id = Date.now() + Math.random();
    toasts.push({ id: id, msg: msg, kind: kind || 'ok' });
    // страховка: убрать даже если ToastRoot не отработал
    setTimeout(function () { toastRemove(id); }, 8000);
  };

  // ---------- палитра Ctrl/Cmd-K ----------
  function paletteRefresh() {
    if (!pstate.fetch) return;
    pstate.items = pstate.fetch(pstate.query) || [];
    if (pstate.active >= pstate.items.length) pstate.active = 0;
  }
  function palettePick(item) {
    var cb = pstate.onPick;
    pstate.open = false;
    if (cb) nextTick(function () { cb(item); });
  }
  window.$palette = {
    open: function (opts) {
      pstate.placeholder = opts.placeholder || 'Поиск…';
      pstate.fetch = opts.fetch || null;
      pstate.onPick = opts.onPick || null;
      pstate.query = '';
      pstate.active = 0;
      paletteRefresh();
      pstate.open = true;
    },
    close: function () { pstate.open = false; },
  };

  // ---------- логин ----------
  window.$login = {
    open: function () {
      modalOpen({
        title: 'Вход в систему',
        locked: true,
        noFooter: true,
        bodyHtml:
          '<div style="display:flex;align-items:center;gap:8px;margin-bottom:16px">' +
          '<img src="assets/apilot_icon.jpg" alt="AgroPILOT" style="width:32px;height:32px;border-radius:8px" />' +
          '<div><div style="font-weight:600">AgroPILOT</div><div class="label">Вход в систему</div></div>' +
          '</div>' +
          '<div style="display:flex;flex-direction:column;gap:12px">' +
          '<div><div class="label" style="margin-bottom:4px">Логин</div>' +
          '<input id="loginInput" class="input w-full" placeholder="Логин" /></div>' +
          '<div><div class="label" style="margin-bottom:4px">Пароль</div>' +
          '<input id="loginPassword" type="password" class="input w-full" placeholder="••••••••" ' +
          'onkeydown="if(event.key===\'Enter\')doLogin()" /></div>' +
          '<div id="loginError" class="text-sm" style="display:none;color:var(--err)"></div>' +
          '<button id="loginBtn" class="btn btn-accent w-full" onclick="doLogin()">Войти</button>' +
          '</div>',
      });
    },
  };

  // ---------- Vue-приложение ----------
  function renderModal() {
    return h(C.DialogRoot, {
      open: mstate.open,
      'onUpdate:open': function (v) { if (!v && !mstate.locked) modalClose(); },
    }, function () {
      return h(C.DialogPortal, function () {
        return [
          h(C.DialogOverlay, { class: 'rk-overlay' }),
          h(C.DialogContent, {
            class: 'rk-dialog' + (mstate.wide ? ' rk-wide' : ''),
            'aria-describedby': undefined,
            onInteractOutside: function (e) { if (mstate.locked) e.preventDefault(); },
            onEscapeKeyDown: function (e) { if (mstate.locked) e.preventDefault(); },
            onOpenAutoFocus: function (e) {
              // фокус на первое поле формы, а не на кнопке закрытия
              e.preventDefault();
              nextTick(function () {
                var f = document.querySelector('.rk-dialog-body input, .rk-dialog-body textarea, .rk-dialog-body select');
                if (f) f.focus();
              });
            },
          }, function () {
            var kids = [
              h('div', { class: 'rk-dialog-head' }, [
                h(C.DialogTitle, function () { return mstate.title; }),
                mstate.locked ? null : h(C.DialogClose, {
                  class: 'btn', style: 'font-size:12px', 'aria-label': 'Закрыть',
                }, function () { return '✕'; }),
              ]),
              h('div', { class: 'rk-dialog-body', innerHTML: mstate.bodyHtml }),
            ];
            if (!mstate.noFooter) {
              kids.push(h('div', { class: 'rk-dialog-foot' }, [
                h(C.DialogClose, { class: 'btn', style: 'font-size:13px' }, function () { return mstate.cancelText; }),
                h('button', { class: 'btn btn-accent', style: 'font-size:13px', onClick: modalSave }, function () { return mstate.saveText; }),
              ]));
            }
            return kids;
          }),
        ];
      });
    });
  }

  function renderPalette() {
    return h(C.DialogRoot, {
      open: pstate.open,
      'onUpdate:open': function (v) { if (!v) pstate.open = false; },
    }, function () {
      return h(C.DialogPortal, function () {
        return [
          h(C.DialogOverlay, { class: 'rk-overlay' }),
          h(C.DialogContent, {
            class: 'rk-palette',
            'aria-describedby': undefined,
            onOpenAutoFocus: function (e) { e.preventDefault(); },
          }, function () {
            var kids = [
              h(C.DialogTitle, { style: 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)' }, 'Быстрый поиск'),
              h('input', {
                class: 'rk-palette-input',
                placeholder: pstate.placeholder,
                value: pstate.query,
                onInput: function (e) { pstate.query = e.target.value; pstate.active = 0; paletteRefresh(); },
                onKeydown: function (e) {
                  if (e.key === 'ArrowDown') { e.preventDefault(); if (pstate.items.length) pstate.active = (pstate.active + 1) % pstate.items.length; }
                  else if (e.key === 'ArrowUp') { e.preventDefault(); if (pstate.items.length) pstate.active = (pstate.active - 1 + pstate.items.length) % pstate.items.length; }
                  else if (e.key === 'Enter') { e.preventDefault(); var it = pstate.items[pstate.active]; if (it) palettePick(it); }
                },
              }),
              h('div', { class: 'rk-palette-list' }, pstate.items.length
                ? pstate.items.map(function (it, i) {
                    return h('div', {
                      class: 'rk-palette-item',
                      'data-active': pstate.active === i ? 'true' : 'false',
                      role: 'option',
                      'aria-selected': pstate.active === i ? 'true' : 'false',
                      onMouseenter: function () { pstate.active = i; },
                      onClick: function () { palettePick(it); },
                    }, [
                      h('span', { style: 'font-size:18px' }, it.icon || ''),
                      h('div', { style: 'flex:1;min-width:0' }, [
                        h('div', { style: 'font-size:14px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' }, it.title || ''),
                        h('div', { style: 'font-size:12px;color:var(--text-dim)' }, it.sub || ''),
                      ]),
                      it.kind ? h('span', { class: 'pill' }, it.kind) : null,
                    ]);
                  })
                : h('div', { style: 'font-size:13px;padding:12px;text-align:center;color:var(--text-mute)' }, 'Ничего не найдено')),
              h('div', { class: 'rk-palette-foot' }, '↑↓ — выбор · Enter — открыть · Esc — закрыть'),
            ];
            return kids;
          }),
        ];
      });
    });
  }

  function renderToasts() {
    return h(C.ToastProvider, { duration: 3200 }, function () {
      return h(C.ToastViewport, { class: 'rk-toast-region' }, function () {
        return toasts.map(function (t) {
          return h(C.ToastRoot, {
            key: t.id,
            class: 'rk-toast' + (t.kind === 'err' ? ' rk-err' : t.kind === 'info' ? ' rk-info' : ''),
            'onUpdate:open': function (v) { if (!v) toastRemove(t.id); },
          }, function () {
            return [
              h('span', { style: 'color:' + (t.kind === 'err' ? 'var(--err)' : t.kind === 'info' ? 'var(--info)' : 'var(--ok)') + ';font-weight:600' },
                t.kind === 'err' ? '✕' : t.kind === 'info' ? 'ℹ' : '✓'),
              h(C.ToastTitle, { style: 'flex:1' }, t.msg),
            ];
          });
        });
      });
    });
  }

  var root = document.createElement('div');
  root.id = 'reka-root';
  document.documentElement.appendChild(root); // в <html>: вне x-data Alpine тела
  V.createApp({ render: function () { return [renderModal(), renderPalette(), renderToasts()]; } }).mount(root);
})();
