from config import LAP_ROW_H


# 7. Oldalsablon: CSS animációk + földgömb-forgató JavaScript
#   - CSS: a dobogó és az oldalváltás animációi
#   - JS: a földgömb folyamatos forgatása, és a kattintáskor az oldal kicsúszása
INDEX_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    {%metas%}
    <title>{%title%}</title>
    <link rel="icon" href="/assets/images/favicon.svg?v=2">
    {%css%}
    <script>
        // --- Animációk CSS-e (a dobogó és az oldalváltás) ---
        (function () {
            var css = '@keyframes podium-grow { from { height: 0; padding-top: 0; } }'
                    + '@keyframes podium-fade { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }'
                    + '.podium-bar { animation: podium-grow 0.7s cubic-bezier(.2,.8,.2,1) both; }'
                    + '.podium-text { animation: podium-fade 0.5s ease-out both; }'
                    + '@keyframes bar-grow { from { transform: scaleY(0); } to { transform: scaleY(1); } }'
                    + '__DELTA_CSS__'
                    + '@keyframes page-in-right { from { opacity: 0; transform: translateX(90px); } to { opacity: 1; transform: none; } }'
                    + '@keyframes page-in-left { from { opacity: 0; transform: translateX(-90px); } to { opacity: 1; transform: none; } }'
                    + '.page-right { animation: page-in-right __PAGE_IN_S__s cubic-bezier(.2,.8,.2,1) backwards; }'
                    + '.page-left { animation: page-in-left __PAGE_IN_S__s cubic-bezier(.2,.8,.2,1) backwards; }'
                    + '@keyframes page-out-left { from { opacity: 1; transform: none; } to { opacity: 0; transform: translateX(-90px); } }'
                    + '@keyframes page-out-right { from { opacity: 1; transform: none; } to { opacity: 0; transform: translateX(90px); } }'
                    + '.page-out-left { animation: page-out-left __PAGE_OUT_S__s ease-in forwards; }'
                    + '.page-out-right { animation: page-out-right __PAGE_OUT_S__s ease-in forwards; }'
                    + '@keyframes lap-fade { from { opacity: 0; } to { opacity: 1; } }'
                    + '@keyframes lap-grow { from { width: 0; } }'
                    + '.lap-wrap { position: relative; }'
                    + '.lap-row { position: absolute; top: 0; left: 0; right: 0; display: flex; align-items: center; gap: 12px; transition: transform 0.8s cubic-bezier(.2,.8,.2,1); animation: lap-fade 0.6s ease-out __LAP_DELAY__s both; }'
                    + '.lap-name { width: 210px; flex: none; font-size: 14px; line-height: 1.25; }'
                    + '.lap-track { position: relative; flex: 1; align-self: stretch; display: flex; align-items: center; gap: 10px; }'
                    + '.lap-bar { flex: none; height: 24px; min-width: 3px; border-radius: 3px 8px 8px 3px; box-shadow: 0 3px 0 rgba(0,0,0,.4), 0 6px 10px rgba(0,0,0,.35), inset 0 2px 0 rgba(255,255,255,.3); animation: lap-grow 0.9s cubic-bezier(.2,.8,.2,1) __LAP_BAR_DELAY__s both; }'
                    + '.lap-time { flex: none; font-size: 16px; font-weight: 900; font-style: italic; }'
                    + '.lap-fast { position: absolute; top: -4px; bottom: -4px; width: 3px; margin-left: -1px; background: #F2F2F2; border-radius: 2px; }'
                    + '__LAP_CSS__'
                    + '@keyframes chip-in { from { opacity: 0; transform: translateX(-140px); } to { opacity: 1; transform: none; } }'
                    + '.tyre-legend { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px 24px; margin: 4px 0 12px; }'
                    + '.tyre-chip { display: flex; flex-direction: column; align-items: center; gap: 4px; }'
                    + '.tyre-chip img { height: 80px; width: 80px; object-fit: contain; opacity: 0; }'
                    + '.tyre-lbl { opacity: 0; }'
                    + '.tyre-legend.in .tyre-chip img, .tyre-legend.in .tyre-lbl { animation: chip-in 1.4s cubic-bezier(.2,.8,.2,1) both; }'
                    + '@keyframes bar-in { from { opacity: 0; transform: translateX(-70px); } to { opacity: 1; transform: none; } }'
                    + '.tyre-anim:not(.in) .barlayer .point, .tyre-anim:not(.in) .scatterlayer { opacity: 0; }'
                    + '.tyre-anim.in .barlayer .point { animation: bar-in 1.8s cubic-bezier(.2,.8,.2,1) 0.4s both; }'
                    + '.tyre-anim.in .scatterlayer { animation: lap-fade 1.2s ease-out 1.6s both; }'
                    + 'html, body { overflow-x: hidden; }';
            var st = document.createElement('style');
            st.id = 'podium-css';
            st.textContent = css;
            document.head.appendChild(st);
        })();
        // --- Földgömb forgatása és a főoldal kicsúszása ---
        (function () {
            var lon = __START_LON__;
            var paused = false;
 
            // Az aktuális oldal kicsúszik (dir: 'left' vagy 'right')
            function exitPage(dir) {
                var pg = document.querySelector('#page > div');
                if (!pg || pg.classList.contains('page-out-left') || pg.classList.contains('page-out-right')) return;
                pg.classList.remove('page-left', 'page-right');
                pg.classList.add(dir === 'left' ? 'page-out-left' : 'page-out-right');
            }
 
            setInterval(function () {
                var el = document.getElementById('globe');
                var gd = el ? el.querySelector('.js-plotly-plot') : null;
 
                // Földgömb pontjára kattintás: a főoldal balra csúszik ki
                if (gd && typeof gd.on === 'function' && !gd._exitBound) {
                    gd._exitBound = true;
                    gd.on('plotly_click', function () { exitPage('left'); });
                    // A Dash a hoverData-t nem üríti ki magától: elhagyáskor mi nullázzuk
                    gd.on('plotly_unhover', function () {
                        if (window.dash_clientside && window.dash_clientside.set_props)
                            window.dash_clientside.set_props('globe', {hoverData: null});
                    });
                }
                if (paused) return;
 
                // Minden tickben egy kicsit tovább forgatjuk a földgömböt
                if (gd && gd.layout && window.Plotly) {
                    lon = (lon + __STEP_DEG__) % 360;
                    window.Plotly.relayout(gd, {'geo.projection.rotation.lon': lon});
                }
            }, __INTERVAL_MS__);
        })();
        (function () {
            function mark() {
                document.querySelectorAll('.bar-anim .js-plotly-plot').forEach(function (gd) {
                    if (!gd._fullLayout || !gd._fullLayout.yaxis) return;
                    var zero = gd._fullLayout.yaxis.l2p(0);
                    gd.querySelectorAll('.barlayer .point:not([data-o])').forEach(function (p) {
                        var path = p.querySelector('path');
                        if (!path) return;
                        var b = path.getBBox();
                        var atBottom = Math.abs(b.y + b.height - zero) <= Math.abs(b.y - zero);
                        p.setAttribute('data-o', atBottom ? 'b' : 't');
                    });
                });
            }
            document.addEventListener('DOMContentLoaded', function () {
                new MutationObserver(mark).observe(document.body, { childList: true, subtree: true });
            });
        })();
         (function () {
            var ROUNDS = __ROUND_NAMES__;
            var lastGraph = null;

            function tickAt(x, y) {
                var hit = null;
                document.querySelectorAll('.nav-chart .xtick text').forEach(function (t) {
                    var r = t.getBoundingClientRect();
                    if (x >= r.left - 4 && x <= r.right + 4 && y >= r.top - 4 && y <= r.bottom + 4)
                        hit = t;
                });
                return hit;
            }

            document.addEventListener('mousemove', function (e) {
                var t = tickAt(e.clientX, e.clientY);
                var g = t ? t.closest('.nav-chart') : null;
                if (lastGraph && lastGraph !== g) lastGraph.style.cursor = '';
                if (g) g.style.cursor = 'pointer';
                lastGraph = g;
            });

            document.addEventListener('click', function (e) {
                var t = tickAt(e.clientX, e.clientY);
                if (!t) return;
                var rn = ROUNDS[t.textContent.trim()];
                if (!rn) return;
                var p = location.pathname.split('/').filter(Boolean);
                var slug = p[0] === 'similar' ? (p[3] || '') : p[0] === 'group' ? '' : (p[2] || '');
                if (slug === 'race') slug = '';
                window.history.pushState({}, '', '/race/' + rn + (slug ? '/' + slug : ''));
                window.dispatchEvent(new PopStateEvent('popstate'));
            });
        })();
        // --- Zene: háttérzene + a győztes himnusza ---
        var anthemVol = ANTHEM_VOL;
        (function () {
            var THEME_VOL = __THEME_VOL__, ANTHEM_VOL = __ANTHEM_VOL__, ANTHEM_S = __ANTHEM_S__;
            var theme = new Audio('__THEME_FILE__');
            theme.loop = true;
            theme.volume = THEME_VOL;
            var anthem = null, anthemTimer = null, fadeTimer = null;
            var anthemActive = false;

            function playTheme() {
                if (anthemActive) return;
                theme.play().catch(function () {});
            }
            // Ha a böngésző blokkolta az automatikus indítást, az első interakció elindítja
            function startTheme() {
                if (anthemActive) return;
                theme.play().then(function () {
                    document.removeEventListener('pointerdown', startTheme);
                    document.removeEventListener('keydown', startTheme);
                }).catch(function () {});
            }
            playTheme();
            window.addEventListener('load', playTheme);
            document.addEventListener('pointerdown', startTheme);
            document.addEventListener('keydown', startTheme);

            function stopAnthem(resume) {
                clearTimeout(anthemTimer);
                clearInterval(fadeTimer);
                if (anthem) { anthem.pause(); anthem = null; }
                anthemActive = false;
                if (resume !== false) playTheme();
            }

            function fadeOut() {
                var a = anthem;
                if (!a) return;
                fadeTimer = setInterval(function () {
                    a.volume = Math.max(0, a.volume - anthemVol / 10);
                    if (a.volume <= 0.001) stopAnthem();
                }, 100);
            }

            function playAnthem(src, delayS, vol, loop) {
                stopAnthem(false);
                if (!src) { playTheme(); return; }
                anthemActive = true;
                anthemVol = vol;
                theme.pause();
                anthemTimer = setTimeout(function () {
                    var a = new Audio(src);
                    anthem = a;
                    a.volume = vol;
                    a.loop = loop;
                    a.play().catch(function () { if (anthem === a) stopAnthem(); });
                    if (!loop) anthemTimer = setTimeout(fadeOut, (ANTHEM_S - 1) * 1000);
                }, delayS * 1000);
            }

            function check() {
                var t = document.getElementById('anthem-trigger');
                var token = t ? t.getAttribute('data-token') : null;
                if (token === lastToken) return;
                lastToken = token;
                if (t) playAnthem(t.getAttribute('data-src'),
                                  parseFloat(t.getAttribute('data-delay')) || 0,
                                  parseFloat(t.getAttribute('data-vol')) || ANTHEM_VOL,
                                  t.getAttribute('data-loop') === '1');
                else stopAnthem();
            }

            document.addEventListener('DOMContentLoaded', function () {
                var lastToken = null;
                function check() {
                    var t = document.getElementById('anthem-trigger');
                    var token = t ? t.getAttribute('data-token') : null;
                    if (token === lastToken) return;
                    lastToken = token;
                    if (t) playAnthem(t.getAttribute('data-src'),
                                      parseFloat(t.getAttribute('data-delay')) || 0);
                    else stopAnthem();
                }
                new MutationObserver(check).observe(document.body, {
                    childList: true, subtree: true,
                    attributes: true, attributeFilter: ['data-token']
                });
            });
        })();
        // --- Gumik beúszása, amikor a képernyőre görgetünk ---
        (function () {
            var io = new IntersectionObserver(function (entries) {
                entries.forEach(function (e) {
                    if (e.isIntersecting) {
                        e.target.classList.add('in');
                        io.unobserve(e.target);
                    }
                });
            }, { threshold: 0.3 });
            setInterval(function () {
                document.querySelectorAll('.tyre-legend:not([data-obs]), .tyre-anim:not([data-obs]), .bar-anim:not([data-obs])').forEach(function (el) {
                    el.setAttribute('data-obs', '1');
                    io.observe(el);
                });
            }, 300);
        })();
    </script>
