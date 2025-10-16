import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

st.set_page_config(page_title="Trendyol Sipariş Takibi", layout="wide")
st.title("📦 Trendyol Kargo Gecikme Takip Paneli")

SELLER_ID = "107703"
USERNAME = st.secrets["USERNAME"]
PASSWORD = st.secrets["PASSWORD"]

def fetch_orders():
    now = datetime.now()
    start_date = int((now - timedelta(days=14)).timestamp() * 1000)
    end_date = int(now.timestamp() * 1000)

    url = f"https://apigw.trendyol.com/integration/order/sellers/{SELLER_ID}/orders"
    statuses = ["Created", "Picking", "Invoiced"]
    all_orders = []

    for status in statuses:
        page = 0
        while True:
            params = {
                "status": status,
                "startDate": start_date,
                "endDate": end_date,
                "orderByField": "PackageLastModifiedDate",
                "orderByDirection": "DESC",
                "size": 200,
                "page": page
            }
            r = requests.get(url, auth=HTTPBasicAuth(USERNAME, PASSWORD), params=params)
            data = r.json().get("content", [])
            if not data:
                break
            all_orders.extend(data)
            page += 1

    if not all_orders:
        return pd.DataFrame()

    rows = []
    for o in all_orders:
        lines = o.get("lines", [])
        barcodes = ", ".join([str(line.get("barcode", "")) for line in lines])
        product_codes = ", ".join([str(line.get("productCode", "")) for line in lines])

        urun_detay = []
        for line in lines:
            urun_detay.append({
                "Barcode": line.get("barcode", ""),
                "Ürün Adı": line.get("productName", ""),
                "Beden": line.get("productSize", ""),
                "Renk": line.get("productColor", ""),
                "Adet": line.get("quantity", 1)
            })

        rows.append({
            "Sipariş No": o["orderNumber"],
            "Sipariş Tarihi": datetime.fromtimestamp(o["orderDate"]/1000),
            "Kargoya Verilmesi Gereken Tarih": datetime.fromtimestamp(o["agreedDeliveryDate"]/1000) + timedelta(hours=3),
            "Statü": o["status"],
            "Barcode": barcodes,
            "ProductCode": product_codes,
            "Ürün Detayları": urun_detay
        })

    return pd.DataFrame(rows)

# --- Verileri Getir ---
if st.button("🔄 Verileri Güncelle"):
    df = fetch_orders()
    st.session_state["data"] = df
    st.success("Veriler güncellendi ✅")

if "data" in st.session_state:
    df = st.session_state["data"]
    now = datetime.now()

    def durum_hesapla(row):
        now_guncel = now + timedelta(hours=3)
        kalan_saat = (row["Kargoya Verilmesi Gereken Tarih"] - now_guncel).total_seconds() / 3600
        if kalan_saat < 0:
            return "🔴 Gecikmede"
        elif kalan_saat <= 3:
            return "🟠 3 Saat İçinde"
        elif kalan_saat <= 6:
            return "🟡 6 Saat İçinde"
        elif kalan_saat <= 12:
            return "🟢 12 Saat İçinde"
        else:
            return "✅ Süresi Var"

    df["Durum"] = df.apply(durum_hesapla, axis=1)

    # --- Tabloyu Göster (Detay butonuyla birlikte) ---
    st.write("### 📋 Sipariş Listesi")

    for idx, row in df.iterrows():
        col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 3, 3, 3, 1])
        col1.write(f"**Sipariş No:** {row['Sipariş No']}")
        col2.write(row["Statü"])
        col3.write(row["Sipariş Tarihi"].strftime("%d.%m.%Y %H:%M"))
        col4.write(row["Kargoya Verilmesi Gereken Tarih"].strftime("%d.%m.%Y %H:%M"))
        col5.write(row["Durum"])
        if col6.button("➕", key=f"detay_{idx}"):
            st.session_state["popup_row"] = row

    # --- Popup Gösterimi ---
    if "popup_row" in st.session_state:
        popup = st.session_state["popup_row"]
        with st.modal(f"Sipariş {popup['Sipariş No']} Detayları"):
            st.write(f"### 🛍️ Ürün Detayları")
            detay_df = pd.DataFrame(popup["Ürün Detayları"])
            st.dataframe(detay_df, use_container_width=True)
            st.button("Kapat", key="kapat", on_click=lambda: st.session_state.pop("popup_row"))
else:
    st.info("Verileri görmek için 'Verileri Güncelle' butonuna tıklayın.")
