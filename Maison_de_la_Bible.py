import streamlit as st
import re
import pandas as pd
from datetime import datetime
from io import BytesIO
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image
import numpy as np
from pyzbar.pyzbar import decode

# Configuration de la page (doit être la première commande Streamlit)
st.set_page_config(
    page_title="Librairie - Gestion Stand",
    layout="wide",
    initial_sidebar_state="auto"
)

st.title("📚 Librairie - Gestion de Stand")
st.caption("Application de vente conférence - Scanner code-barres + synchronisation Google Sheets")

# -------------------------------------------------------------------
# INITIALISATION DES SESSION STATES
# -------------------------------------------------------------------
if "books" not in st.session_state:
    st.session_state.books = pd.DataFrame([
        {"barcode": "9782070368228", "title": "Le Petit Prince", "price": 8.90, "stock": 12},
        {"barcode": "9782253006329", "title": "1984", "price": 12.50, "stock": 8},
        {"barcode": "9782070413119", "title": "L'Étranger", "price": 7.20, "stock": 5},
    ])

if "cart" not in st.session_state:
    st.session_state.cart = []

if "sales" not in st.session_state:
    st.session_state.sales = []

if "scanned_barcode" not in st.session_state:
    st.session_state.scanned_barcode = ""

# -------------------------------------------------------------------
# FONCTION D'ENVOI VERS GOOGLE SHEETS
# -------------------------------------------------------------------
def save_to_google_sheet(sale_record):
    try:
        if "google_sheet_key" in st.secrets and "sheet_id" in st.secrets:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds_dict = json.loads(st.secrets["google_sheet_key"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            sheet = client.open_by_key(st.secrets["sheet_id"]).sheet1
        elif "temp_google_key" in st.session_state and "temp_sheet_id" in st.session_state:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds_dict = json.loads(st.session_state.temp_google_key)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            sheet = client.open_by_key(st.session_state.temp_sheet_id).sheet1
        else:
            return False

        for item in sale_record["items"]:
            row = [
                sale_record["date"],
                sale_record["conference"],
                sale_record["vendeur"],
                item["title"],
                item["barcode"],
                item["quantity"],
                sale_record["payment"],
                sale_record["discount"],
                sale_record["total"]
            ]
            sheet.append_row(row)
        return True
    except Exception as e:
        st.error(f"Erreur Google Sheets : {e}")
        return False

# -------------------------------------------------------------------
# SIDEBAR : CONFIGURATION
# -------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuration")
    conference_name = st.text_input("Nom de la conférence", placeholder="Ex: Salon du Livre 2025")
    seller_name = st.text_input("Nom du vendeur", placeholder="Prénom Nom")

    uploaded_file = st.file_uploader("Importer le stock CSV", type=["csv"])
    if uploaded_file:
        try:
            imported_df = pd.read_csv(uploaded_file)
            imported_df.columns = [col.strip().lower() for col in imported_df.columns]
            required = ["barcode", "title", "price", "stock"]
            if all(col in imported_df.columns for col in required):
                imported_df["barcode"] = imported_df["barcode"].astype(str)
                imported_df["price"] = pd.to_numeric(imported_df["price"], errors="coerce").fillna(0)
                imported_df["stock"] = pd.to_numeric(imported_df["stock"], errors="coerce").fillna(0).astype(int)
                st.session_state.books = imported_df
                st.success("Stock importé avec succès")
            else:
                st.error(f"Colonnes requises : {', '.join(required)}")
        except Exception as e:
            st.error(f"Erreur import : {e}")

    st.divider()
    st.subheader("📎 Liaison Google Sheets (optionnel)")
    st.markdown("""
    Pour synchroniser les ventes vers Google Sheets :
    1. Créez un compte de service et téléchargez sa clé JSON.
    2. Copiez le contenu du fichier JSON ci-dessous.
    3. Indiquez l'ID de votre feuille.
    """)
    uploaded_json = st.file_uploader("Fichier JSON du compte de service", type=["json"])
    if uploaded_json is not None:
        try:
            key_content = json.load(uploaded_json)
            st.session_state["temp_google_key"] = json.dumps(key_content)
            st.success("Clé chargée temporairement")
        except:
            st.error("Fichier JSON invalide")

    sheet_id_input = st.text_input("ID de la feuille Google Sheet", placeholder="1ABC...xyz")
    if sheet_id_input:
        st.session_state["temp_sheet_id"] = sheet_id_input

# -------------------------------------------------------------------
# SCANNER PAR CAMÉRA
# -------------------------------------------------------------------
st.subheader("📸 Scanner un livre avec la caméra")
camera_image = st.camera_input("Prenez une photo du code-barres")
if camera_image is not None:
    try:
        img = Image.open(camera_image).convert('RGB')
        decoded_objects = decode(np.array(img))
        if decoded_objects:
            barcode_value = decoded_objects[0].data.decode('utf-8')
            st.session_state.scanned_barcode = barcode_value
            st.success(f"Code scanné : {barcode_value}")
        else:
            st.error("Aucun code-barres trouvé sur l'image")
    except Exception as e:
        st.error(f"Erreur lors du décodage : {e}")

col_manual, col_btn = st.columns([3, 1])
with col_manual:
    manual_barcode = st.text_input(
        "Ou saisissez le code-barres manuellement",
        placeholder="9782070368228",
        key="manual_barcode_input"
    )
with col_btn:
    st.write("")
    add_button = st.button("➕ Ajouter au panier", use_container_width=True)

clean_barcode = ""
if st.session_state.scanned_barcode:
    clean_barcode = st.session_state.scanned_barcode.strip()
elif manual_barcode:
    clean_barcode = re.sub(r"\s+", "", manual_barcode)

if add_button:
    if clean_barcode == "":
        st.warning("Veuillez scanner ou saisir un code-barres")
    else:
        matching_books = st.session_state.books[st.session_state.books["barcode"].astype(str) == clean_barcode]
        if matching_books.empty:
            st.error("Livre introuvable dans le stock")
        else:
            book = matching_books.iloc[0]
            if book["stock"] <= 0:
                st.error("Stock épuisé pour cet ouvrage")
            else:
                existing = next((item for item in st.session_state.cart if str(item["barcode"]) == str(book["barcode"])), None)
                if existing:
                    existing["quantity"] += 1
                else:
                    st.session_state.cart.append({
                        "barcode": book["barcode"],
                        "title": book["title"],
                        "price": float(book["price"]),
                        "quantity": 1
                    })
                idx = st.session_state.books[st.session_state.books["barcode"] == book["barcode"]].index[0]
                st.session_state.books.at[idx, "stock"] = max(int(book["stock"]) - 1, 0)
                st.success(f"{book['title']} ajouté au panier")
                st.session_state.scanned_barcode = ""

# -------------------------------------------------------------------
# PAIEMENT & TOTAL
# -------------------------------------------------------------------
col_pay1, col_pay2 = st.columns(2)
with col_pay1:
    payment_method = st.selectbox("Mode de paiement", ["Carte Bancaire", "Espèces", "Chèque"])
    discount = st.number_input("Remise (€)", min_value=0.0, value=0.0, step=0.5)
with col_pay2:
    subtotal = sum(item["price"] * item["quantity"] for item in st.session_state.cart)
    total = max(subtotal - discount, 0)
    st.metric("Sous-total", f"{subtotal:.2f} €")
    st.metric("Total final", f"{total:.2f} €", delta=f"-{discount:.2f} €" if discount > 0 else None)

    if st.button("✅ Valider la vente", use_container_width=True):
        if not st.session_state.cart:
            st.warning("Le panier est vide")
        else:
            sale_record = {
                "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "conference": conference_name if conference_name else "Non spécifiée",
                "vendeur": seller_name if seller_name else "Anonyme",
                "items": st.session_state.cart.copy(),
                "payment": payment_method,
                "discount": discount,
                "total": total,
            }
            st.session_state.sales.append(sale_record)
            synced = save_to_google_sheet(sale_record)
            if synced:
                st.success("Vente enregistrée localement et synchronisée dans Google Sheets")
            else:
                st.success("Vente enregistrée localement (Google Sheets non configuré)")
            st.session_state.cart = []

# -------------------------------------------------------------------
# AFFICHAGE PANIER & STOCK
# -------------------------------------------------------------------
st.divider()
col_left, col_right = st.columns(2)
with col_left:
    st.subheader("🛒 Panier actuel")
    if st.session_state.cart:
        cart_df = pd.DataFrame([{
            "ISBN": item["barcode"],
            "Titre": item["title"],
            "Qté": item["quantity"],
            "Prix": item["price"],
            "Total": item["price"] * item["quantity"]
        } for item in st.session_state.cart])
        st.dataframe(cart_df, use_container_width=True)
    else:
        st.info("Aucun livre dans le panier")
with col_right:
    st.subheader("📦 Stock restant")
    stock_view = st.session_state.books.rename(columns={
        "barcode": "ISBN", "title": "Titre", "price": "Prix", "stock": "Stock"
    })
    st.dataframe(stock_view, use_container_width=True)

# -------------------------------------------------------------------
# HISTORIQUE DES VENTES
# -------------------------------------------------------------------
st.divider()
st.subheader("📈 Historique des ventes")
if st.session_state.sales:
    rows = []
    for sale in st.session_state.sales:
        for item in sale["items"]:
            rows.append({
                "Date": sale["date"],
                "Conférence": sale["conference"],
                "Vendeur": sale["vendeur"],
                "Livre": item["title"],
                "ISBN": item["barcode"],
                "Quantité": item["quantity"],
                "Paiement": sale["payment"],
                "Remise": sale["discount"],
                "Total": sale["total"]
            })
    history_df = pd.DataFrame(rows)
    st.dataframe(history_df, use_container_width=True)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        history_df.to_excel(writer, index=False, sheet_name="Ventes")
    st.download_button(
        label="📥 Télécharger l'historique (Excel)",
        data=output.getvalue(),
        file_name=f"ventes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Aucune vente enregistrée pour l'instant")

# -------------------------------------------------------------------
# INSTRUCTIONS FINALES
# -------------------------------------------------------------------
st.divider()
st.markdown("""
### 🚀 Utilisation sur téléphone

- L'application est responsive et s'adapte aux petits écrans.
- Utilisez le bouton "Prenez une photo" pour scanner un code-barres avec la caméra.
- Vous pouvez aussi saisir manuellement l'ISBN.

### 🔧 Configuration Google Sheets (optionnel)

1. Déployez sur Streamlit Cloud.
2. Ajoutez les secrets : `google_sheet_key` (contenu du JSON) et `sheet_id`.
3. Partagez l'URL avec votre équipe.

### 📦 Dépendances

```bash
pip install streamlit pandas openpyxl gspread oauth2client pyzbar pillow
