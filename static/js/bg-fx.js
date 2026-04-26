/**
 * Sci-fi Background FX — PCB Traces + Component Pulses
 * Warm-toned, subtle, never distracting.
 */
(function () {
    'use strict';

    // Respect user's motion preference
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (prefersReduced.matches) return;

    const canvas = document.createElement('canvas');
    canvas.id = 'bg-fx-canvas';
    const ctx = canvas.getContext('2d');

    Object.assign(canvas.style, {
        position: 'fixed',
        top: '0',
        left: '0',
        width: '100%',
        height: '100%',
        zIndex: '0',
        pointerEvents: 'none',
    });

    // Insert as first real child so it layers above body::before (z:-1) but below app-shell (z:1)
    document.body.insertBefore(canvas, document.body.firstChild);

    let W = 0, H = 0;
    let tick = 0;
    let traces = [];
    let components = [];

    /* ========== Geometry Helpers ========== */

    function rand(min, max) { return Math.random() * (max - min) + min; }
    function randInt(min, max) { return Math.floor(rand(min, max)); }
    function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

    /* ========== Scene Generation ========== */

    function generateTrace() {
        const segs = [];
        let x = rand(0, W);
        let y = rand(0, H);
        const segCount = randInt(3, 7);
        const dirs = [0, Math.PI / 2, Math.PI, -Math.PI / 2];
        let dir = pick(dirs);

        for (let i = 0; i < segCount; i++) {
            const len = rand(60, 200);
            const nx = x + Math.cos(dir) * len;
            const ny = y + Math.sin(dir) * len;
            segs.push({ x1: x, y1: y, x2: nx, y2: ny });
            x = nx;
            y = ny;
            if (Math.random() > 0.35) {
                dir += Math.random() > 0.5 ? Math.PI / 2 : -Math.PI / 2;
            }
        }

        return {
            segs,
            hasFlow: Math.random() > 0.55,
            flowPos: Math.random(),
            flowSpeed: rand(0.0015, 0.004),
            flowWarm: Math.random() > 0.4, // true = gold, false = teal
            flowOffset: rand(0, 100),
        };
    }

    function generateComponent() {
        const types = ['chip', 'resistor', 'capacitor', 'dip'];
        return {
            type: pick(types),
            x: rand(40, W - 40),
            y: rand(40, H - 40),
            rot: pick([0, Math.PI / 2]),
            pulseTimer: randInt(60, 400),
            pulseActive: false,
            pulsePhase: 0,
            pulseWarm: Math.random() > 0.4,
        };
    }

    function buildScene() {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        W = window.innerWidth;
        H = window.innerHeight;
        canvas.width = W * dpr;
        canvas.height = H * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        const area = W * H;
        const traceCount = Math.max(14, Math.min(36, Math.floor(area / 38000)));
        const compCount = Math.max(8, Math.min(22, Math.floor(area / 65000)));

        traces = [];
        for (let i = 0; i < traceCount; i++) traces.push(generateTrace());

        components = [];
        for (let i = 0; i < compCount; i++) components.push(generateComponent());
    }

    /* ========== Trace Flow ========== */

    function pointOnTrace(segs, t) {
        const total = segs.reduce((s, g) => s + Math.hypot(g.x2 - g.x1, g.y2 - g.y1), 0);
        let target = total * t;
        for (const g of segs) {
            const len = Math.hypot(g.x2 - g.x1, g.y2 - g.y1);
            if (target <= len) {
                const r = len === 0 ? 0 : target / len;
                return { x: g.x1 + (g.x2 - g.x1) * r, y: g.y1 + (g.y2 - g.y1) * r };
            }
            target -= len;
        }
        const last = segs[segs.length - 1];
        return { x: last.x2, y: last.y2 };
    }

    /* ========== Drawing ========== */

    function drawTraces() {
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        traces.forEach(tr => {
            // Static trace line
            ctx.strokeStyle = 'rgba(188, 170, 140, 0.18)';
            ctx.lineWidth = 1.4;
            ctx.beginPath();
            tr.segs.forEach((s, i) => {
                if (i === 0) ctx.moveTo(s.x1, s.y1);
                ctx.lineTo(s.x2, s.y2);
            });
            ctx.stroke();

            // Solder-dot at joints
            ctx.fillStyle = 'rgba(188, 170, 140, 0.28)';
            tr.segs.forEach((s, i) => {
                if (i > 0) {
                    ctx.beginPath();
                    ctx.arc(s.x1, s.y1, 2.0, 0, Math.PI * 2);
                    ctx.fill();
                }
            });

            // Flowing light
            if (tr.hasFlow) {
                const pos = pointOnTrace(tr.segs, tr.flowPos);
                if (pos) {
                    const breathe = 0.5 + Math.sin((tick + tr.flowOffset) * 0.04) * 0.5;
                    const rgb = tr.flowWarm ? '243, 212, 170' : '160, 210, 190';

                    // Wide outer glow
                    ctx.shadowColor = `rgba(${rgb}, ${0.6 * breathe})`;
                    ctx.shadowBlur = 22;
                    ctx.fillStyle = `rgba(${rgb}, ${0.65 * breathe})`;
                    ctx.beginPath();
                    ctx.arc(pos.x, pos.y, 4.5, 0, Math.PI * 2);
                    ctx.fill();

                    // Middle halo
                    ctx.shadowBlur = 0;
                    ctx.fillStyle = `rgba(${rgb}, ${0.9 * breathe})`;
                    ctx.beginPath();
                    ctx.arc(pos.x, pos.y, 2.6, 0, Math.PI * 2);
                    ctx.fill();

                    // Bright core
                    ctx.fillStyle = `rgba(255, 252, 245, ${0.95 * breathe})`;
                    ctx.beginPath();
                    ctx.arc(pos.x, pos.y, 1.2, 0, Math.PI * 2);
                    ctx.fill();
                }
            }
        });
    }

    function drawComponents() {
        components.forEach(c => {
            ctx.save();
            ctx.translate(c.x, c.y);
            ctx.rotate(c.rot);

            const baseAlpha = 0.12 + Math.sin(tick * 0.015 + c.x * 0.01) * 0.03;
            ctx.strokeStyle = `rgba(150, 140, 120, ${baseAlpha})`;
            ctx.fillStyle = `rgba(150, 140, 120, ${baseAlpha * 0.6})`;
            ctx.lineWidth = 1;

            const pins = [];

            switch (c.type) {
                case 'chip': {
                    const w = 26, h = 14;
                    ctx.strokeRect(-w / 2, -h / 2, w, h);
                    for (let i = 0; i < 3; i++) {
                        const py = -h / 2 + (i + 0.5) * (h / 3);
                        ctx.beginPath(); ctx.moveTo(-w / 2, py); ctx.lineTo(-w / 2 - 7, py); ctx.stroke();
                        ctx.beginPath(); ctx.moveTo(w / 2, py); ctx.lineTo(w / 2 + 7, py); ctx.stroke();
                        pins.push({ x: -w / 2 - 7, y: py }, { x: w / 2 + 7, y: py });
                    }
                    break;
                }
                case 'resistor': {
                    const w = 22, h = 7;
                    ctx.fillRect(-w / 2, -h / 2, w, h);
                    ctx.strokeStyle = `rgba(150, 140, 120, ${baseAlpha * 1.5})`;
                    ctx.beginPath(); ctx.moveTo(-w / 2, 0); ctx.lineTo(-w / 2 - 5, 0); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(w / 2, 0); ctx.lineTo(w / 2 + 5, 0); ctx.stroke();
                    pins.push({ x: -w / 2 - 5, y: 0 }, { x: w / 2 + 5, y: 0 });
                    break;
                }
                case 'capacitor': {
                    ctx.strokeStyle = `rgba(150, 140, 120, ${baseAlpha * 1.5})`;
                    ctx.beginPath(); ctx.moveTo(-3, -9); ctx.lineTo(-3, 9); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(3, -9); ctx.lineTo(3, 9); ctx.stroke();
                    pins.push({ x: -3, y: -11 }, { x: 3, y: -11 }, { x: -3, y: 11 }, { x: 3, y: 11 });
                    break;
                }
                case 'dip': {
                    const w = 22, h = 34;
                    ctx.strokeRect(-w / 2, -h / 2, w, h);
                    // Pin-1 dot
                    ctx.beginPath(); ctx.arc(-w / 2 + 4, -h / 2 + 4, 1.5, 0, Math.PI * 2); ctx.fill();
                    for (let i = 0; i < 4; i++) {
                        const py = -h / 2 + 7 + i * 7;
                        ctx.beginPath(); ctx.moveTo(-w / 2, py); ctx.lineTo(-w / 2 - 6, py); ctx.stroke();
                        ctx.beginPath(); ctx.moveTo(w / 2, py); ctx.lineTo(w / 2 + 6, py); ctx.stroke();
                        pins.push({ x: -w / 2 - 6, y: py }, { x: w / 2 + 6, y: py });
                    }
                    break;
                }
            }

            ctx.restore();

            // Pulse on random pins
            if (c.pulseActive) {
                const rgb = c.pulseWarm ? '243, 212, 170' : '160, 210, 190';
                const alpha = Math.sin(c.pulsePhase * Math.PI) * 0.85;
                if (alpha > 0.01) {
                    ctx.save();
                    ctx.translate(c.x, c.y);
                    ctx.rotate(c.rot);
                    ctx.fillStyle = `rgba(${rgb}, ${alpha})`;
                    ctx.shadowColor = `rgba(${rgb}, ${alpha * 1.1})`;
                    ctx.shadowBlur = 18;
                    pins.forEach((p, idx) => {
                        if ((idx + c.pulseTimer) % 3 === 0) { // pseudo-random subset
                            ctx.beginPath();
                            ctx.arc(p.x, p.y, 3.2, 0, Math.PI * 2);
                            ctx.fill();
                        }
                    });
                    ctx.shadowBlur = 0;
                    ctx.restore();
                }
            }
        });
    }

    /* ========== Update ========== */

    function update() {
        tick++;

        // Advance flows
        traces.forEach(tr => {
            if (tr.hasFlow) {
                tr.flowPos += tr.flowSpeed;
                if (tr.flowPos > 1) {
                    tr.flowPos = 0;
                    tr.flowWarm = Math.random() > 0.35;
                }
            }
        });

        // Advance pulses
        components.forEach(c => {
            c.pulseTimer--;
            if (c.pulseTimer <= 0) {
                c.pulseTimer = randInt(120, 500);
                c.pulseActive = true;
                c.pulsePhase = 0;
                c.pulseWarm = Math.random() > 0.35;
            }
            if (c.pulseActive) {
                c.pulsePhase += 0.018;
                if (c.pulsePhase >= 1) {
                    c.pulseActive = false;
                }
            }
        });
    }

    /* ========== Loop ========== */

    let frameId;
    function loop() {
        update();
        ctx.clearRect(0, 0, W, H);
        drawTraces();
        drawComponents();
        frameId = requestAnimationFrame(loop);
    }

    /* ========== Init ========== */

    buildScene();
    loop();

    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(buildScene, 250);
    });

    // Page visibility — pause when hidden to save battery
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            cancelAnimationFrame(frameId);
        } else {
            frameId = requestAnimationFrame(loop);
        }
    });
})();
