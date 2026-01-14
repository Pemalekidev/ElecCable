import streamlit as st
import pandas as pd
from fpdf import FPDF
import datetime
import matplotlib.pyplot as plt
import tempfile
import os

# --- 1. CONFIGURATION DE LA PAGE & DESIGN ---
st.set_page_config(
    page_title="ElecCable Pro | NF C 15-100",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Personnalisé pour un look "App Pro"
st.markdown("""
    <style>
    /* Structure globale */
    .stApp {
        background-color: #0e1117;
        color: #f0f2f6;
    }
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    /* Métriques (KPIs) */
    [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #00d4ff; /* Cyan Néon */
    }
    [data-testid="stMetricLabel"] {
        color: #b0b8c4;
    }
    /* Onglets */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #161b22;
        border-radius: 4px 4px 0px 0px;
        color: white;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #238636; /* Vert GitHub */
        color: white;
    }
    /* Boutons */
    .stButton>button {
        border-radius: 8px;
        font-weight: bold;
        background-color: #238636;
        color: white;
        border: none;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #2ea043;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. DONNÉES TECHNIQUES (NF C 15-100) ---
IZ_REF_TABLE = {
    1.5: 20, 2.5: 29, 4: 39, 6: 50, 10: 71, 
    16: 94, 25: 124, 35: 154, 50: 187, 70: 236, 
    95: 292, 120: 344, 150: 391, 185: 448, 240: 528
}

K_POSE = {
    "C - Enterré": 0.8, 
    "B - Sous conduit apparent": 0.9, 
    "E - Chemin de câble/Air libre": 1.0, 
    "F - Contact maçonnerie": 0.95
}

TEMP_COEFF = {25: 1.06, 30: 1.0, 35: 0.94, 40: 0.87, 45: 0.79, 50: 0.71}

# --- 3. LOGIQUE MÉTIER ---
class CableCalculator:
    def __init__(self, phase, ib, longueur, matiere, pose, temp, limite_du):
        self.phase = phase
        self.ib = ib
        self.longueur = longueur
        self.rho = 0.0225 if matiere == "Cuivre" else 0.036
        self.k_total = K_POSE[pose] * TEMP_COEFF[temp]
        self.limite_du = limite_du
        self.tension = 400 if phase == "Triphasé" else 230
        self.b_factor = 1 if phase == "Triphasé" else 2

    def calculer_dataset(self) -> pd.DataFrame:
        donnees = []
        for s in sorted(IZ_REF_TABLE.keys()):
            iz_reel = IZ_REF_TABLE[s] * self.k_total
            resistance = (self.rho * self.longueur) / s
            chute_p = ((self.b_factor * resistance * self.ib) / self.tension) * 100
            
            # Critères de validation
            valid_iz = iz_reel >= self.ib
            valid_du = chute_p <= self.limite_du
            is_valid = valid_iz and valid_du
            
            donnees.append({
                "Section": s, 
                "Iz_Reel": iz_reel, 
                "dU_Percent": chute_p,
                "Valide": is_valid
            })
        return pd.DataFrame(donnees)

    def obtenir_meilleure_section(self, df: pd.DataFrame):
        filtre = df[df['Valide'] == True]
        if not filtre.empty:
            return filtre.iloc[0]
        return None

# --- 4. GRAPHIQUES (Matplotlib) ---
def create_charts(df, user_ib, limit_du, best_section):
    # Utilisation d'un style sombre compatible avec le thème
    plt.style.use('dark_background')
    
    # FIG 1: Chute de Tension
    fig1, ax1 = plt.subplots(figsize=(7, 4))
    # Fond légèrement plus clair que le noir pur
    fig1.patch.set_facecolor('#0e1117')
    ax1.set_facecolor('#161b22')
    
    ax1.plot(df['Section'], df['dU_Percent'], color='#ff4b4b', linewidth=2, label='Chute de Tension (%)')
    ax1.axhline(y=limit_du, color='white', linestyle='--', alpha=0.5, label=f'Limite {limit_du}%')
    
    if best_section is not None:
        ax1.scatter([best_section['Section']], [best_section['dU_Percent']], color='#00d4ff', s=150, zorder=5, edgecolors='white', label="Solution")
    
    ax1.set_title("Chute de Tension vs Section", color='white', fontweight='bold')
    ax1.set_xlabel("Section (mm²)", color='white')
    ax1.set_ylabel("dU (%)", color='white')
    ax1.grid(color='gray', linestyle=':', alpha=0.3)
    ax1.legend(facecolor='#161b22', edgecolor='white')
    
    # FIG 2: Courant Admissible
    fig2, ax2 = plt.subplots(figsize=(7, 4))
    fig2.patch.set_facecolor('#0e1117')
    ax2.set_facecolor('#161b22')
    
    ax2.plot(df['Section'], df['Iz_Reel'], color='#238636', linewidth=2, label='Iz Câble (A)')
    ax2.axhline(y=user_ib, color='white', linestyle='--', alpha=0.5, label=f'Ib requis {user_ib}A')
    
    if best_section is not None:
         ax2.scatter([best_section['Section']], [best_section['Iz_Reel']], color='#00d4ff', s=150, zorder=5, edgecolors='white', label="Solution")

    ax2.set_title("Courant Admissible (Iz) vs Section", color='white', fontweight='bold')
    ax2.set_xlabel("Section (mm²)", color='white')
    ax2.set_ylabel("Ampères (A)", color='white')
    ax2.grid(color='gray', linestyle=':', alpha=0.3)
    ax2.legend(facecolor='#161b22', edgecolor='white')

    return fig1, fig2

# --- 5. GÉNÉRATEUR PDF (CORRIGÉ & STYLISÉ) ---
class PDFReport(FPDF):
    def header(self):
        # Bandeau Bleu Foncé Professionnel
        self.set_fill_color(22, 33, 62) 
        self.rect(0, 0, 210, 40, 'F')
        
        # Titre
        self.set_y(12)
        self.set_font('Arial', 'B', 22)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, 'NOTE DE CALCUL ELECTRIQUE', 0, 1, 'C')
        
        # Sous-titre
        self.set_font('Arial', '', 10)
        self.set_text_color(200, 200, 200)
        self.cell(0, 8, f'Date : {datetime.date.today()} | Projet : Dimensionnement BT', 0, 1, 'C')
        self.ln(25)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, 'ElecCable Pro - Généré automatiquement', 0, 0, 'C')

    def chapter_title(self, label):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(230, 230, 230)
        self.set_text_color(22, 33, 62)
        self.cell(0, 8, f"  {label}", 0, 1, 'L', True)
        self.ln(4)

def generate_pdf(params, res_data, fig1, fig2):
    """Génère le PDF en utilisant des fichiers temporaires pour les images (Fix Windows)."""
    pdf = PDFReport()
    pdf.add_page()
    
    # 1. Hypothèses
    pdf.chapter_title("1. HYPOTHESES DU PROJET")
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(0, 0, 0)
    
    # Tableau des paramètres (2 colonnes)
    col_width = 95
    line_height = 7
    fill = False
    pdf.set_fill_color(245, 245, 245)
    
    for k, v in params.items():
        pdf.cell(col_width, line_height, f"  {k} : {v}", border=0, fill=fill)
        if pdf.get_x() > 180:
            pdf.ln()
            fill = not fill # Effet zébré
            
    pdf.ln(10)

    # 2. Résultats
    pdf.chapter_title("2. RESULTATS DU CALCUL")
    
    if res_data is not None:
        # Cadre de résultat
        pdf.set_fill_color(220, 255, 220) # Vert clair
        pdf.set_draw_color(34, 139, 34)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 15, f"  SECTION RETENUE : {res_data['Section']} mm2", 1, 1, 'C', True)
        pdf.ln(8)
        
        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 8, f"  -> Chute de tension : {res_data['dU_Percent']:.2f} % (Max : {params['Limite dU']})", 0, 1)
        pdf.cell(0, 8, f"  -> Courant Admissible (Iz) : {res_data['Iz_Reel']:.1f} A (Ib : {params['Courant Ib']})", 0, 1)
        pdf.cell(0, 8, f"  -> Conformité : OUI", 0, 1)
    else:
        pdf.set_text_color(200, 0, 0)
        pdf.cell(0, 10, "  AUCUNE SECTION STANDARD NE CONVIENT", 1, 1)

    pdf.ln(5)

    # 3. Graphiques
    pdf.chapter_title("3. ANALYSE GRAPHIQUE")
    pdf.ln(2)

    # --- CORRECTION DU BUG R-FIND ICI ---
    # On sauvegarde les graphs Matplotlib dans des fichiers temporaires physiques
    # car FPDF (v1.7.2) n'aime pas BytesIO sur Windows
    
    # Changement temporaire du style pour le PDF (fond blanc)
    current_style = plt.style.context('default') 
    with current_style:
        # On recrée des figures simples pour le PDF (fond blanc, texte noir) pour impression propre
        # Note: Dans un cas réel, on pourrait refaire les plot. Ici, on utilise les figs existantes
        # mais on force le fond blanc lors du savefig.
        pass

    def save_temp_image(figure):
        try:
            # delete=False est obligatoire pour que FPDF puisse relire le fichier après sa création sur Windows
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            # force le fond blanc pour le PDF
            figure.savefig(tmp.name, format='png', dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
            tmp.close()
            return tmp.name
        except Exception as e:
            st.error(f"Erreur image: {e}")
            return None

    path1 = save_temp_image(fig1)
    path2 = save_temp_image(fig2)

    if path1:
        pdf.image(path1, x=15, w=180)
        pdf.ln(5)
    if path2:
        pdf.image(path2, x=15, w=180)

    # Nettoyage des fichiers temporaires
    try:
        if path1: os.remove(path1)
        if path2: os.remove(path2)
    except:
        pass

    return pdf.output(dest='S').encode('latin-1')


# --- 6. INTERFACE UTILISATEUR (MAIN) ---
def main():
    
    # --- Sidebar ---
    with st.sidebar:
        st.header("⚙️ Paramètres")
        st.write("---")
        
        # Inputs
        p_phase = st.selectbox("Réseau", ["Monophasé (230V)", "Triphasé (400V)"])
        phase_str = "Triphasé" if "Triphasé" in p_phase else "Monophasé"
        
        _, c2 = st.columns([2, 1])
        with st.sidebar:
            p_mat = st.radio("Métal", ["Cuivre", "Aluminium"], horizontal=True)
        with c2:
            st.write("") # Spacer
            
        p_ib = st.number_input("Courant d'emploi Ib (A)", 1.0, 1000.0, 32.0, 1.0)
        p_long = st.number_input("Longueur câble (m)", 1, 2000, 50, 5)
        
        st.write("---")
        st.subheader("Environnement")
        p_pose = st.selectbox("Mode de Pose", list(K_POSE.keys()))
        p_temp = st.select_slider("Température (°C)", list(TEMP_COEFF.keys()), value=30)
        p_lim = st.slider("Chute tension max (%)", 1.0, 10.0, 3.0, 0.5)
        
        st.caption("v1.0 | By Petema Maleki")

    # --- Titre Principal ---
    st.title("⚡ ElecCable Pro")
    st.markdown("##### Outil de dimensionnement électrique conforme NF C 15-100")
    st.write("") # Spacer

    # --- Calculs en Temps Réel ---
    calc = CableCalculator(phase_str, p_ib, p_long, p_mat, p_pose, p_temp, p_lim)
    df_res = calc.calculer_dataset()
    solution = calc.obtenir_meilleure_section(df_res)
    
    # Création des graphes en mémoire
    fig_du, fig_iz = create_charts(df_res, p_ib, p_lim, solution)

    # --- Gestion des Onglets ---
    tab_calc, tab_doc = st.tabs(["📊 Calculateur & Résultats", "📘 Documentation Technique"])

    # --- ONGLET 1 : RÉSULTATS ---
    with tab_calc:
        if solution is not None:
            # 1. KPIs
            st.success(f"✅ Section Recommandée : **{solution['Section']} mm²**")
            
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("Section", f"{solution['Section']} mm²")
            kpi2.metric("Chute de Tension", f"{solution['dU_Percent']:.2f} %", f"Limite {p_lim}%", delta_color="inverse")
            kpi3.metric("Iz (Admissible)", f"{solution['Iz_Reel']:.1f} A", f"Marge {solution['Iz_Reel']-p_ib:.1f} A")
            kpi4.metric("Résistance", f"{(calc.rho * p_long / solution['Section']):.3f} Ω")
            
            st.markdown("---")
            
            # 2. Graphes
            st.subheader("📈 Analyse Visuelle")
            g1, g2 = st.columns(2)
            with g1:
                st.pyplot(fig_du)
            with g2:
                st.pyplot(fig_iz)
                
            # 3. Export PDF
            st.markdown("---")
            st.subheader("📥 Exportation")
            
            # Préparation données PDF
            params_pdf = {
                "Réseau": phase_str, "Matériau": p_mat, "Courant Ib": f"{p_ib} A",
                "Longueur": f"{p_long} m", "Pose": p_pose, "Température": f"{p_temp} °C",
                "Limite dU": f"{p_lim} %"
            }
            
            # Bouton de génération
            if st.button("Générer la Note de Calcul PDF"):
                with st.spinner("Génération du rapport en cours..."):
                    pdf_bytes = generate_pdf(params_pdf, solution, fig_du, fig_iz)
                    
                    st.download_button(
                        label="📄 Télécharger le Rapport Final",
                        data=pdf_bytes,
                        file_name=f"Note_Calcul_{int(p_ib)}A_{p_long}m.pdf",
                        mime="application/pdf"
                    )
            
            # 4. Détails Tableau
            with st.expander("Voir le tableau de données brut"):
                st.dataframe(df_res.style.applymap(
                    lambda x: 'color: #4ade80' if x else 'color: #f87171', subset=['Valide']
                ).format({"Iz_Reel": "{:.1f}", "dU_Percent": "{:.2f}"}))

        else:
            st.error("❌ Impossible de trouver une section standard satisfaisant les critères.")
            st.warning("Essayez d'augmenter la chute de tension admissible ou de changer de matériau.")

    # --- ONGLET 2 : DOCUMENTATION ---
    with tab_doc:
        st.header("Manuel d'Utilisation & Hypothèses")
        
        st.markdown("""
        ### 1. Objectif
        Cette application permet de déterminer la section de câble minimale requise selon la norme **NF C 15-100**, en prenant en compte :
        1.  La capacité de transport de courant (**Iz**).
        2.  La chute de tension maximale admissible (**dU**).

        ### 2. Formules Utilisées
        
        **A. Calcul de la Résistance :**
        $$ R = \\frac{\\rho \cdot L}{S} $$
        * $\\rho$ : Résistivité (0.0225 Cuivre / 0.036 Alu)
        * $L$ : Longueur (m)
        * $S$ : Section ($mm^2$)

        **B. Chute de Tension :**
        $$ dU(\%) = \\frac{b \cdot R \cdot I_b}{U_{n}} \cdot 100 $$
        * $b$ : 1 pour Triphasé, 2 pour Monophasé
        * $I_b$ : Courant d'emploi
        * $U_{n}$ : Tension nominale (400V ou 230V)

        ### 3. Facteurs de Correction (K)
        Le courant admissible final $I_z$ est calculé comme suit :
        $$ I_z(réel) = I_z(tab) \cdot K_{pose} \cdot K_{temp} $$
        
        * **K_pose** : Dépend de la méthode d'installation (Enterré, Chemin de câble...).
        * **K_temp** : Dépend de la température ambiante (Base 30°C).
        """)
        
        st.info("Note : Ce logiciel est une aide au calcul.")

if __name__ == "__main__":
    main()