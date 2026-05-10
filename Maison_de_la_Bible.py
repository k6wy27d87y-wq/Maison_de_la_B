import React, { useMemo, useRef, useState } from "react"

const INITIAL_BOOKS = [
  {
    barcode: "9782070368228",
    title: "Le Petit Prince",
    price: 8.9,
    stock: 12,
  },
  {
    barcode: "9782253006329",
    title: "1984",
    price: 12.5,
    stock: 8,
  },
  {
    barcode: "9782070413119",
    title: "L'Étranger",
    price: 7.2,
    stock: 5,
  },
]

export default function BookStandSalesApp() {
  const [books, setBooks] = useState(INITIAL_BOOKS)
  const [barcodeInput, setBarcodeInput] = useState("")
  const [cart, setCart] = useState([])
  const [sales, setSales] = useState([])
  const [paymentMethod, setPaymentMethod] = useState("Carte Bancaire")
  const [discount, setDiscount] = useState(0)

  const inputRef = useRef(null)

  const addBookToCart = () => {
    const scannedBook = books.find(
      (book) => book.barcode === barcodeInput.trim(),
    )

    if (!scannedBook) {
      alert("Livre introuvable")
      return
    }

    if (scannedBook.stock <= 0) {
      alert("Stock épuisé")
      return
    }

    setCart((previousCart) => {
      const existingBook = previousCart.find(
        (item) => item.barcode === scannedBook.barcode,
      )

      if (existingBook) {
        return previousCart.map((item) =>
          item.barcode === scannedBook.barcode
            ? {
                ...item,
                quantity: item.quantity + 1,
              }
            : item,
        )
      }

      return [
        ...previousCart,
        {
          ...scannedBook,
          quantity: 1,
        },
      ]
    })

    setBooks((previousBooks) =>
      previousBooks.map((book) =>
        book.barcode === scannedBook.barcode
          ? {
              ...book,
              stock: book.stock - 1,
            }
          : book,
      ),
    )

    setBarcodeInput("")

    setTimeout(() => {
      inputRef.current?.focus()
    }, 50)
  }

  const removeBook = (barcode) => {
    const targetBook = cart.find((item) => item.barcode === barcode)

    if (!targetBook) return

    if (targetBook.quantity === 1) {
      setCart((previous) =>
        previous.filter((item) => item.barcode !== barcode),
      )
    } else {
      setCart((previous) =>
        previous.map((item) =>
          item.barcode === barcode
            ? {
                ...item,
                quantity: item.quantity - 1,
              }
            : item,
        ),
      )
    }

    setBooks((previousBooks) =>
      previousBooks.map((book) =>
        book.barcode === barcode
          ? {
              ...book,
              stock: book.stock + 1,
            }
          : book,
      ),
    )
  }

  const subtotal = useMemo(() => {
    return cart.reduce((accumulator, item) => {
      return accumulator + item.price * item.quantity
    }, 0)
  }, [cart])

  const total = useMemo(() => {
    return Math.max(subtotal - Number(discount || 0), 0)
  }, [subtotal, discount])

  const validateSale = () => {
    if (cart.length === 0) {
      alert("Le panier est vide")
      return
    }

    const newSale = {
      id: Date.now(),
      date: new Date().toLocaleString("fr-FR"),
      items: cart,
      paymentMethod,
      subtotal,
      discount,
      total,
    }

    setSales((previousSales) => [newSale, ...previousSales])

    setCart([])
    setDiscount(0)
  }

  const exportSales = () => {
    const rows = []

    sales.forEach((sale) => {
      sale.items.forEach((item) => {
        rows.push({
          date: sale.date,
          titre: item.title,
          isbn: item.barcode,
          quantite: item.quantity,
          prix_unitaire: item.price,
          paiement: sale.paymentMethod,
          remise: sale.discount,
          total: sale.total,
        })
      })
    })

    const csvContent = [
      Object.keys(rows[0] || {}).join(","),
      ...rows.map((row) => Object.values(row).join(",")),
    ].join("\n")

    const blob = new Blob([csvContent], {
      type: "text/csv;charset=utf-8;",
    })

    const link = document.createElement("a")

    link.href = URL.createObjectURL(blob)
    link.download = "ventes_conference.csv"

    link.click()
  }

  return (
    <div className="min-h-screen bg-slate-100 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2">
            Librairie - Gestion de Stand
          </h1>

          <p className="text-slate-600">
            Application de vente conférence avec scan code-barres
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <div className="bg-white rounded-3xl shadow-lg p-6">
            <h2 className="text-2xl font-semibold mb-4">
              Scanner un livre
            </h2>

            <input
              ref={inputRef}
              value={barcodeInput}
              onChange={(event) => setBarcodeInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  addBookToCart()
                }
              }}
              type="text"
              placeholder="Scanner ISBN / Code-barres"
              className="w-full border rounded-2xl p-4 mb-4"
            />

            <button
              onClick={addBookToCart}
              className="w-full bg-black text-white rounded-2xl p-4 hover:opacity-90"
            >
              Ajouter au panier
            </button>
          </div>

          <div className="bg-white rounded-3xl shadow-lg p-6">
            <h2 className="text-2xl font-semibold mb-4">Paiement</h2>

            <select
              value={paymentMethod}
              onChange={(event) => setPaymentMethod(event.target.value)}
              className="w-full border rounded-2xl p-4 mb-4"
            >
              <option>Carte Bancaire</option>
              <option>Espèces</option>
              <option>Chèque</option>
            </select>

            <input
              type="number"
              value={discount}
              onChange={(event) => setDiscount(event.target.value)}
              placeholder="Remise €"
              className="w-full border rounded-2xl p-4"
            />
          </div>

          <div className="bg-white rounded-3xl shadow-lg p-6 flex flex-col justify-center items-center">
            <div className="text-slate-500 mb-2">Sous-total</div>

            <div className="text-2xl font-semibold mb-4">
              {subtotal.toFixed(2)} €
            </div>

            <div className="text-slate-500 mb-2">Total final</div>

            <div className="text-5xl font-bold mb-6">
              {total.toFixed(2)} €
            </div>

            <button
              onClick={validateSale}
              className="bg-green-600 text-white px-6 py-4 rounded-2xl hover:opacity-90 w-full"
            >
              Valider la vente
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-6">
          <div className="bg-white rounded-3xl shadow-lg p-6 overflow-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-semibold">Panier</h2>

              <div className="text-sm text-slate-500">
                {cart.reduce((acc, item) => acc + item.quantity, 0)} article(s)
              </div>
            </div>

            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b text-left">
                  <th className="p-3">ISBN</th>
                  <th className="p-3">Titre</th>
                  <th className="p-3">Qté</th>
                  <th className="p-3">Prix</th>
                  <th className="p-3">Actions</th>
                </tr>
              </thead>

              <tbody>
                {cart.map((item) => (
                  <tr key={item.barcode} className="border-b">
                    <td className="p-3">{item.barcode}</td>
                    <td className="p-3">{item.title}</td>
                    <td className="p-3">{item.quantity}</td>
                    <td className="p-3">
                      {(item.quantity * item.price).toFixed(2)} €
                    </td>
                    <td className="p-3">
                      <button
                        onClick={() => removeBook(item.barcode)}
                        className="bg-red-500 text-white px-3 py-2 rounded-xl"
                      >
                        -1
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="bg-white rounded-3xl shadow-lg p-6 overflow-auto">
            <h2 className="text-2xl font-semibold mb-4">Stock Stand</h2>

            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b text-left">
                  <th className="p-3">Titre</th>
                  <th className="p-3">Prix</th>
                  <th className="p-3">Stock</th>
                </tr>
              </thead>

              <tbody>
                {books.map((book) => (
                  <tr key={book.barcode} className="border-b">
                    <td className="p-3">{book.title}</td>
                    <td className="p-3">{book.price.toFixed(2)} €</td>
                    <td
                      className={`p-3 font-semibold ${
                        book.stock <= 2 ? "text-red-600" : ""
                      }`}
                    >
                      {book.stock}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-white rounded-3xl shadow-lg p-6 overflow-auto">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-semibold">Historique ventes</h2>

            <button
              onClick={exportSales}
              className="bg-blue-600 text-white px-5 py-3 rounded-2xl hover:opacity-90"
            >
              Export CSV
            </button>
          </div>

          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b text-left">
                <th className="p-3">Date</th>
                <th className="p-3">Articles</th>
                <th className="p-3">Paiement</th>
                <th className="p-3">Remise</th>
                <th className="p-3">Total</th>
              </tr>
            </thead>

            <tbody>
              {sales.map((sale) => (
                <tr key={sale.id} className="border-b align-top">
                  <td className="p-3">{sale.date}</td>
                  <td className="p-3">
                    {sale.items.map((item) => (
                      <div key={item.barcode}>
                        {item.title} × {item.quantity}
                      </div>
                    ))}
                  </td>
                  <td className="p-3">{sale.paymentMethod}</td>
                  <td className="p-3">{sale.discount} €</td>
                  <td className="p-3 font-semibold">
                    {sale.total.toFixed(2)} €
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
