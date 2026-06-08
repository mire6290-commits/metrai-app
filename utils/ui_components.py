def get_wireframe_animation_html():
    """
    Returns the HTML/CSS/SVG code for the Blue Laser Blueprint Scan Animation.
    Full top-view structural plan with blue neon scan line, looping, smooth text rotation.
    """
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }

            body {
                background: #080c18;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-start;
                height: 100%;
                padding: 8px 12px 4px;
                font-family: 'Courier New', Courier, monospace;
                overflow: hidden;
            }

            /* ─── HEADER ─── */
            .ai-header {
                width: 100%;
                text-align: center;
                margin-bottom: 8px;
            }
            .ai-title {
                color: #00D4FF;
                font-size: 0.82rem;
                font-weight: bold;
                letter-spacing: 5px;
                text-transform: uppercase;
                text-shadow: 0 0 10px #00D4FF, 0 0 20px rgba(0,212,255,0.4);
                animation: titlePulse 2.5s ease-in-out infinite;
            }
            .ai-subtitle {
                color: #003d55;
                font-size: 0.6rem;
                letter-spacing: 3px;
                margin-top: 3px;
            }
            .blink {
                animation: blink 0.9s step-end infinite;
            }
            @keyframes blink { 50% { opacity: 0; } }
            @keyframes titlePulse {
                0%, 100% { text-shadow: 0 0 10px #00D4FF; }
                50%       { text-shadow: 0 0 18px #00D4FF, 0 0 35px rgba(0,212,255,0.5); }
            }

            /* ─── PLAN SVG WRAPPER ─── */
            .plan-wrap {
                width: 100%;
                max-width: 600px;
                height: 135px;
                position: relative;
                border: 1px solid rgba(0,212,255,0.12);
                background:
                    linear-gradient(rgba(0,180,255,0.035) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(0,180,255,0.035) 1px, transparent 1px);
                background-size: 28px 28px;
                overflow: hidden;
            }

            /* ─── SCAN LINE — BLUE NEON ─── */
            .scan-line {
                position: absolute;
                left: 0;
                top: 0;
                width: 100%;
                height: 2px;
                background: linear-gradient(
                    90deg,
                    transparent 0%,
                    rgba(0,212,255,0.3) 10%,
                    #00D4FF 35%,
                    #ffffff 50%,
                    #00D4FF 65%,
                    rgba(0,212,255,0.3) 90%,
                    transparent 100%
                );
                box-shadow:
                    0 0 6px 1px rgba(0, 212, 255, 1),
                    0 0 14px 3px rgba(0, 212, 255, 0.6),
                    0 0 30px 6px rgba(0, 100, 255, 0.3);
                animation: laserScan 3s linear infinite;
            }
            .scan-glow {
                position: absolute;
                left: 0;
                width: 100%;
                height: 50px;
                background: linear-gradient(
                    180deg,
                    transparent 0%,
                    rgba(0,212,255,0.06) 40%,
                    rgba(0,212,255,0.10) 50%,
                    rgba(0,212,255,0.06) 60%,
                    transparent 100%
                );
                pointer-events: none;
                animation: glowFollow 3s linear infinite;
            }
            @keyframes laserScan {
                0%   { top: -2px; opacity: 0; }
                4%   { opacity: 1; }
                96%  { opacity: 1; }
                100% { top: 135px; opacity: 0; }
            }
            @keyframes glowFollow {
                0%   { top: -50px; }
                100% { top: 135px; }
            }

            /* ─── CORNER BRACKETS ─── */
            .corner {
                position: absolute;
                width: 10px;
                height: 10px;
                border-color: rgba(0,212,255,0.4);
                border-style: solid;
            }
            .tl { top: 3px;  left: 3px;  border-width: 1px 0 0 1px; }
            .tr { top: 3px;  right: 3px; border-width: 1px 1px 0 0; }
            .bl { bottom: 3px; left: 3px;  border-width: 0 0 1px 1px; }
            .br { bottom: 3px; right: 3px; border-width: 0 1px 1px 0; }

            /* ─── SVG STRUCTURAL ELEMENTS ─── */
            svg { position: absolute; top: 0; left: 0; }

            .main-beam {
                fill: none;
                stroke: #00D4FF;
                stroke-width: 2.2;
                stroke-linecap: round;
                opacity: 0.65;
                filter: url(#glowFilter);
            }
            .sec-beam {
                fill: none;
                stroke: #00D4FF;
                stroke-width: 1.2;
                stroke-linecap: round;
                opacity: 0.4;
            }
            .brace-line {
                fill: none;
                stroke: #00D4FF;
                stroke-width: 1;
                stroke-dasharray: 5 3;
                opacity: 0.3;
            }
            .col-dot {
                fill: #00D4FF;
                opacity: 0.7;
                filter: url(#glowFilter);
            }
            .col-dot-sm {
                fill: none;
                stroke: #00D4FF;
                stroke-width: 1.2;
                opacity: 0.45;
            }
            .dim-text {
                fill: rgba(0,180,255,0.2);
                font-size: 7px;
                font-family: 'Courier New', monospace;
            }

            /* ─── STATUS TEXT ─── */
            .status-wrap {
                width: 100%;
                max-width: 600px;
                height: 42px;
                position: relative;
                margin-top: 7px;
            }
            .msg {
                position: absolute;
                top: 0; left: 0;
                width: 100%;
                text-align: center;
                opacity: 0;
            }
            .msg-title {
                color: #00D4FF;
                font-size: 0.88rem;
                font-weight: bold;
                letter-spacing: 2px;
                text-shadow: 0 0 8px rgba(0,212,255,0.7);
            }
            .msg-sub {
                color: #004d66;
                font-size: 0.68rem;
                margin-top: 3px;
                letter-spacing: 1px;
            }
            .msg:nth-child(1) { animation: msgCycle 10s infinite 0.0s; }
            .msg:nth-child(2) { animation: msgCycle 10s infinite 2.5s; }
            .msg:nth-child(3) { animation: msgCycle 10s infinite 5.0s; }
            .msg:nth-child(4) { animation: msgCycle 10s infinite 7.5s; }
            @keyframes msgCycle {
                0%   { opacity: 0; transform: translateY(5px); }
                8%   { opacity: 1; transform: translateY(0); }
                20%  { opacity: 1; transform: translateY(0); }
                27%  { opacity: 0; transform: translateY(-4px); }
                100% { opacity: 0; }
            }

            /* ─── PROGRESS BAR ─── */
            .prog-wrap {
                width: 100%;
                max-width: 600px;
                display: flex;
                align-items: center;
                gap: 8px;
                margin-top: 5px;
            }
            .prog-label {
                color: rgba(0,212,255,0.4);
                font-size: 0.6rem;
                letter-spacing: 2px;
                white-space: nowrap;
            }
            .prog-bar {
                flex: 1;
                height: 2px;
                background: rgba(0,212,255,0.08);
                border-radius: 2px;
                overflow: hidden;
            }
            .prog-fill {
                height: 100%;
                background: linear-gradient(90deg, #004466 0%, #00D4FF 100%);
                box-shadow: 0 0 8px rgba(0,212,255,0.8);
                animation: progScan 3s linear infinite;
            }
            @keyframes progScan {
                0%   { width: 0%; margin-left: 0; }
                70%  { width: 100%; margin-left: 0; }
                71%  { width: 0%; margin-left: 100%; }
                100% { width: 0%; margin-left: 100%; }
            }
        </style>
    </head>
    <body>

        <!-- HEADER -->
        <div class="ai-header">
            <div class="ai-title">⬡ MÉTRÉ AI — STRUCTURAL SCAN <span class="blink">█</span></div>
            <div class="ai-subtitle">ANALYSE CHARPENTE MÉTALLIQUE &nbsp;·&nbsp; AGENTIC ZONING &nbsp;·&nbsp; v2.5</div>
        </div>

        <!-- PLAN BLUEPRINT -->
        <div class="plan-wrap">
            <!-- Corner brackets -->
            <div class="corner tl"></div>
            <div class="corner tr"></div>
            <div class="corner bl"></div>
            <div class="corner br"></div>

            <!-- Scan beam -->
            <div class="scan-line"></div>
            <div class="scan-glow"></div>

            <svg viewBox="0 0 580 135" width="100%" height="100%">
                <defs>
                    <filter id="glowFilter" x="-30%" y="-30%" width="160%" height="160%">
                        <feGaussianBlur stdDeviation="2.5" result="blur"/>
                        <feMerge>
                            <feMergeNode in="blur"/>
                            <feMergeNode in="SourceGraphic"/>
                        </feMerge>
                    </filter>
                </defs>

                <!-- LONGITUDINAL MAIN BEAMS (horizontal) -->
                <line class="main-beam" x1="45" y1="30"  x2="535" y2="30"/>
                <line class="main-beam" x1="45" y1="105" x2="535" y2="105"/>
                <!-- MIDDLE PURLIN LINE -->
                <line class="sec-beam"  x1="45" y1="67"  x2="535" y2="67"/>

                <!-- TRANSVERSE FRAMES (vertical — 6 bays) -->
                <line class="main-beam" x1="45"  y1="25" x2="45"  y2="110"/>
                <line class="sec-beam"  x1="127" y1="25" x2="127" y2="110"/>
                <line class="sec-beam"  x1="209" y1="25" x2="209" y2="110"/>
                <line class="sec-beam"  x1="291" y1="25" x2="291" y2="110"/>
                <line class="sec-beam"  x1="373" y1="25" x2="373" y2="110"/>
                <line class="sec-beam"  x1="455" y1="25" x2="455" y2="110"/>
                <line class="main-beam" x1="535" y1="25" x2="535" y2="110"/>

                <!-- CORNER X BRACING (CVT) — bay 1 -->
                <line class="brace-line" x1="45"  y1="30"  x2="127" y2="105"/>
                <line class="brace-line" x1="45"  y1="105" x2="127" y2="30"/>
                <!-- CVT — bay 6 -->
                <line class="brace-line" x1="455" y1="30"  x2="535" y2="105"/>
                <line class="brace-line" x1="455" y1="105" x2="535" y2="30"/>

                <!-- COLUMN DOTS — corners (filled) -->
                <circle class="col-dot" cx="45"  cy="30"  r="4"/>
                <circle class="col-dot" cx="45"  cy="105" r="4"/>
                <circle class="col-dot" cx="535" cy="30"  r="4"/>
                <circle class="col-dot" cx="535" cy="105" r="4"/>

                <!-- COLUMN DOTS — interior (outline) -->
                <circle class="col-dot-sm" cx="127" cy="30"  r="3"/>
                <circle class="col-dot-sm" cx="127" cy="105" r="3"/>
                <circle class="col-dot-sm" cx="209" cy="30"  r="3"/>
                <circle class="col-dot-sm" cx="209" cy="105" r="3"/>
                <circle class="col-dot-sm" cx="291" cy="30"  r="3"/>
                <circle class="col-dot-sm" cx="291" cy="105" r="3"/>
                <circle class="col-dot-sm" cx="373" cy="30"  r="3"/>
                <circle class="col-dot-sm" cx="373" cy="105" r="3"/>
                <circle class="col-dot-sm" cx="455" cy="30"  r="3"/>
                <circle class="col-dot-sm" cx="455" cy="105" r="3"/>

                <!-- DIMENSION ANNOTATIONS -->
                <text class="dim-text" x="86"  y="19" text-anchor="middle">6000</text>
                <text class="dim-text" x="168" y="19" text-anchor="middle">6000</text>
                <text class="dim-text" x="250" y="19" text-anchor="middle">6000</text>
                <text class="dim-text" x="332" y="19" text-anchor="middle">6000</text>
                <text class="dim-text" x="414" y="19" text-anchor="middle">6000</text>
                <text class="dim-text" x="495" y="19" text-anchor="middle">6000</text>

                <!-- BAY WIDTH ON LEFT -->
                <text class="dim-text" x="28" y="72" text-anchor="middle">18m</text>

                <!-- SCALE + NORTH -->
                <text class="dim-text" x="290" y="128" text-anchor="middle">PLAN CHARPENTE — ÉCHELLE 1:100</text>
                <text x="555" y="72" fill="rgba(0,212,255,0.25)" font-size="9" font-family="Courier New" text-anchor="middle">N↑</text>
            </svg>
        </div>

        <!-- STATUS MESSAGES -->
        <div class="status-wrap">
            <div class="msg">
                <div class="msg-title">◈ INITIALISATION DU SCAN ◈</div>
                <div class="msg-sub">Lecture de la géométrie 2D · Détection des vues</div>
            </div>
            <div class="msg">
                <div class="msg-title">◈ EXTRACTION ACTIVE ◈</div>
                <div class="msg-sub">Analyse des Poteaux · Traverses · Pannes · CVT</div>
            </div>
            <div class="msg">
                <div class="msg-title">◈ CARTOGRAPHIE DES ACCESSOIRES ◈</div>
                <div class="msg-sub">Platines · Goussets · Tiges d'ancrage</div>
            </div>
            <div class="msg">
                <div class="msg-title">◈ CALCULS EN COURS ◈</div>
                <div class="msg-sub">Poids · Quantités · Nomenclature finale</div>
            </div>
        </div>

        <!-- PROGRESS BAR -->
        <div class="prog-wrap">
            <span class="prog-label">SCAN</span>
            <div class="prog-bar">
                <div class="prog-fill"></div>
            </div>
            <span class="prog-label">AI</span>
        </div>

    </body>
    </html>
    """
