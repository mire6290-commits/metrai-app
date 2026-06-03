import React, { useState, useRef } from 'react';
import { UploadCloud, FileType, CheckCircle, RotateCcw, AlertTriangle, ArrowRight, Download, BarChart2 } from 'lucide-react';
import './index.css';

// Base de données locale de poids linéiques et de surfaces pour recalculs instantanés côté client
const PROFILES_DB = {
  "IPE100": [8.1, 0.40], "IPE120": [10.4, 0.47], "IPE140": [12.9, 0.55], "IPE160": [15.8, 0.62],
  "IPE180": [18.8, 0.70], "IPE200": [22.4, 0.77], "IPE220": [26.2, 0.85], "IPE240": [30.7, 0.92],
  "IPE270": [36.1, 1.04], "IPE300": [42.2, 1.16], "IPE330": [49.1, 1.25], "IPE360": [57.1, 1.35],
  "IPE400": [66.3, 1.47], "IPE450": [77.6, 1.66],
  "HEA100": [16.7, 0.56], "HEA120": [19.9, 0.68], "HEA140": [24.7, 0.80], "HEA160": [30.4, 0.92],
  "HEA180": [35.5, 1.04], "HEA200": [42.3, 1.15], "HEA220": [50.5, 1.26], "HEA240": [60.3, 1.37],
  "HEA300": [88.3, 1.73],
  "HEB100": [20.4, 0.57], "HEB120": [26.7, 0.69], "HEB140": [33.7, 0.81], "HEB160": [42.6, 0.93],
  "HEB180": [51.2, 1.05], "HEB200": [61.3, 1.17], "HEB220": [71.5, 1.28], "HEB240": [83.2, 1.40],
  "UPN80": [8.64, 0.31], "UPN100": [10.6, 0.37], "UPN120": [13.4, 0.44], "UPN140": [16.0, 0.50], 
  "UPN160": [18.8, 0.57], "UPN200": [25.2, 0.70],
  "L70X70X7": [7.38, 0.28], "L70X7": [7.38, 0.28],
  "L50X50X5": [3.77, 0.20], "L50X5": [3.77, 0.20],
  "ROND24": [3.55, 0.08], "RONDPLEINØ14": [1.20, 0.04], "RONDPLEINØ24": [3.55, 0.08],
  "D14": [1.20, 0.04],
  "TUBEC40X40X2": [2.31, 0.16], "TUBECARRE40X2": [2.31, 0.16], "TUBECARRE40X40X2": [2.31, 0.16],
  "JARRETIPE400": [66.3, 1.47], "JARRETSIPE400": [66.3, 1.47],
  "JARRETIPE270": [36.1, 1.04], "JARRETSIPE270": [36.1, 1.04],
  "JARRETIPE450": [77.6, 1.66], "JARRETSIPE450": [77.6, 1.66]
};

const API_BASE_URL = "https://amira221-metrai-backend.hf.space";

