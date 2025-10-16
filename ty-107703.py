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

st.write("API bağlantısı için bilgiler yüklendi ✅")

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
        return pd.DataFrame(columns=[
            "Sipariş No", "Sipariş Tarihi", "Kargoya Verilmesi Gereken Tarih",
            "Statü", "FastDelivery", "Barcode", "ProductCode", "Ürün Detayları"
        ])

    rows = []
    for o in all_orders:
        lines = o.get("lines", [])

        # Bir siparişte birden fazla ürün varsa, barcode ve productCode değerlerini virgülle birleştir
        barcodes = ", ".join([str(line.get("barcode", "")) for line in lines if line.get("barcode")])
        product_codes = ", ".join([str(line.get("productCode", "")) for line in lines if line.get("productCode")])

        # Ürün detayları (doğru alan adlarıyla)
        urun_detay = []
        for line in lines:
            urun_detay.append({
                "Barcode": line.get("barcode", ""),
                "ProductCode": line.get("productCode", ""),
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
            "FastDelivery": o.get("fastDelivery", False),
            "Barcode": barcodes,
            "ProductCode": product_codes,
            "Ürün Detayları": urun_detay
        })

    df = pd.DataFrame(rows)
    return df


# --- Verileri Güncelle ---
if st.button("🔄 Verileri Güncelle"):
    df = fetch_orders()
    st.session_state["data"] = df
    st.success("Veriler güncellendi ✅")


# --- Veri Gösterimi ---
if "data" in st.session_state:
    df = st.session_state["data"]
    now = datetime.now()

    def durum_hesapla(row):
        now_guncel = now + timedelta(hours=3)
        kalan_saat = (row["Kargoya Verilmesi Gereken Tarih"] - now_guncel).total_seconds() / 3600

        if kalan_saat < 0:
            toplam_saat = -kalan_saat
            gun = int(toplam_saat // 24)
            saat = int(toplam_saat % 24)
            dakika = int((toplam_saat - int(toplam_saat)) * 60)
            return f"🔴 Gecikmede ({gun} Gün {saat} Saat {dakika} Dakika)"
        elif kalan_saat <= 3:
            saat = int(kalan_saat)
            dakika = int((kalan_saat - saat) * 60)
            return f"🟠 3 Saat İçinde ({saat} Saat {dakika} Dakika)"
        elif kalan_saat <= 6:
            saat = int(kalan_saat)
            dakika = int((kalan_saat - saat) * 60)
            return f"🟡 6 Saat İçinde ({saat} Saat {dakika} Dakika)"
        elif kalan_saat <= 12:
            saat = int(kalan_saat)
            dakika = int((kalan_saat - saat) * 60)
            return f"🟢 12 Saat İçinde ({saat} Saat {dakika} Dakika)"
        else:
            saat = int(kalan_saat)
            dakika = int((kalan_saat - saat) * 60)
            return f"✅ Süresi Var ({saat} Saat {dakika} Dakika)"

    if not df.empty:
        df["Durum"] = df.apply(durum_hesapla, axis=1)
    else:
        st.info("API’den veri gelmedi veya hiç sipariş yok.")

    kategori_listesi = ["🔴 Gecikmede", "🟠 3 Saat İçinde", "🟡 6 Saat İçinde", "🟢 12 Saat İçinde", "✅ Süresi Var"]
    tabs = st.tabs([f"{k} ({len(df[df['Durum'].str.contains(k)])})" for k in kategori_listesi])

    def highlight_fast_delivery(row):
        if row["FastDelivery"]:
            return ['background-color: #b6fcb6']*len(row)
        else:
            return ['']*len(row)

    for i, kategori in enumerate(kategori_listesi):
        with tabs[i]:
            df_k = df[df["Durum"].str.contains(kategori)].copy()
            if not df_k.empty:
                df_k = df_k.sort_values(by="Sipariş Tarihi", ascending=True)
                df_k.insert(0, "No", range(1, len(df_k) + 1))

                # --- Detay butonlu görünüm ---
                for idx, row in df_k.iterrows():
                    with st.container(border=True):
                        c1, c2, c3, c4, c5 = st.columns([2, 2, 3, 3, 1])
                        c1.write(f"**No:** {idx+1}")
                        c2.write(f"**Sipariş No:** {row['Sipariş No']}")
                        c3.write(f"📅 {row['Sipariş Tarihi'].strftime('%d.%m.%Y %H:%M')}")
                        c4.write(f"{row['Durum']}")
                        if c5.button("➕ Detay", key=f"detay_{i}_{idx}"):
                            with st.modal(f"Sipariş {row['Sipariş No']} Ürün Detayları"):
                                st.write(f"### 🛍️ Ürünler")
                                detay_df = pd.DataFrame(row["Ürün Detayları"])
                                st.dataframe(detay_df, use_container_width=True)
                                st.button("Kapat", key=f"kapat_{i}_{idx}")
                st.divider()
            else:
                st.info("Bu kategoride sipariş bulunmuyor.")

else:
    st.info("Verileri görmek için yukarıdan 'Verileri Güncelle' butonuna tıklayın.")