</head>
<body>
    {%app_entry%}
    <footer>
        {%config%}
        {%scripts%}
        {%renderer%}
    </footer>
</body>
</html>"""
 

# 8. App, útvonalválasztás és callbackek

#Köridő oszlopok rendezése
def _lap_css(max_rows=40):
    out = []
    for i in range(max_rows):
        y = i * LAP_ROW_H
        d = i * 0.03
        out.append(f".lap-row.a-{i}{{transform:translateY({y}px);transition-delay:{d:.2f}s}}")
        out.append(f".lap-sorted .lap-row.s-{i}{{transform:translateY({y}px);transition-delay:{d:.2f}s}}")
    return "".join(out)

#Oszlopok animációja
def _delta_css():
    return (".bar-anim:not(.in) .barlayer .point{opacity:0}"
            ".bar-anim.in .point:not([data-o]){opacity:0}"
            ".bar-anim.in .point[data-o]{transform-box:fill-box;"
            "animation:bar-grow 1.2s cubic-bezier(.2,.8,.2,1) both}"
            '.bar-anim .point[data-o="b"]{transform-origin:center bottom}'
            '.bar-anim .point[data-o="t"]{transform-origin:center top}'
            ".nav-chart .nsewdrag, .nav-chart .cursor-pointer"
            "{cursor:default !important}")