function App() {
  const [file, setFile] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processStep, setProcessStep] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (selectedFile.type !== "application/pdf") {
        setError("Veuillez sélectionner un fichier PDF valide.");
        return;
      }
      setFile(selectedFile);
      setError(null);
    }
  };

  const handleUploadAndProcess = async (e) => {
    e.preventDefault();
    if (!file) return;

    setIsProcessing(true);
    setError(null);
    
    try {
      setProcessStep("Lecture OCR et application des règles métier de charpente...");
      const formData = new FormData();
      formData.append('file', file);
      formData.append('mode', 'vision');
      
      // 2) Appel à l'API asynchrone (bypasses timeouts)
      const extractRes = await fetch(`${API_BASE_URL}/extract_async`, {
        method: 'POST',
        headers: {
          'Bypass-Tunnel-Reminder': 'true'
        },
        body: formData,
      });

      if (!extractRes.ok) {
        const errData = await extractRes.json().catch(() => ({}));
        throw new Error(errData.detail || `Erreur serveur: ${extractRes.statusText}`);
      }

      const { task_id } = await extractRes.json();
      
      let extractData = null;
      while (true) {
        await new Promise(r => setTimeout(r, 3000));
        const statusRes = await fetch(`${API_BASE_URL}/extract_status/${task_id}`, {
            headers: { 'Bypass-Tunnel-Reminder': 'true' }
        });
        if (!statusRes.ok) {
            const errData = await statusRes.json().catch(() => ({}));
            throw new Error(errData.detail || 'Erreur lors du polling');
        }
        const statusData = await statusRes.json();
        if (statusData.status === 'done') {
            extractData = statusData.result;
            break;
        } else if (statusData.status === 'error') {
            throw new Error(statusData.detail || 'Erreur inconnue');
        }
      }

      const mappedData = extractData.profiles.map((p, idx) => {
        const profil = p.designation || "";
        const profilKey = profil.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, "").toUpperCase();
        
        let poidsLineique = 0;
        let surfaceLineique = 0;
        let poidsUnitaire = 0;
        const longueurMM = p.length_m ? Math.round(p.length_m * 1000) : 0;
        const quantite = p.quantity || 0;
        
        if (PROFILES_DB[profilKey]) {
            [poidsLineique, surfaceLineique] = PROFILES_DB[profilKey];
            poidsUnitaire = (longueurMM / 1000.0) * poidsLineique;
        } else if (profilKey.startsWith('TN') || profilKey.startsWith('PL')) {
            const dims3 = profilKey.match(/(\d+)[\*X](\d+)[\*X](\d+)/i);
            const dims2 = profilKey.match(/(\d+)[\*X](\d+)/i);
            if (dims3) {
                const a = parseInt(dims3[1]);
                const b = parseInt(dims3[2]);
                const epaisseur = parseInt(dims3[3]);
                poidsUnitaire = (a * b * epaisseur) / 1000000000.0 * 8000;
            } else if (dims2) {
                const a = parseInt(dims2[1]);
                const epaisseur = parseInt(dims2[2]);
                poidsUnitaire = (a * epaisseur * longueurMM) / 1000000000.0 * 8000;
            }
        }
        
        const poidsTotal = poidsUnitaire * quantite;
        
        return {
          id: p.id || idx.toString(),
          repere: p.id || "",
          profil: profil,
          longueur: longueurMM || "",
          quantite: quantite,
          poids_lineique: poidsLineique || "---",
          poids_unitaire: Number(poidsUnitaire.toFixed(3)),
          poids_total: Number(poidsTotal.toFixed(3)),
          surface_total: (longueurMM / 1000.0) * surfaceLineique * quantite,
          assemblage: p.role || "",
        };
      });
      setData(mappedData);
    } catch (err) {
      console.error(err);
      setError(err.message || "Une erreur est survenue lors du traitement du plan.");
    } finally {
      setIsProcessing(false);
      setProcessStep("");
    }
  };

  const handleDataChange = (id, field, value) => {
    setData(data.map(item => {
      if (item.id === id) {
        const updatedItem = { ...item, [field]: value };
        
        // Recalcul instantané du poids et de la surface de peinture si modification des dimensions
        if (field === 'profil' || field === 'longueur' || field === 'quantite') {
          const profilKey = updatedItem.profil.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, "").toUpperCase();
          const longueur = parseFloat(updatedItem.longueur) || 0;
          const quantite = parseInt(updatedItem.quantite) || 0;
          
          let poidsLineique = 0;
          let surfaceLineique = 0;
          let poidsUnitaire = 0;
          
          if (PROFILES_DB[profilKey]) {
            [poidsLineique, surfaceLineique] = PROFILES_DB[profilKey];
            poidsUnitaire = (longueur / 1000.0) * poidsLineique;
          } else if (profilKey.startsWith('TN') || profilKey.startsWith('PL')) {
            const dims3 = profilKey.match(/(\d+)[\*X](\d+)[\*X](\d+)/i);
            const dims2 = profilKey.match(/(\d+)[\*X](\d+)/i);
            if (dims3) {
                const a = parseInt(dims3[1]);
                const b = parseInt(dims3[2]);
                const epaisseur = parseInt(dims3[3]);
                poidsUnitaire = (a * b * epaisseur) / 1000000000.0 * 8000;
            } else if (dims2) {
                const a = parseInt(dims2[1]);
                const epaisseur = parseInt(dims2[2]);
                poidsUnitaire = (a * epaisseur * longueur) / 1000000000.0 * 8000;
            }
          }
          
          updatedItem.poids_lineique = poidsLineique || "---";
          updatedItem.poids_unitaire = Number(poidsUnitaire.toFixed(3));
          updatedItem.poids_total = Number((poidsUnitaire * quantite).toFixed(3));
          
          updatedItem.surface_lineique = surfaceLineique || 0;
          updatedItem.surface_unitaire = (longueur / 1000.0) * (surfaceLineique || 0);
          updatedItem.surface_total = updatedItem.surface_unitaire * quantite;
        }
        
        return updatedItem;
      }
      return item;
    }));
  };

  const handleExport = async (format) => {
    if (format !== 'excel') {
      alert("L'export " + format.toUpperCase() + " sera disponible prochainement !");
      return;
    }
    
    try {
      const res = await fetch(`${API_BASE_URL}/export/${format}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Bypass-Tunnel-Reminder': 'true'
        },
        body: JSON.stringify({ data: data }),
      });

      if (!res.ok) {
        throw new Error("L'exportation a échoué.");
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = "metrai_quantites.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert("Erreur lors de l'exportation : " + err.message);
    }
  };

  const handleReset = () => {
    setFile(null);
    setData(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Calcul des statistiques globales pour le tableau de bord
  const totalWeight = data ? data.reduce((acc, curr) => acc + (curr.poids_total || 0), 0) : 0;
  const totalPaintSurface = data ? data.reduce((acc, curr) => acc + (curr.surface_total || 0), 0) : 0;
  const totalQuantity = data ? data.reduce((acc, curr) => acc + (curr.quantite || 0), 0) : 0;

  const groupedData = data ? data.reduce((acc, item) => {
    const role = (item.assemblage || 'AUTRES').toUpperCase();
    if (!acc[role]) acc[role] = [];
    acc[role].push(item);
    return acc;
  }, {}) : {};
  const sortedRoles = Object.keys(groupedData).sort();

  return (
    <div style={{ padding: '40px 20px', maxWidth: '1280px', margin: '0 auto' }}>
      <header style={{ marginBottom: '40px', textAlign: 'center' }}>
        <h1 style={{ fontSize: '2.8rem', fontWeight: '800', marginBottom: '10px', background: 'linear-gradient(to right, #3b82f6, #10b981)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          SaaS Métré Charpente
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem' }}>
          Extraction intelligente et automatique depuis vos plans PDF (Architecte, Charpente, Fabrication)
        </p>
      </header>

      {error && (
        <div className="glass-panel animate-fade-in" style={{ borderColor: '#ef4444', background: 'rgba(239, 68, 68, 0.05)', display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
          <AlertTriangle color="#ef4444" size={24} />
          <div>
            <h4 style={{ color: '#ef4444', fontWeight: '600' }}>Une erreur est survenue</h4>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>{error}</p>
          </div>
        </div>
      )}

      {/* Étape 1 : Zone d'Upload */}
      {!data && !isProcessing && (
        <div className="glass-panel animate-fade-in" style={{ textAlign: 'center', padding: '60px 40px', maxWidth: '640px', margin: '0 auto' }}>
          <div className="dropzone-container" onClick={() => fileInputRef.current.click()}>
            <UploadCloud size={64} color="var(--primary-color)" style={{ margin: '0 auto 20px auto' }} />
            <h2 style={{ marginBottom: '12px', fontSize: '1.5rem', fontWeight: '700' }}>Téléverser votre plan PDF</h2>
            <p style={{ color: 'var(--text-muted)', marginBottom: '8px' }}>
              Glissez-déposez un fichier ici ou cliquez pour parcourir
            </p>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              Fichiers acceptés : PDF de charpente métallique, d'assemblage ou de fabrication
            </p>
            <input 
              type="file" 
              ref={fileInputRef}
              onChange={handleFileChange}
              style={{ display: 'none' }}
              accept=".pdf"
            />
          </div>
          
          {file && (
            <div style={{ marginTop: '24px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px' }}>
              <FileType color="var(--primary-color)" size={20} />
              <span style={{ fontWeight: '500' }}>{file.name}</span>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>({(file.size / 1024 / 1024).toFixed(2)} Mo)</span>
            </div>
          )}

          {file && (
            <button className="btn-primary" onClick={handleUploadAndProcess} style={{ marginTop: '32px', width: '100%', justifyContent: 'center' }}>
              Lancer l'analyse <ArrowRight size={18} />
            </button>
          )}
        </div>
      )}

      {/* Étape de chargement/traitement */}
      {isProcessing && (
        <div className="glass-panel animate-fade-in" style={{ textAlign: 'center', padding: '80px 20px', maxWidth: '500px', margin: '0 auto' }}>
          <div className="spinner" style={{ margin: '0 auto 24px auto' }}></div>
          <h3 style={{ marginBottom: '12px', fontWeight: '700' }}>Analyse du plan en cours...</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>{processStep}</p>
        </div>
      )}

      {/* Étape 2 : Visualisation et Export des Données */}
      {data && (
        <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
          {/* Tableau de Bord Rapide */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
            <div className="glass-panel" style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
              <div style={{ padding: '16px', background: 'rgba(59, 130, 246, 0.1)', borderRadius: '12px' }}>
                <BarChart2 size={32} color="var(--primary-color)" />
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textTransform: 'uppercase' }}>Poids Total Théorique</span>
                <h3 style={{ fontSize: '1.8rem', fontWeight: '800', color: 'var(--primary-color)' }}>{totalWeight.toFixed(2)} kg</h3>
              </div>
            </div>

            <div className="glass-panel" style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
              <div style={{ padding: '16px', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '12px' }}>
                <CheckCircle size={32} color="var(--success)" />
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textTransform: 'uppercase' }}>Surface de Peinture</span>
                <h3 style={{ fontSize: '1.8rem', fontWeight: '800', color: 'var(--success)' }}>{totalPaintSurface.toFixed(2)} m²</h3>
              </div>
            </div>

            <div className="glass-panel" style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
              <div style={{ padding: '16px', background: 'rgba(139, 92, 246, 0.1)', borderRadius: '12px' }}>
                <FileType size={32} color="#a78bfa" />
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textTransform: 'uppercase' }}>Nombre d'éléments</span>
                <h3 style={{ fontSize: '1.8rem', fontWeight: '800', color: '#a78bfa' }}>{totalQuantity} pcs</h3>
              </div>
            </div>
          </div>

          {/* Tableau de métré interactif */}
          <div className="glass-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '20px', marginBottom: '24px' }}>
              <div>
                <h2 style={{ fontSize: '1.4rem', fontWeight: '700' }}>Quantitatifs et éléments extraits</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Vous pouvez éditer les valeurs directement dans le tableau pour ajuster le métré.</p>
              </div>
              
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                <button className="btn-secondary" onClick={handleReset}>
                  <RotateCcw size={16} /> Nouveau Plan
                </button>
                <button className="btn-secondary" onClick={() => handleExport('csv')}>
                  Exporter CSV
                </button>
                <button className="btn-secondary" onClick={() => handleExport('pdf')}>
                  Exporter PDF
                </button>
                <button className="btn-primary" onClick={() => handleExport('excel')} style={{ background: 'var(--success)' }}>
                  <Download size={16} /> Télécharger l'Excel
                </button>
              </div>
            </div>
            
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Pos</th>
                    <th>Nomenclatures</th>
                    <th>Quantité</th>
                    <th>Designation</th>
                    <th>Long (mm)</th>
                    <th>Poids Kg/(m)</th>
                    <th>Poids Kg/Unt</th>
                    <th>Poids Tot Kg</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRoles.map(role => (
                    <React.Fragment key={role}>
                      <tr>
                        <td colSpan="8" style={{ background: 'var(--primary-color)', color: 'white', fontWeight: '700', textAlign: 'center', padding: '12px' }}>
                          {role}
                        </td>
                      </tr>
                      {groupedData[role].map((item, index) => (
                        <tr key={item.id}>
                          <td style={{ width: '8%', textAlign: 'center', fontWeight: '600' }}>
                            {item.repere || (index + 1)}
                          </td>
                          <td style={{ width: '15%' }}>
                            <span className="badge badge-blue">
                              {item.assemblage}
                            </span>
                          </td>
                          <td style={{ width: '10%' }}>
                            <input 
                              className="editable-cell" 
                              type="number"
                              value={item.quantite}
                              onChange={(e) => handleDataChange(item.id, 'quantite', e.target.value)}
                            />
                          </td>
                          <td style={{ width: '15%' }}>
                            <input 
                              className="editable-cell" 
                              value={item.profil}
                              onChange={(e) => handleDataChange(item.id, 'profil', e.target.value)}
                            />
                          </td>
                          <td style={{ width: '12%' }}>
                            <input 
                              className="editable-cell" 
                              type="number"
                              value={item.longueur}
                              onChange={(e) => handleDataChange(item.id, 'longueur', e.target.value)}
                            />
                          </td>
                          <td style={{ fontWeight: '500', color: 'var(--text-muted)' }}>
                            {item.poids_lineique !== "---" ? Number(item.poids_lineique).toFixed(2) : "---"}
                          </td>
                          <td style={{ fontWeight: '500', color: 'var(--text-muted)' }}>
                            {item.poids_unitaire ? item.poids_unitaire.toFixed(2) : "0.00"}
                          </td>
                          <td style={{ fontWeight: '700', color: 'var(--primary-color)' }}>
                            {item.poids_total ? item.poids_total.toFixed(2) : "0.00"}
                          </td>
                        </tr>
                      ))}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
