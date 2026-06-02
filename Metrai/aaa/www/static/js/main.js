document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('pdf-upload');
    const startBtn = document.getElementById('start-btn');
    const fileNameDisplay = document.getElementById('file-name');

    // Sections
    const sectionUpload = document.getElementById('upload-section');
    const sectionProcessing = document.getElementById('processing-section');
    const sectionDashboard = document.getElementById('dashboard-section');
    const sectionExports = document.getElementById('exports-section');

    // Steps
    const steps = [
        document.getElementById('step1'),
        document.getElementById('step2'),
        document.getElementById('step3'),
        document.getElementById('step4')
    ];

    let selectedFile = null;
    let extractedData = [];
    let extractedLogo = null;
    let projectName = "PROJET";

    // Drag & Drop Handlers
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#ff5e36';
    });
    dropZone.addEventListener('dragleave', () => {
        dropZone.style.borderColor = 'rgba(237, 125, 49, 0.4)';
    });
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'rgba(237, 125, 49, 0.4)';
        if (e.dataTransfer.files.length) {
            handleFile(e.dataTransfer.files[0]);
        }
    });
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
            handleFile(e.target.files[0]);
        }
    });

    function handleFile(file) {
        if (file.type !== 'application/pdf') {
            alert('Veuillez sélectionner un fichier PDF.');
            return;
        }
        selectedFile = file;
        fileNameDisplay.textContent = file.name;
        startBtn.style.display = 'block';
    }

    function switchSection(index) {
        [sectionUpload, sectionProcessing, sectionDashboard, sectionExports].forEach((sec, i) => {
            sec.style.display = i === index ? 'block' : 'none';
        });
        steps.forEach((step, i) => {
            step.classList.toggle('active', i === index);
        });
    }

    startBtn.addEventListener('click', async () => {
        if (!selectedFile) return;
        
        // Go to processing
        switchSection(1);

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const response = await fetch('/api/extract', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Erreur réseau');
            const data = await response.json();
            extractedData = data.results;
            if (data.logo) extractedLogo = data.logo;
            if (data.project_name) projectName = data.project_name;

            // Compute & Render
            renderDashboard();
            switchSection(2);

        } catch (error) {
            alert('Erreur lors du traitement du fichier: ' + error.message);
            switchSection(0);
        }
    });

    function renderDashboard() {
        let totalWeight = 0;
        let totalPieces = 0;
        let totalSurface = 0;

        const tbody = document.getElementById('table-body');
        tbody.innerHTML = '';

        extractedData.forEach(item => {
            const weight = item.Poids_Unit * item.Longueur * item.Quantité;
            const surface = item.Surface_Unit * item.Longueur * item.Quantité;

            totalWeight += weight;
            totalPieces += item.Quantité;
            totalSurface += surface;

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><b>${item.Profilé}</b></td>
                <td>${item.Quantité}</td>
                <td>${item.Longueur.toFixed(2)}</td>
                <td>${item.Type}</td>
                <td>${item.Localisation}</td>
                <td style="font-weight: bold; color: #ed7d31;">${weight.toFixed(2)}</td>
            `;
            tbody.appendChild(tr);
        });

        document.getElementById('kpi-weight').textContent = totalWeight.toLocaleString('fr-FR', {maximumFractionDigits: 1}) + ' kg';
        document.getElementById('kpi-ton').textContent = (totalWeight / 1000).toLocaleString('fr-FR', {maximumFractionDigits: 3}) + ' T';
        document.getElementById('kpi-surface').textContent = totalSurface.toLocaleString('fr-FR', {maximumFractionDigits: 1}) + ' m²';
        document.getElementById('kpi-pieces').textContent = totalPieces + ' Pcs';
    }

    document.getElementById('back-btn').addEventListener('click', () => {
        switchSection(0);
        selectedFile = null;
        fileNameDisplay.textContent = '';
        startBtn.style.display = 'none';
    });

    document.getElementById('export-btn').addEventListener('click', () => {
        switchSection(3);
    });

    document.getElementById('download-excel-btn').addEventListener('click', async () => {
        try {
            const response = await fetch('/api/export/excel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    data: extractedData,
                    logo_b64: extractedLogo,
                    project_name: projectName
                })
            });

            if (!response.ok) throw new Error('Erreur lors de la génération du fichier Excel');
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = "Metrai_AI_Report.xlsx";
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            alert(error.message);
        }
    });
});
