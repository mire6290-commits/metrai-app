def get_wireframe_animation_html():
    """
    Returns the HTML/CSS/SVG code for the Golden Orange Blueprint Animation.
    """
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <style>
            body {
                background-color: transparent;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                height: 100%;
                margin: 0;
                font-family: 'Courier New', Courier, monospace;
                overflow: hidden;
            }

            .blueprint-bg {
                position: absolute;
                top: 0; left: 0; width: 100%; height: 100%;
                background-image: 
                    linear-gradient(rgba(255, 165, 0, 0.05) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255, 165, 0, 0.05) 1px, transparent 1px),
                    linear-gradient(rgba(255, 165, 0, 0.02) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255, 165, 0, 0.02) 1px, transparent 1px);
                background-size: 100px 100px, 100px 100px, 20px 20px, 20px 20px;
                background-position: -2px -2px, -2px -2px, -1px -1px, -1px -1px;
                z-index: 0;
            }

            .scanner {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 3px;
                background: #FFA500;
                box-shadow: 0 0 10px #FFA500, 0 0 20px #FFA500;
                opacity: 0.5;
                animation: scan 4s linear infinite;
                z-index: 1;
            }

            @keyframes scan {
                0% { top: 0%; opacity: 0; }
                10% { opacity: 0.5; }
                90% { opacity: 0.5; }
                100% { top: 100%; opacity: 0; }
            }

            .svg-container {
                width: 100%;
                height: 160px;
                position: relative;
                z-index: 2;
                display: flex;
                justify-content: center;
            }

            .draw-path {
                fill: none;
                stroke: #FFA500;
                stroke-linecap: round;
                stroke-linejoin: round;
                filter: url(#glow);
                stroke-dasharray: 1000;
                stroke-dashoffset: 1000;
            }

            /* Animation Phases (10s Loop) */
            /* Poteaux (0-1.5s draw, stay until 8s, erase 8-10s) */
            .poteau {
                stroke-width: 2.5;
                animation: drawPoteau 10s infinite;
            }
            @keyframes drawPoteau {
                0% { stroke-dashoffset: 1000; }
                15% { stroke-dashoffset: 0; }
                80% { stroke-dashoffset: 0; }
                100% { stroke-dashoffset: 1000; }
            }

            /* Traverses (1.5s-3s draw, stay until 8s, erase 8-10s) */
            .traverse {
                stroke-width: 2.5;
                animation: drawTraverse 10s infinite;
            }
            @keyframes drawTraverse {
                0% { stroke-dashoffset: 1000; }
                15% { stroke-dashoffset: 1000; }
                30% { stroke-dashoffset: 0; }
                80% { stroke-dashoffset: 0; }
                100% { stroke-dashoffset: 1000; }
            }

            /* Pannes / Lisses (3s-5s draw, stay until 8s, erase 8-10s) */
            .panne {
                stroke-width: 1.5;
                animation: drawPanne 10s infinite;
            }
            @keyframes drawPanne {
                0% { stroke-dashoffset: 1000; }
                30% { stroke-dashoffset: 1000; }
                50% { stroke-dashoffset: 0; }
                80% { stroke-dashoffset: 0; }
                100% { stroke-dashoffset: 1000; }
            }

            /* Diagonales (4.5s-6.5s draw, stay until 8s, erase 8-10s) */
            .diagonale {
                stroke-width: 1;
                stroke-dasharray: 10, 5;
                opacity: 0.7;
                animation: drawDiagonale 10s infinite;
            }
            @keyframes drawDiagonale {
                0% { stroke-dashoffset: 1000; }
                45% { stroke-dashoffset: 1000; }
                65% { stroke-dashoffset: 0; }
                80% { stroke-dashoffset: 0; }
                100% { stroke-dashoffset: 1000; }
            }

            /* Blinking Status Text */
            .status-container {
                margin-top: 10px;
                text-align: center;
                position: relative;
                width: 100%;
                height: 50px;
                z-index: 2;
            }

            .status-text {
                color: #FFA500;
                font-size: 1.1rem;
                font-weight: bold;
                text-shadow: 0 0 8px rgba(255, 165, 0, 0.8);
            }
            
            .status-subtext {
                color: #A06500;
                font-size: 0.85rem;
                margin-top: 2px;
            }

            /* Status cycle */
            .msg1, .msg2, .msg3, .msg4 {
                position: absolute;
                width: 100%;
                text-align: center;
                opacity: 0;
            }
            
            .msg1 { animation: showText1 10s infinite; }
            .msg2 { animation: showText2 10s infinite; }
            .msg3 { animation: showText3 10s infinite; }
            .msg4 { animation: showText4 10s infinite; }

            @keyframes showText1 { 0%{opacity:1;} 20%{opacity:1;} 25%{opacity:0;} 100%{opacity:0;} }
            @keyframes showText2 { 0%{opacity:0;} 25%{opacity:1;} 45%{opacity:1;} 50%{opacity:0;} 100%{opacity:0;} }
            @keyframes showText3 { 0%{opacity:0;} 50%{opacity:1;} 70%{opacity:1;} 75%{opacity:0;} 100%{opacity:0;} }
            @keyframes showText4 { 0%{opacity:0;} 75%{opacity:1;} 95%{opacity:1;} 100%{opacity:0;} }

        </style>
    </head>
    <body>
        <div class="blueprint-bg"></div>
        <div class="scanner"></div>
        <div class="svg-container">
            <svg viewBox="0 0 600 400" width="100%" height="100%">
                <defs>
                    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                        <feGaussianBlur stdDeviation="3" result="blur" />
                        <feMerge>
                            <feMergeNode in="blur"/>
                            <feMergeNode in="SourceGraphic"/>
                        </feMerge>
                    </filter>
                </defs>

                <!-- Back Portique -->
                <path class="draw-path poteau" d="M 250,300 L 250,150" />
                <path class="draw-path poteau" d="M 450,300 L 450,150" />
                <path class="draw-path traverse" d="M 250,150 L 350,80 L 450,150" />
                
                <!-- Front Portique -->
                <path class="draw-path poteau" d="M 100,350 L 100,200" />
                <path class="draw-path poteau" d="M 300,350 L 300,200" />
                <path class="draw-path traverse" d="M 100,200 L 200,130 L 300,200" />

                <!-- Connecting elements (Pannes / Lisses) -->
                <!-- Bottom Lisses -->
                <path class="draw-path panne" d="M 100,350 L 250,300" />
                <path class="draw-path panne" d="M 300,350 L 450,300" />
                <!-- Eaves / Sablières -->
                <path class="draw-path panne" d="M 100,200 L 250,150" />
                <path class="draw-path panne" d="M 300,200 L 450,150" />
                <!-- Faîtière (Ridge) -->
                <path class="draw-path panne" d="M 200,130 L 350,80" />
                
                <!-- Extra Pannes on roof -->
                <path class="draw-path panne" d="M 150,165 L 300,115" />
                <path class="draw-path panne" d="M 250,165 L 400,115" />

                <!-- Croix de St-André (Bracing) on left wall -->
                <path class="draw-path diagonale" d="M 100,350 L 250,150" />
                <path class="draw-path diagonale" d="M 100,200 L 250,300" />
            </svg>
        </div>

        <div class="status-container">
            <div class="msg1">
                <div class="status-text">INITIALISATION DU SCAN...</div>
                <div class="status-subtext">Lecture de la géométrie 2D</div>
            </div>
            <div class="msg2">
                <div class="status-text">EXTRACTION ACTIVE</div>
                <div class="status-subtext">Analyse des Poteaux et Traverses</div>
            </div>
            <div class="msg3">
                <div class="status-text">CARTOGRAPHIE DES PANNES</div>
                <div class="status-subtext">Identification de la structure secondaire</div>
            </div>
            <div class="msg4">
                <div class="status-text">CALCULS EN COURS</div>
                <div class="status-subtext">Application des formules d'ingénierie...</div>
            </div>
        </div>
    </body>
    </html>
    """
