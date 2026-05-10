import streamlit as st
import re
import pandas as pd
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="Librairie - Gestion Stand", layout="wide")

st.title("📚 Librairie - Gestion de Stand")
st.caption("Application de vente conférence avec scan code-barres")

if "books" not in st.session_state:
    st.session_state.books = pd.DataFrame([
        {
            "barcode": "9782070368228",
            "title": "Le Petit Prince",
            "price": 8.90,
            "stock": 12,
        },
        {
            "barcode": "9782253006329",
            "title": "1984",
            "price": 12.50,
            "stock": 8,
        },
        {
            "barcode": "9782070413119",
            "title": "L'Étranger",
            "price": 7.20,
            "stock": 5,
        },
    ])

if "cart" not in st.session_state:
    st.session_state.cart = []

if "sales" not in st.session_state:
    st.session_state.sales = []

with st.sidebar:
    st.header("⚙️ Configuration")

    conference_name = st.text_input("Nom de la conférence")
    seller_name = st.text_input("Nom du vendeur")

    uploaded_file = st.file_uploader(
        "Importer le stock CSV",
        type=["csv"],
    )

    if uploaded_file:
        try:
            imported_df = pd.read_csv(uploaded_file)

            imported_df.columns = [col.strip().lower() for col in imported_df.columns]
            required_columns = ["barcode", "title", "price", "stock"]

            if all(col in imported_df.columns for col in required_columns):
                imported_df["barcode"] = imported_df["barcode"].astype(str)
                imported_df["price"] = pd.to_numeric(imported_df["price"], errors="coerce").fillna(0)
                imported_df["stock"] = pd.to_numeric(imported_df["stock"], errors="coerce").fillna(0).astype(int)

                st.session_state.books = imported_df
                st.success("Stock importé avec succès")
            else:
                st.error(
                    "Colonnes requises : barcode, title, price, stock"
                )

        except Exception as error:
            st.error(f"Erreur import : {error}")

col1, col2, col3 = st.columns([1.5, 1, 1])

with col1:
    st.subheader("📷 Scanner un livre")

    barcode_input = st.text_input(
        "Scanner ISBN / Code-barres",
        placeholder="9782070368228",
    )

    clean_barcode = re.sub(r"\\s+", "", barcode_input)

    if st.button("Ajouter au panier"):
        if clean_barcode == "":
            st.warning("Veuillez scanner un livre")

        else:
            matching_books = st.session_state.books[
                st.session_state.books["barcode"].astype(str)
                == clean_barcode
            ]

            if matching_books.empty:
                st.error("Livre introuvable")

            else:
                book = matching_books.iloc[0]

                if book["stock"] <= 0:
                    st.error("Stock épuisé")

                else:
                    existing_item = next(
                        (
                            item
                            for item in st.session_state.cart
                            if str(item["barcode"]) == str(book["barcode"])
                        ),
                        None,
                    )

                    if existing_item:
                        existing_item["quantity"] += 1

                    else:
                        st.session_state.cart.append(
                            {
                                "barcode": book["barcode"],
                                "title": book["title"],
                                "price": float(book["price"]),
                                "quantity": 1,
                            }
                        )

                    index = st.session_state.books[
                        st.session_state.books["barcode"]
                        == book["barcode"]
                    ].index[0]

                    current_stock = int(st.session_state.books.at[index, "stock"])
                    st.session_state.books.at[index, "stock"] = max(current_stock - 1, 0)

                    st.success(f"{book['title']} ajouté au panier")

with col2:
    st.subheader("💳 Paiement")

    payment_method = st.selectbox(
        "Mode de paiement",
        ["Carte Bancaire", "Espèces", "Chèque"],
    )

    discount = st.number_input(
        "Remise (€)",
        min_value=0.0,
        value=0.0,
        step=1.0,
    )

with col3:
    st.subheader("💰 Total")

    subtotal = sum(
        item["price"] * item["quantity"]
        for item in st.session_state.cart
    )

    total = max(subtotal - discount, 0)

    st.metric("Sous-total", f"{subtotal:.2f} €")
    st.metric("Total final", f"{total:.2f} €")

    if st.button("✅ Valider la vente"):
        if len(st.session_state.cart) == 0:
            st.warning("Le panier est vide")

        else:
            st.session_state.sales.append(
                {
                    "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "conference": conference_name,
                    "vendeur": seller_name,
                    "items": st.session_state.cart.copy(),
                    "payment": payment_method,
                    "discount": discount,
                    "total": total,
                }
            )

            st.session_state.cart = []

            st.success("Vente enregistrée")

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("🛒 Panier")

    if len(st.session_state.cart) == 0:
        st.info("Aucun livre dans le panier")

    else:
        cart_df = pd.DataFrame([
            {
                "ISBN": item["barcode"],
                "Titre": item["title"],
                "Qté": item["quantity"],
                "Prix": item["price"],
                "Total": item["price"] * item["quantity"],
            }
            for item in st.session_state.cart
        ])

        st.dataframe(cart_df, use_container_width=True)

with right:
    st.subheader("📦 Stock Stand")

    stock_display = st.session_state.books.copy()
    stock_display = stock_display.rename(columns={
        "barcode": "ISBN",
        "title": "Titre",
        "price": "Prix",
        "stock": "Stock",
    })

    st.dataframe(stock_display, use_container_width=True)

st.divider()

st.subheader("📈 Historique des ventes")

sales_rows = []

for sale in st.session_state.sales:
    for item in sale["items"]:
        sales_rows.append(
            {
                "Date": sale["date"],
                "Conférence": sale["conference"],
                "Vendeur": sale["vendeur"],
                "Livre": item["title"],
                "ISBN": item["barcode"],
                "Quantité": item["quantity"],
                "Paiement": sale["payment"],
                "Remise": sale["discount"],
                "Total": sale["total"],
            }
        )

if len(sales_rows) > 0:
    sales_df = pd.DataFrame(sales_rows)

    st.dataframe(sales_df, use_container_width=True)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sales_df.to_excel(writer, index=False, sheet_name="Ventes")

    st.download_button(
        label="📥 Télécharger Excel",
        data=output.getvalue(),
        file_name="ventes_conference.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

else:
    st.info("Aucune vente enregistrée")

st.divider()

st.markdown(
    """
### 🚀 Déploiement Streamlit

Lancer localement :
```bash
pip install streamlit pandas openpyxl
streamlit run app.py
```

Déploiement cloud :
- GitHub
- Streamlit Community Cloud
"""
)
