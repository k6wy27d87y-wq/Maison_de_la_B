import streamlit as st
import pandas as pd
from datetime import datetime

# Configuration de la page
st.set_page_config(page_title="StandPro - Librairie", layout="centered")

# --- INITIALISATION DES DONNÉES ---
if 'inventory' not in st.session_state:
    st.session_state.inventory = None
if 'sales' not in st.session_state:
    st.session_state.sales = []
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- INTERFACE ---
st.title("📚 StandPro - Gestion de Stand")

tabs = st.tabs(["⚡ Caisse", "📦 Stock & Catalogue", "📊 Résumé & Export"])

# --- TAB 2: GESTION DU STOCK (A faire en premier) ---
with tabs[1]:
    st.subheader("Importation du stock")
    uploaded_file = st.file_uploader("Charger le fichier Excel de sortie de stock", type=["xlsx", "csv"])
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
        st.write("Aperçu du stock :")
        st.dataframe(df.head())
        st.session_state.inventory = df
        st.success("Catalogue chargé avec succès !")

# --- TAB 1: LA CAISSE ---
with tabs[0]:
    if st.session_state.inventory is None:
        st.warning("Veuillez charger un catalogue dans l'onglet Stock.")
    else:
        # Zone de Scan
        st.subheader("Panier")
        # Sur mobile, ce champ active le scan si une scannette est branchée ou via clavier
        barcode = st.text_input("Scanner un code-barres / Entrer ISBN", key="scanner", placeholder="Scannez ici...")

        if barcode:
            # Recherche dans l'inventaire (on suppose une colonne 'Code' ou 'ISBN')
            book = st.session_state.inventory[st.session_state.inventory.astype(str).values == barcode]
            
            if not book.empty:
                item = {
                    "Titre": book.iloc[0]['Titre'],
                    "Prix": float(book.iloc[0]['Prix']),
                    "ISBN": barcode
                }
                st.session_state.cart.append(item)
                st.toast(f"Ajouté : {item['Titre']}")
            else:
                st.error("Livre non trouvé dans le catalogue.")

        # Affichage du Panier
        if st.session_state.cart:
            cart_df = pd.DataFrame(st.session_state.cart)
            st.table(cart_df)
            
            total_brut = sum(item['Prix'] for item in st.session_state.cart)
            
            # --- ZONE CALCULATRICE / DÉCOTE ---
            col1, col2 = st.columns(2)
            with col1:
                discount_type = st.radio("Type de remise", ["Aucune", "Pourcentage (%)", "Montant fixe (€)"])
            with col2:
                discount_val = st.number_input("Valeur de la remise", value=0.0)

            if discount_type == "Pourcentage (%)":
                total_final = total_brut * (1 - discount_val / 100)
            elif discount_type == "Montant fixe (€)":
                total_final = total_brut - discount_val
            else:
                total_final = total_brut

            st.metric(label="TOTAL À PAYER", value=f"{total_final:.2f} €")

            # --- VALIDATION PAIEMENT ---
            payment_mode = st.selectbox("Mode de paiement", ["CB", "Espèces", "Chèque"])
            
            if st.button("Valider la vente", type="primary"):
                for item in st.session_state.cart:
                    st.session_state.sales.append({
                        "Date": datetime.now().strftime("%H:%M:%S"),
                        "Titre": item['Titre'],
                        "ISBN": item['ISBN'],
                        "Prix_Final": total_final / len(st.session_state.cart), # Répartition du prix
                        "Paiement": payment_mode
                    })
                st.session_state.cart = [] # Vide le panier
                st.success("Vente enregistrée !")
                st.rerun()

# --- TAB 3: RÉSUMÉ & EXPORT ---
with tabs[2]:
    if st.session_state.sales:
        sales_df = pd.DataFrame(st.session_state.sales)
        st.subheader("Ventes de la journée")
        st.dataframe(sales_df)
        
        # Récapitulatif
        st.write("---")
        recap = sales_df.groupby("Paiement")["Prix_Final"].sum()
        st.write("**Total par mode de paiement :**")
        st.table(recap)

        # Export Excel
        def convert_df(df):
            return df.to_csv(index=False).encode('utf-8')

        csv = convert_df(sales_df)
        st.download_button(
            label="📥 Télécharger le bilan final (CSV/Excel)",
            data=csv,
            file_name=f"bilan_stand_{datetime.now().strftime('%Y-%m-%d')}.csv",
            mime='text/csv',
        )
    else:
        st.info("Aucune vente enregistrée pour le moment.")