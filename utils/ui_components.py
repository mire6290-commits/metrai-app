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
                background-color: #0b0f19;
                /* Blueprint grid background */
                background-image: 
                    linear-gradient(rgba(255, 165, 0, 0.05) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255, 165, 0, 0.05) 1px, transparent 1px),
                    linear-gradient(rgba(255, 165, 0, 0.02) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255, 165, 0, 0.02) 1px, transparent 1px);
                background-size: 100px 100px, 100px 100px, 20px 20px, 20px 20px;
                background-position: -2px -2px, -2px -2px, -1px -1px, -1px -1px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                font-family: 'Courier New', Courier, monospace;
                overflow: hidden;
            }

            .svg-container {
                width: 600px;
                height: 400px;
                position: relative;
            }

            .draw-path {
                fill: none;
                stroke: #FFA500;
                stroke-width: 2.5;
                stroke-linecap: round;
                stroke-linejoin: round;
                filter: url(#glow);
                stroke-dasharray: 1000;
                stroke-dashoffset: 1000;
            }

            /* Animation Phases */
            /* Poteaux (Columns) */
            .poteau {
                animation: draw 1.5s ease-in-out forwards;
            }
            /* Traverses (Rafters) */
            .traverse {
                animation: draw 1.5s ease-in-out forwards;
                animation-delay: 1.5s;
            }
            /* Pannes / Lisses (Connecting elements) */
            .panne {
                stroke-width: 1.5;
                animation: draw 2s ease-in-out forwards;
                animation-delay: 3s;
            }
            /* Diagonales (Bracing) */
            .diagonale {
                stroke-width: 1;
                stroke-dasharray: 10, 5;
                animation: draw-dashed 2s ease-in-out forwards;
                animation-delay: 4.5s;
                opacity: 0.7;
            }

            @keyframes draw {
                to { stroke-dashoffset: 0; }
            }
            
            @keyframes draw-dashed {
                from { stroke-dashoffset: 1000; }
                to { stroke-dashoffset: 0; }
            }

            /* Blinking Status Text */
            .status-container {
                margin-top: 20px;
                text-align: center;
            }

            .status-text {
                color: #FFA500;
                font-size: 1.2rem;
                font-weight: bold;
                text-shadow: 0 0 10px rgba(255, 165, 0, 0.8);
                opacity: 0;
                animation: fadeInOut 2s infinite;
            }
            
            .status-subtext {
                color: #A06500;
                font-size: 0.9rem;
                margin-top: 5px;
                opacity: 0;
                animation: fadeIn 1s forwards;
                animation-delay: 1s;
            }

            @keyframes fadeInOut {
                0% { opacity: 0.3; }
                50% { opacity: 1; text-shadow: 0 0 15px rgba(255, 165, 0, 1); }
                100% { opacity: 0.3; }
            }
            
            @keyframes fadeIn {
                to { opacity: 1; }
            }

            /* Status cycle */
            .msg1, .msg2, .msg3, .msg4 {
                position: absolute;
                width: 100%;
                text-align: center;
                opacity: 0;
            }
            
            .msg1 { animation: showText 3s forwards; }
            .msg2 { animation: showText 4s forwards; animation-delay: 3s; }
            .msg3 { animation: showText 5s forwards; animation-delay: 7s; }
            .msg4 { animation: showText 10s forwards; animation-delay: 12s; }

            @keyframes showText {
                0% { opacity: 0; }
                10% { opacity: 1; }
                90% { opacity: 1; }
                100% { opacity: 0; }
            }

        </style>
    </head>
    <body>
        <div class="svg-container">
            <svg viewBox="0 0 600 400" width="100%" height="100%">
                <defs>
                    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                        <feGaussianBlur stdDeviation="4" result="blur" />
                        <feMerge>
                            <feMergeNode in="blur"/>
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

        <div class="status-container" style="position: relative; width: 100%; height: 50px;">
            <div class="msg1">
                <div class="status-text">INITIALISATION DU SCAN...</div>
                <div class="status-subtext">Lecture de la géométrie 2D</div>
            </div>
            <div class="msg2">
                <div class="status-text">INTELLIGENCE ARTIFICIELLE ACTIVE</div>
                <div class="status-subtext">Extraction des profilés (Poteaux, Traverses...)</div>
            </div>
            <div class="msg3">
                <div class="status-text">CALCULS EN COURS</div>
                <div class="status-subtext">Application des formules d'ingénierie (Poids & Surfaces)</div>
            </div>
            <div class="msg4">
                <div class="status-text">GÉNÉRATION DU NOMENCLATURE...</div>
                <div class="status-subtext">Préparation de la liste de débit</div>
            </div>
        </div>
    </body>
    </html>
    """
