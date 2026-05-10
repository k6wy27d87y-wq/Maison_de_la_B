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

# -------------------------------------------------------------------
# CONFIG PAGE
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Librairie - Gestion Stand",
    layout="wide",
    initial_sidebar_state="auto"
)

st.title("📚 Librairie - Gestion de Stand")
st.caption("Application de vente conférence - Scanner code-barres + synchronisation Google Sheets")

# -------------------------------------------------------------------
# SESSION STATE INIT
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
# GOOGLE SHEETS
# -------------------------------------------------------------------
def save_to_google_sheet(sale_record):
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        if "google_sheet_key" in st.secrets and "sheet_id" in st.secrets:
            creds_dict = json.loads(st.secrets["google_sheet_key"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            sheet = client.open_by_key(st.secrets["sheet_id"]).sheet1

        elif "temp_google_key" in st.session_state and "temp_sheet_id" in st.session_state:
            creds_dict = json.loads(st.session_state.temp_google_key)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            sheet = client.open_by_key(st.session_state.temp_sheet_id).sheet1
        else:
            return False

        for item in sale_record["items"]:
            sheet.append_row([
                sale_record["date"],
                sale_record["conference"],
                sale_record["vendeur"],
                item["title"],
                item["barcode"],
                item["quantity"],
                sale_record["payment"],
                sale_record["discount"],
                sale_record["total"]
            ])

        return True

    except Exception as e:
        st.error(f"Erreur Google Sheets : {e}")
        return False

# -------------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuration")

    conference_name = st.text_input("Nom de la conférence")
    seller_name = st.text_input("Nom du vendeur")

    uploaded_file = st.file_uploader("Importer le stock CSV", type=["csv"])

    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            df.columns = [c.lower().strip() for c in df.columns]

            required = ["barcode", "title", "price", "stock"]

            if all(col in df.columns for col in required):
                df["barcode"] = df["barcode"].astype(str)
                df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
                df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0).astype(int)
                st.session_state.books = df
                st.success("Stock importé")
            else:
                st.error(f"Colonnes requises : {required}")

        except Exception as e:
            st.error(f"Erreur import : {e}")

    st.divider()
    st.subheader("📎 Google Sheets")

    uploaded_json = st.file_uploader("Clé JSON", type=["json"])
    if uploaded_json:
        try:
            key = json.load(uploaded_json)
            st.session_state["temp_google_key"] = json.dumps(key)
            st.success("Clé chargée")
        except:
            st.error("JSON invalide")

    sheet_id_input = st.text_input("Sheet ID")
    if sheet_id_input:
        st.session_state["temp_sheet_id"] = sheet_id_input

# -------------------------------------------------------------------
# SCANNER
# -------------------------------------------------------------------
st.subheader("📸 Scanner")

camera_image = st.camera_input("Photo code-barres")

if camera_image:
    try:
        img = Image.open(camera_image).convert("RGB")
        decoded = decode(np.array(img))

        if decoded:
            barcode = decoded[0].data.decode("utf-8")
            st.session_state.scanned_barcode = barcode
            st.success(f"Code scanné : {barcode}")
        else:
            st.warning("Aucun code détecté")

    except Exception as e:
        st.error(f"Erreur scan : {e}")

col1, col2 = st.columns([3, 1])

with col1:
    manual_barcode = st.text_input("Code-barres manuel")

with col2:
    add_button = st.button("➕ Ajouter")

barcode = ""
if st.session_state.scanned_barcode:
    barcode = st.session_state.scanned_barcode.strip()
elif manual_barcode:
    barcode = re.sub(r"\s+", "", manual_barcode)

if add_button:
    if not barcode:
        st.warning("Code manquant")
    else:
        match = st.session_state.books[
            st.session_state.books["barcode"].astype(str) == barcode
        ]

        if match.empty:
            st.error("Livre introuvable")
        else:
            book = match.iloc[0]

            if book["stock"] <= 0:
                st.error("Stock épuisé")
            else:
                existing = next(
                    (i for i in st.session_state.cart if str(i["barcode"]) == str(book["barcode"])),
                    None
                )

                if existing:
                    existing["quantity"] += 1
                else:
                    st.session_state.cart.append({
                        "barcode": book["barcode"],
                        "title": book["title"],
                        "price": float(book["price"]),
                        "quantity": 1
                    })

                idx = st.session_state.books[
                    st.session_state.books["barcode"] == book["barcode"]
                ].index[0]

                st.session_state.books.at[idx, "stock"] -= 1

                st.success("Ajouté au panier")
                st.session_state.scanned_barcode = ""

# -------------------------------------------------------------------
# PAYMENT
# -------------------------------------------------------------------
colA, colB = st.columns(2)

with colA:
    payment = st.selectbox("Paiement", ["Carte", "Espèces", "Chèque"])
    discount = st.number_input("Remise", min_value=0.0, value=0.0)

with colB:
    subtotal = sum(i["price"] * i["quantity"] for i in st.session_state.cart)
    total = max(subtotal - discount, 0)

    st.metric("Sous-total", f"{subtotal:.2f} €")
    st.metric("Total", f"{total:.2f} €")

    if st.button("Valider vente"):
        if st.session_state.cart:
            sale = {
                "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "conference": conference_name or "Non définie",
                "vendeur": seller_name or "Anonyme",
                "items": st.session_state.cart.copy(),
                "payment": payment,
                "discount": discount,
                "total": total
            }

            st.session_state.sales.append(sale)

            ok = save_to_google_sheet(sale)

            if ok:
                st.success("Vente enregistrée + Google Sheets")
            else:
                st.success("Vente enregistrée localement")

            st.session_state.cart = []

        else:
            st.warning("Panier vide")

# -------------------------------------------------------------------
# CART
# -------------------------------------------------------------------
st.divider()
st.subheader("🛒 Panier")

if st.session_state.cart:
    df = pd.DataFrame([
        {
            "ISBN": i["barcode"],
            "Titre": i["title"],
            "Qté": i["quantity"],
            "Prix": i["price"],
            "Total": i["price"] * i["quantity"]
        }
        for i in st.session_state.cart
    ])
    st.dataframe(df)
else:
    st.info("Panier vide")

# -------------------------------------------------------------------
# STOCK
# -------------------------------------------------------------------
st.subheader("📦 Stock")
st.dataframe(st.session_state.books)

# -------------------------------------------------------------------
# HISTORY
# -------------------------------------------------------------------
st.subheader("📈 Historique")

if st.session_state.sales:
    rows = []
    for sale in st.session_state.sales:
        for item in sale["items"]:
            rows.append({
                "Date": sale["date"],
                "Livre": item["title"],
                "ISBN": item["barcode"],
                "Qté": item["quantity"],
                "Total": sale["total"]
            })

    history = pd.DataFrame(rows)
    st.dataframe(history)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        history.to_excel(writer, index=False)

    st.download_button(
        "Télécharger Excel",
        data=output.getvalue(),
        file_name="ventes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Aucune vente")

# -------------------------------------------------------------------
# FINAL MARKDOWN FIXED (IMPORTANT)
# -------------------------------------------------------------------
st.markdown("""
### 🚀 Utilisation

- Scanner avec caméra ou saisie manuelle
- Ajout automatique au panier
- Gestion du stock en temps réel

### 📦 Installation

```bash
pip install streamlit pandas openpyxl gspread oauth2client pyzbar pillow
