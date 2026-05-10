import streamlit as st
import pandas as pd
import numpy as np
import re
import json
from datetime import datetime
from io import BytesIO

from PIL import Image
from pyzbar.pyzbar import decode

import gspread
from oauth2client.service_account import ServiceAccountCredentials


# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="Librairie Stand", layout="wide")

st.title("📚 Librairie - Stand Conférence")
st.caption("Version stable - scan + caisse + sync")

# =========================================================
# INIT STATE
# =========================================================
def init_state():
    if "books" not in st.session_state:
        st.session_state.books = pd.DataFrame([
            {"barcode": "9782070368228", "title": "Le Petit Prince", "price": 8.9, "stock": 12},
            {"barcode": "9782253006329", "title": "1984", "price": 12.5, "stock": 8},
            {"barcode": "9782070413119", "title": "L'Étranger", "price": 7.2, "stock": 5},
        ])

    if "cart" not in st.session_state:
        st.session_state.cart = []

    if "sales" not in st.session_state:
        st.session_state.sales = []

    if "barcode" not in st.session_state:
        st.session_state.barcode = ""


init_state()


# =========================================================
# GOOGLE SHEETS
# =========================================================
def push_google_sheet(sale):
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        creds_dict = None

        if "google_sheet_key" in st.secrets:
            creds_dict = json.loads(st.secrets["google_sheet_key"])

        elif "temp_google_key" in st.session_state:
            creds_dict = json.loads(st.session_state["temp_google_key"])

        if not creds_dict:
            return False

        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)

        sheet_id = st.secrets.get("sheet_id") or st.session_state.get("temp_sheet_id")
        if not sheet_id:
            return False

        sheet = client.open_by_key(sheet_id).sheet1

        for item in sale["items"]:
            sheet.append_row([
                sale["date"],
                sale["conference"],
                sale["seller"],
                item["title"],
                item["barcode"],
                item["quantity"],
                sale["payment"],
                sale["discount"],
                sale["total"]
            ])

        return True

    except Exception as e:
        st.error(f"Google Sheets error: {e}")
        return False


# =========================================================
# BARCODE SCAN SAFE
# =========================================================
def decode_barcode(image):
    try:
        img = Image.open(image).convert("RGB")
        decoded = decode(np.array(img))

        if decoded:
            return decoded[0].data.decode("utf-8")

    except Exception:
        return None

    return None


# =========================================================
# FIND BOOK
# =========================================================
def find_book(barcode):
    df = st.session_state.books
    match = df[df["barcode"].astype(str) == str(barcode)]
    return match.iloc[0] if not match.empty else None


# =========================================================
# ADD TO CART
# =========================================================
def add_to_cart(book):
    for item in st.session_state.cart:
        if item["barcode"] == book["barcode"]:
            item["quantity"] += 1
            return

    st.session_state.cart.append({
        "barcode": book["barcode"],
        "title": book["title"],
        "price": float(book["price"]),
        "quantity": 1
    })


# =========================================================
# UPDATE STOCK
# =========================================================
def update_stock(barcode):
    idx = st.session_state.books.index[
        st.session_state.books["barcode"] == barcode
    ][0]

    st.session_state.books.at[idx, "stock"] -= 1


# =========================================================
# UI - SIDEBAR
# =========================================================
with st.sidebar:
    st.header("⚙️ Config")

    conference = st.text_input("Conférence")
    seller = st.text_input("Vendeur")

    file = st.file_uploader("Stock CSV", type=["csv"])

    if file:
        df = pd.read_csv(file)
        df.columns = [c.lower().strip() for c in df.columns]

        if {"barcode", "title", "price", "stock"}.issubset(df.columns):
            df["barcode"] = df["barcode"].astype(str)
            df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
            df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0).astype(int)
            st.session_state.books = df
            st.success("Stock chargé")


# =========================================================
# SCANNER
# =========================================================
st.subheader("📸 Scan")

img = st.camera_input("Scanner code-barres")

if img:
    barcode = decode_barcode(img)

    if barcode:
        st.session_state.barcode = barcode
        st.success(f"Code: {barcode}")
    else:
        st.warning("Scan impossible")


manual = st.text_input("Ou saisie manuelle")
barcode_final = st.session_state.barcode or re.sub(r"\s+", "", manual)

if st.button("➕ Ajouter"):
    if not barcode_final:
        st.warning("Code manquant")
    else:
        book = find_book(barcode_final)

        if not book:
            st.error("Livre introuvable")
        elif book["stock"] <= 0:
            st.error("Stock épuisé")
        else:
            add_to_cart(book)
            update_stock(book["barcode"])
            st.session_state.barcode = ""
            st.success("Ajouté")


# =========================================================
# CART + TOTAL
# =========================================================
st.divider()
st.subheader("🛒 Panier")

total = 0

for item in st.session_state.cart:
    total += item["price"] * item["quantity"]

st.write(st.session_state.cart)
st.metric("Total", f"{total:.2f} €")

discount = st.number_input("Remise", 0.0)
payment = st.selectbox("Paiement", ["CB", "Espèces", "Chèque"])


if st.button("Valider vente"):
    if st.session_state.cart:

        sale = {
            "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "conference": conference or "NA",
            "seller": seller or "NA",
            "items": st.session_state.cart.copy(),
            "payment": payment,
            "discount": discount,
            "total": max(total - discount, 0)
        }

        st.session_state.sales.append(sale)

        ok = push_google_sheet(sale)

        if ok:
            st.success("Vente sync Google Sheets")
        else:
            st.success("Vente locale uniquement")

        st.session_state.cart = []

    else:
        st.warning("Panier vide")


# =========================================================
# STOCK
# =========================================================
st.divider()
st.subheader("📦 Stock")
st.dataframe(st.session_state.books)


# =========================================================
# HISTORY
# =========================================================
st.subheader("📈 Historique")

rows = []

for sale in st.session_state.sales:
    for item in sale["items"]:
        rows.append({
            "Date": sale["date"],
            "Livre": item["title"],
            "Qté": item["quantity"],
            "Total": sale["total"]
        })

if rows:
    df = pd.DataFrame(rows)
    st.dataframe(df)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    st.download_button(
        "Export Excel",
        buffer.getvalue(),
        file_name="sales.xlsx"
    )
else:
    st.info("Aucune vente")
