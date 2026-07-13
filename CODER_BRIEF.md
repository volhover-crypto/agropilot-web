# CODER BRIEF — issue#1, дефекты #1 и #2

> Для агента-кодера или разработчика. Сразу приступай к действиям.

---

## Одной фразой: что сломано

Продовый сайт `https://mdked.hlab.kz/agropilot/` работает с `DEV_MOCK = false`. Это означает:

```js
M = window.EMPTY_MODEL  // все массивы [] — записей нет
```

`#view` пустой на старте и при любом клике. `owlBody` тоже пустой.

---

## Корневая причина

`active`-класс на пункте меню ставится — значит, `$watch('route', ...)` зарегистрирован и Alpine-компонент живой.  
Но `render()` падает **до** `el.innerHTML = ...` молча (без сообщения в Console, кроме `console.log`).

**Наиболее вероятная точка** — `vMyDay4()`, которая вызывается первой при старте:

```js
// в vMyDay4(): зона 1 фокуса
const hot = todayTasks.filter(t => t.score >= 80);         // ✔ безопасно
const activeDeals = M.deals.filter(d => d.stage !== 'Сервис'); // ✔ безопасно

// зона 3: сигналы
// M.signals = [] — здесь OK

// зона 4: wizardCard()
// M.clients.length === 0 → this.wizardCard() вызывается
// wizardCard() внутри: this.petIco(18) → рендерит img-teg — OK
// wizardCard() внутри: this.money(pk.priceFrom) — НЕ вызывается при пустом M

// НО: owlPending() → this.M.owlSuggestions.filter(...)  ← ❗
// EMPTY_MODEL.owlSuggestions = [] — OK

// НО: vMetrics() → M.deals.filter(...) — OK
// НО: vMetrics() → M.STAGES.map(st => ...) ← ❗
// EMPTY_MODEL.STAGES = ['...6 элементов...'] — OK
```

**Главный подозреваемый участок** — `wizardCard()`, строка `step()`:

```js
const step = (done, n, title, desc, btn, attr) =>
  `... <button ... ${attr}>${done ? 'Готово' : btn}</button> ...`;
```

В проде `M.sources = []` → `hasSrc = false` → кнопка рендерится с `attr = 'data-src-add'`.

Handler `data-src-add` навешивается в `bindView()`. Если `bindView()` падает или недоопределён — ошибка поглощается.

---

## Что проверить в первую очередь (АЛГОРИТМ)

### Шаг 1 — найти `bindView()`

Открой `js/app.objects.js`, найди метод `bindView()`.

Убедись, что внутри нет `throw` без `try/catch`.

Чаще всего внутри `bindView()` есть обработчики `data-*` атрибутов — один из них может вызывать метод, который не определён в объекте в том чанке.

```
grep -n 'bindView' js/app.objects.js
grep -n 'data-src-add\|srcAddModal\|sourceAdd' js/app.objects.js
```

Если `srcAddModal()` / `sourceAddModal()` / `monAddModal()` не найден — ЭТО ПРИЧИНА. Кнопка `data-src-add` вызывает несуществующий метод, `bindView()` кидает `TypeError`, Alpine перехватывает ошибку и гасит её. `#view` остаётся пустым.

### Шаг 2 — проверить все `data-*` в wizardCard()

В `wizardCard()` используются три атрибута:

| Атрибут | Метод | Есть в bindView? |
|---|---|---|
| `data-cli-add` | `cliAddModal()` | проверить |
| `data-src-add` | `srcAddModal()` или аналог | **проверить особо** |
| `data-deal-add` | `dealAddModal()` | проверить |

### Шаг 3 — патч для дефекта #1

Вариант А (если метод не есть): **добавить заглушку** в `bindView()`:

```js
// в bindView() — найти блок с data-src-add и добавить:
el.querySelectorAll('[data-src-add]').forEach(n =>
  n.addEventListener('click', () => this.monAddModal && this.monAddModal()));
```

Вариант Б (если метод есть, но неправильно вызывается): **проверить название** метода и исправить ссылку.

Вариант В (корневая защита): **обернуть `bindView()` в try/catch** чтобы `render()` не становился неработоспособным из-за одной ошибки в хандлере:

```js
// в render() — строка после el.innerHTML = ...:
el.innerHTML = `<div class="fade-in">${html}</div>`;
try {
  this.bindView();
} catch (e) {
  console.error('[AgroPILOT] bindView error:', e);
}
this.owlRender();
```

**рекомендую оба варианта**: и защитить `bindView`, и добавить обработчик `data-src-add`.

---

## Дефект #2 — PETUSHKA (после фикса #1)

После того как `#view` начнёт рендерить, проверь:

```
grep -n 'owlInput\|owlAsk\|owlBody\|petSend' js/app.objects.js
```

`owlAsk()` определён, `petSend(q)` определён, фоллбэк `petReply(q)` определён.  
Биндинг `keydown` Enter на `owlInput` навешивается в `init()`:

```js
this.$nextTick(() => {
  const f = document.getElementById('owlInput');
  if (f) f.addEventListener('keydown', e => { if (e.key === 'Enter') this.owlAsk(); });
});
```

Если `init()` выполняется успешно и `#owlInput` есть в DOM, проблемы быть не должно.  

Проверь `owlRender()` — он записывает в `#owlBody`. Убедись, что `document.getElementById('owlBody')` возвращает `non-null`.

Если `owlRender()` падает (TypeError внутри) — `owlBody` тоже останется пустым.  
Возможные кандидаты в `owlRender()`:

```
grep -n 'owlRender\|owlSuggestionsCtx\|owlContext\|sug\.' js/app.objects.js | head -30
```

---

## Коммиты (format)

```
fix(issue#1-1): wrap bindView in try/catch + add data-src-add handler
fix(issue#1-2): <если есть доп фикс owlRender>
```

---

## Чек-лист после патча

```
1. Открыть https://mdked.hlab.kz/agropilot/
2. DevTools Console — ошибок [AgroPILOT] bindView error нет
3. Страница рендерит содержимое (видена зона "Begin work")
4. Клик «Стратегия» → #view наполняется
5. Ввод в owlInput + Enter → owlBody получает ответ ПЕТРУШКИ
```

---

## Ссылки

- Исходник: [`js/app.objects.js`](https://github.com/volhover-crypto/agropilot-web/blob/main/js/app.objects.js)
- Issue: [#1](https://github.com/volhover-crypto/agropilot-web/issues/1)
- OPENCLAW_PROMPT: [`OPENCLAW_PROMPT.md`](https://github.com/volhover-crypto/agropilot-web/blob/main/OPENCLAW_PROMPT.md)
- Прод: `https://mdked.hlab.kz/agropilot/`
