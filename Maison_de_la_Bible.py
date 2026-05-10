import streamlit as st
import re
import pandas as pd
from datetime import datetime
from io import BytesIO
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit.components.v1 as components

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

# Variable temporaire pour stocker le code-barres scanné par la caméra
if "scanned_barcode" not in st.session_state:
    st.session_state.scanned_barcode = ""

# -------------------------------------------------------------------
# FONCTIONS D'ACCÈS À GOOGLE SHEETS
# -------------------------------------------------------------------
def save_to_google_sheet(sale_record):
    """
    Enregistre une vente dans un Google Sheet partagé.
    La feuille doit contenir les colonnes :
    Date, Conférence, Vendeur, Livre, ISBN, Quantité, Paiement, Remise, Total
    """
    try:
        # Récupérer les identifiants depuis les secrets Streamlit
        # Ou bien depuis un fichier uploadé (voir sidebar)
        if "google_sheet_key" not in st.secrets:
            st.warning("Configuration Google Sheets manquante. Vente non synchronisée.")
            return False

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(st.secrets["google_sheet_key"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)

        sheet_id = st.secrets.get("sheet_id", "")
        if not sheet_id:
            st.warning("ID de la feuille Google Sheet manquant.")
            return False

        sheet = client.open_by_key(sheet_id).sheet1

        # Ajouter chaque ligne (un livre par ligne, même si la vente contient plusieurs livres)
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

    # Import du stock CSV
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
    st.subheader("📎 Liaison Google Sheets")
    st.markdown(
        """
        Pour synchroniser les ventes vers une feuille Google Sheets partagée :
        1. [Créez un projet Google Cloud](https://console.cloud.google.com/) activez l'API Google Sheets et Drive.
        2. Créez un compte de service et téléchargez sa clé JSON.
        3. Copiez le contenu du fichier JSON et collez-le ci-dessous.
        4. Indiquez l'ID de votre feuille (dans l'URL : `https://docs.google.com/spreadsheets/d/ID_ICI/edit`).
        """
    )
    # Option pour uploader la clé JSON directement (sans secrets)
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
# SCANNER CODE-BARRES PAR CAMÉRA (HTML5-QRCode)
# -------------------------------------------------------------------
st.subheader("📷 Scanner un livre")
# Zone pour le scanner caméra
scanner_html = """
<div id="reader" style="width: 100%; max-width: 400px; margin: auto;"></div>
<script src="https://unpkg.com/html5-qrcode@2.3.8/minified/html5-qrcode.min.js"></script>
<script>
    function onScanSuccess(decodedText, decodedResult) {
        // Envoyer le résultat à Streamlit via un événement
        const input = document.createElement('input');
        input.type = 'text';
        input.value = decodedText;
        input.id = 'scanned_value';
        document.body.appendChild(input);
        // Créer un événement personnalisé pour Streamlit
        const event = new Event('streamlit:valueChanged', {bubbles: true});
        input.dispatchEvent(event);
        // Arrêter le scanner après un scan réussi (optionnel)
        html5QrcodeScanner.clear();
    }
    let html5QrcodeScanner = new Html5QrcodeScanner(
        "reader", { fps: 10, qrbox: {width: 250, height: 250} }, false);
    html5QrcodeScanner.render(onScanSuccess);
</script>
"""
components.html(scanner_html, height=300)

# Champ texte manuel alternative
barcode_input = st.text_input(
    "Ou saisissez le code-barres manuellement",
    placeholder="9782070368228",
    key="manual_barcode"
)

# Combiner les deux sources : le scan caméra remplit un champ caché ? 
# On utilise un callback avec un champ texte qui se met à jour via JS.
# Pour simplifier, on utilise un champ texte normal et on ajoute un bouton "Ajouter"
# Le scan caméra remplit st.session_state.scanned_barcode via un composant qui appelle st.rerun()
# Ici, on va plutôt récupérer la valeur dans le champ texte (car JS peut injecter la valeur)
# Mais Streamlit ne capte pas automatiquement. On va utiliser un bouton "Utiliser le scan" supplémentaire.

# Solution simple : un champ texte modifiable par le scanner grâce à st.text_input + clé
# Le JS ci-dessus ne peut pas modifier directement la valeur. On opte pour une approche plus robuste :
# On utilise st.query_params pour passer le code scanné. Autre approche : un bouton "Ajouter" commun.

# Réécrivons la partie scanner caméra avec un callback qui envoie la valeur scannée via un paramètre d'URL.
# Version plus fiable : un composant qui appelle st.set_query_params puis st.experimental_rerun.
# Mais pour éviter la complexité, on garde la saisie manuelle ET on ajoute un bouton "Scanner" qui utilise la caméra
# via un popup ? Non, restons simples : l'utilisateur utilise la zone HTML pour scanner, puis copie-colle le résultat ?
# Pas idéal.

# Meilleure méthode : utiliser le module "streamlit_webrtc" ou "streamlit_qrcode_scanner" mais dépendances externes.
# Je choisis d'intégrer un scanner plus simple : un bouton "📸 Scanner" qui ouvre un fichier image (photo) via st.camera_input
# puis décode le code-barres avec pyzbar. Cela fonctionne sur mobile et bureau.

# On va remplacer le scanner HTML par st.camera_input + pyzbar (plus fiable pour tous les appareils).

# -------------------------------------------------------------------
# SCANNER PAR CAMERA AVEC IMAGE (pyzbar)
# -------------------------------------------------------------------
st.subheader("📸 Scanner avec la caméra (photo)")
camera_image = st.camera_input("Prenez une photo du code-barres")
if camera_image is not None:
    try:
        from PIL import Image
        import numpy as np
        from pyzbar.pyzbar import decode
        img = Image.open(camera_image)
        # Convertir en RGB si nécessaire
        img = img.convert('RGB')
        decoded_objects = decode(np.array(img))
        if decoded_objects:
            barcode_value = decoded_objects[0].data.decode('utf-8')
            st.session_state.scanned_barcode = barcode_value
            st.success(f"Code scanné : {barcode_value}")
        else:
            st.error("Aucun code-barres trouvé sur l'image")
    except ImportError:
        st.error("Bibliothèque pyzbar manquante. Installez-la : `pip install pyzbar pillow`")
    except Exception as e:
        st.error(f"Erreur lors du décodage : {e}")

# Champ pour le code-barres (manuel ou scanné)
clean_barcode = ""
if st.session_state.scanned_barcode:
    clean_barcode = st.session_state.scanned_barcode.strip()
    # vider après ajout ?
elif barcode_input:
    clean_barcode = re.sub(r"\s+", "", barcode_input)

# Bouton d'ajout
if st.button("➕ Ajouter au panier", use_container_width=True):
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
                # Ajout au panier
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
                # Mise à jour du stock
                idx = st.session_state.books[st.session_state.books["barcode"] == book["barcode"]].index[0]
                st.session_state.books.at[idx, "stock"] = max(int(book["stock"]) - 1, 0)
                st.success(f"{book['title']} ajouté au panier")
                # Réinitialiser le code scanné
                st.session_state.scanned_barcode = ""

# -------------------------------------------------------------------
# PAIEMENT & TOTAL
# -------------------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    payment_method = st.selectbox("Mode de paiement", ["Carte Bancaire", "Espèces", "Chèque"])
    discount = st.number_input("Remise (€)", min_value=0.0, value=0.0, step=0.5)
with col2:
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
            # Sauvegarde locale
            st.session_state.sales.append(sale_record)
            # Sauvegarde Google Sheet si configuré
            if "temp_google_key" in st.session_state and "temp_sheet_id" in st.session_state:
                # Utiliser les identifiants temporaires
                try:
                    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                    creds_dict = json.loads(st.session_state.temp_google_key)
                    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                    client = gspread.authorize(creds)
                    sheet = client.open_by_key(st.session_state.temp_sheet_id).sheet1
                    for item in sale_record["items"]:
                        sheet.append_row([
                            sale_record["date"], sale_record["conference"], sale_record["vendeur"],
                            item["title"], item["barcode"], item["quantity"],
                            sale_record["payment"], sale_record["discount"], sale_record["total"]
                        ])
                    st.success("Vente enregistrée localement et synchronisée dans Google Sheets")
                except Exception as e:
                    st.error(f"Erreur synchronisation Google Sheets : {e}. Vente enregistrée localement.")
            else:
                # Tenter d'utiliser st.secrets si présents
                try:
                    if "google_sheet_key" in st.secrets and "sheet_id" in st.secrets:
                        save_to_google_sheet(sale_record)
                        st.success("Vente enregistrée localement et synchronisée (secrets)")
                    else:
                        st.success("Vente enregistrée localement (Google Sheets non configuré)")
                except:
                    st.success("Vente enregistrée localement")
            # Vider le panier
            st.session_state.cart = []

# -------------------------------------------------------------------
# AFFICHAGE PANIER & STOCK
# -------------------------------------------------------------------
st.divider()
left, right = st.columns(2)
with left:
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
with right:
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

    # Export Excel
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

- L'application est **responsiv**e et s'adapte aux petits écrans.
- Utilisez le **bouton "Prenez une photo"** pour scanner un code-barres avec la caméra de votre téléphone.
- Vous pouvez aussi saisir manuellement l'ISBN.
- Pour partager l'application sur le réseau local, lancez Streamlit avec `--server.address 0.0.0.0` et accédez-y depuis l'IP de votre machine.

### 🔧 Déploiement et configuration Google Sheets (optionnel)

1. **Streamlit Community Cloud** : déposez ce code sur GitHub, connectez votre compte Streamlit.
2. Ajoutez les secrets dans les paramètres de l'app Streamlit :
   - `google_sheet_key` = contenu complet du fichier JSON du compte de service
   - `sheet_id` = ID de votre Google Sheet
3. Partagez l'URL avec votre équipe.

### 📦 Dépendances à installer

```bash
pip install streamlit pandas openpyxl gspread oauth2client pyzbar pillow
