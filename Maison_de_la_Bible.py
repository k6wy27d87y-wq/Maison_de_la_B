import streamlit as st
import pandas as pd
import numpy as np
import uuid
import json
from datetime import datetime
from io import BytesIO

import cv2
from PIL import Image
import requests
import base64


# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="Librairie Stand PRO", layout="wide")

st.title("📚 Librairie - Caisse Stand PRO")
st.caption("Scan code-barres + caisse + stock + fallback intelligent")


# =========================================================
# STATE INIT
# =========================================================
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


# =========================================================
# BOOK SEARCH
# =========================================================
def find_book(barcode):
    df = st.session_state.books
    match = df[df["barcode"].astype(str) == str(barcode)]
    return match.iloc[0] if not match.empty else None


# =========================================================
# ZXING FALLBACK (WEB API)
# =========================================================
def decode_zxing(image):
    try:
        _, buffer = cv2.imencode(".jpg", image)
        img_b64 = base64.b64encode(buffer).decode()

        files = {
            "file": ("image.jpg", base64.b64decode(img_b64), "image/jpeg")
        }

        r = requests.post(
            "https://zxing.org/w/decode",
            files=files,
            timeout=5
        )

        if "Parsed Result" in r.text:
            import re
            match = re.search(r"Parsed Result</td><td>(.*?)</td>", r.text)
            if match:
                return match.group(1)

    except:
        return None

    return None


# =========================================================
# OPENCV DETECTION (LOCAL ROI)
# =========================================================
def detect_barcode_opencv(image):
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        grad = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=-1)
        grad = cv2.convertScaleAbs(grad)

        blurred = cv2.blur(grad, (9, 9))
        _, thresh = cv2.threshold(blurred, 225, 255, cv2.THRESH_BINARY)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            c = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(c)

            roi = image[y:y+h, x:x+w]

            return decode_zxing(roi)

    except:
        return None

    return None


# =========================================================
# FULL SCAN PIPELINE
# =========================================================
def scan_image(file):
    img = Image.open(file).convert("RGB")
    img_np = np.array(img)
    img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    # 1. OpenCV detection
    result = detect_barcode_opencv(img_cv)

    # 2. fallback global
    if not result:
        result = decode_zxing(img_cv)

    return result


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
# SIDEBAR
# =========================================================
conference = st.text_input("Conférence")
seller = st.text_input("Vendeur")


# =========================================================
# SCANNER
# =========================================================
st.subheader("📸 Scan Code-Barres")

camera = st.camera_input("Prendre une photo du code-barres")

barcode_detected = None

if camera:
    barcode_detected = scan_image(camera)

    if barcode_detected:
        st.success(f"Code détecté : {barcode_detected}")
    else:
        st.warning("Détection automatique impossible")


# =========================================================
# MANUAL INPUT (PRIMARY RELIABILITY)
# =========================================================
manual_barcode = st.text_input("Ou saisir code-barres")

final_barcode = barcode_detected or manual_barcode


# =========================================================
# ADD BUTTON
# =========================================================
if st.button("➕ Ajouter au panier"):

    if not final_barcode:
        st.warning("Aucun code-barres")
    else:
        book = find_book(final_barcode)

        if not book:
            st.error("Livre introuvable")
        elif book["stock"] <= 0:
            st.error("Stock épuisé")
        else:
            add_to_cart(book)

            idx = st.session_state.books.index[
                st.session_state.books["barcode"] == book["barcode"]
            ][0]

            st.session_state.books.at[idx, "stock"] -= 1

            st.success(f"{book['title']} ajouté")


# =========================================================
# CART
# =========================================================
st.divider()
st.subheader("🛒 Panier")

total = sum(i["price"] * i["quantity"] for i in st.session_state.cart)

st.write(st.session_state.cart)
st.metric("Total", f"{total:.2f} €")


discount = st.number_input("Remise", 0.0)
payment = st.selectbox("Paiement", ["CB", "Espèces", "Chèque"])


# =========================================================
# VALIDATION VENTE
# =========================================================
if st.button("💳 Valider vente"):

    if st.session_state.cart:

        sale = {
            "id": str(uuid.uuid4())[:8],
            "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "conference": conference or "NA",
            "seller": seller or "NA",
            "items": st.session_state.cart.copy(),
            "payment": payment,
            "discount": discount,
            "total": max(total - discount, 0)
        }

        st.session_state.sales.append(sale)

        st.session_state.cart = []

        st.success(f"Vente enregistrée ({sale['id']})")

    else:
        st.warning("Panier vide")


# =========================================================
# STOCK
# =========================================================
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
    st.dataframe(pd.DataFrame(rows))
else:
    st.info("Aucune vente")
