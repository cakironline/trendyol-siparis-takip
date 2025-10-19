import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

st.markdown("""
    <style>
    .navbar {
        background-color: #f0f0f0;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
    }
    .navbar a {
        text-decoration: none;
        margin: 0 20px;
        color: black;
        font-weight: 600;
    }
    .navbar a:hover {
        color: #ff6600;
    }
    </style>

    <div class="navbar">
        <a href="https://urunler.streamlit.app/" target="_blank">💼 Ürün Yönetim</a>
        <a href="https://dgn-satis-takip-ddzwb2ys9nzk5p5fyddxbw.streamlit.app/" target="_blank">📊 Satış Takip</a>
        <a href="https://dgn-siparis-takip.streamlit.app/" target="_blank">📦 Sipariş Takip</a>
        <a href="https://trendyol-gecikme.streamlit.app/" target="_blank">📦 Trendyol Gecikme Takip</a>
        
    </div>
""", unsafe_allow_html=True)

st.set_page_config(page_title="Trendyol Sipariş Takibi", layout="wide")
st.title("📦 Trendyol Kargo Gecikme Takip Paneli")

st.title("📦 Trendyol Kargo Gecikme Takip Paneli")

tabs_hesap = st.tabs(["🟠 Trendyol Hesap 1", "🔵 Trendyol Hesap 2"])

with tabs_hesap[0]:
    st.subheader("🟠 Hesap 1")
    if st.button("🔄 Hesap 1 Verilerini Güncelle"):
        df1 = fetch_orders(SELLER_ID_1, USERNAME_1, PASSWORD_1)
        st.session_state["data1"] = df1
        st.success("Hesap 1 verileri güncellendi ✅")

    if "data1" in st.session_state:
        df = st.session_state["data1"]
        # burada senin mevcut tablo ve kategori kodların (durum_hesapla, highlight vs)
        # olduğu gibi kalabilir

with tabs_hesap[1]:
    st.subheader("🔵 Hesap 2")
    if st.button("🔄 Hesap 2 Verilerini Güncelle"):
        df2 = fetch_orders(SELLER_ID_2, USERNAME_2, PASSWORD_2)
        st.session_state["data2"] = df2
        st.success("Hesap 2 verileri güncellendi ✅")

    if "data2" in st.session_state:
        df = st.session_state["data2"]
        # aynı tablo gösterim kısmı burada da


SELLER_ID_1 = "107703"
USERNAME_1 = st.secrets["USERNAME_1"]
PASSWORD_1 = st.secrets["PASSWORD_1"]

SELLER_ID_2 = "1054434"
USERNAME_2 = st.secrets["USERNAME_2"]
PASSWORD_2 = st.secrets["PASSWORD_2"]


st.write("API bağlantısı için bilgiler yüklendi ✅")

def fetch_orders(seller_id, username, password):
    now = datetime.now()
    start_date = int((now - timedelta(days=14)).timestamp() * 1000)
    end_date = int(now.timestamp() * 1000)

    url = f"https://apigw.trendyol.com/integration/order/sellers/{SELLER_ID}/orders"

    # --- TÜM STATÜLERİ ÇEKME ---
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
            "Statü", "FastDelivery", "Barcode", "ProductCode", "Micro", "Fatura Durumu", "Kargo Kodu"
        ])

    rows = []
    for o in all_orders:
        lines = o.get("lines", [])

        # Bir siparişte birden fazla ürün varsa, barcode ve productCode değerlerini virgülle birleştir
        barcodes = ", ".join([str(line.get("barcode", "")) for line in lines if line.get("barcode")])
        product_codes = ", ".join([str(line.get("productCode", "")) for line in lines if line.get("productCode")])

        # Yeni alanlar:
        micro_value = o.get("micro", "")  # Servisten gelen "micro"
        invoice_link = o.get("invoiceLink", "")  # Fatura linki
        fatura_durumu = "Faturalı" if invoice_link else "Fatura Yüklü Değil"
        kargo_code = o.get("cargoTrackingNumber", "")

        rows.append({
            "HB_SİP_NO": f"{o.get('id', '')}_{o['orderNumber']}",  # Yeni sütun
            "Sipariş No": o["orderNumber"],
            "Müşteri Adı": f"{o.get('customerFirstName', '')} {o.get('customerLastName', '')}".strip(),  # Ad Soyad birleşimi
            "Package ID": o.get("id", ""),  # shipmentPackageId,
            "Sipariş Tarihi": datetime.fromtimestamp(o["orderDate"]/1000),
            "Kargoya Verilmesi Gereken Tarih": datetime.fromtimestamp(o["agreedDeliveryDate"]/1000) + timedelta(hours=3),
            "Statü": o["status"],
            "FastDelivery": o.get("fastDelivery", False),
            "Barcode": barcodes,
            "ProductCode": product_codes,
            "Micro": micro_value,
            "Fatura Durumu": fatura_durumu,
            "Kargo Kodu":    kargo_code
            
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

        if kalan_saat < 0:  # Gecikmede
            toplam_saat = -kalan_saat
            gun = int(toplam_saat // 24)
            saat = int(toplam_saat % 24)
            dakika = int((toplam_saat - int(toplam_saat)) * 60)
            return f"🔴 Gecikmede ({gun} Gün {saat} Saat {dakika} Dakika)"
        elif kalan_saat <= 2:
            saat = int(kalan_saat)
            dakika = int((kalan_saat - saat) * 60)
            return f"🟠 2 Saat İçinde ({saat} Saat {dakika} Dakika)"
        elif kalan_saat <= 4:
            saat = int(kalan_saat)
            dakika = int((kalan_saat - saat) * 60)
            return f"🟡 4 Saat İçinde ({saat} Saat {dakika} Dakika)"
        elif kalan_saat <= 6:
            saat = int(kalan_saat)
            dakika = int((kalan_saat - saat) * 60)
            return f"🔵​ 6 Saat İçinde ({saat} Saat {dakika} Dakika)"
        elif kalan_saat <= 12:
            saat = int(kalan_saat)
            dakika = int((kalan_saat - saat) * 60)
            return f"🟣​ 12 Saat İçinde ({saat} Saat {dakika} Dakika)"
        elif kalan_saat <= 24:
            saat = int(kalan_saat)
            dakika = int((kalan_saat - saat) * 60)
            return f"🟢 24 Saat İçinde ({saat} Saat {dakika} Dakika)"
            
        else:
            saat = int(kalan_saat)
            dakika = int((kalan_saat - saat) * 60)
            return f"✅ Süresi Var ({saat} Saat {dakika} Dakika)"

    if not df.empty:
        df["Durum"] = df.apply(durum_hesapla, axis=1)
    else:
        st.info("API’den veri gelmedi veya hiç sipariş yok.")

     
    df_faturasiz_micro = df[(df["Fatura Durumu"] == "Fatura Yüklü Değil") & (df["Micro"] == True)]

    kategori_listesi = ["🔴 Gecikmede", "🟠 2 Saat İçinde", "🟡 4 Saat İçinde", "🔵​ 6 Saat İçinde", "🟣​ 12 Saat İçinde", "🟢 24 Saat İçinde", "✅ Süresi Var"]
    tabs = st.tabs(
        [f"{k} ({len(df[df['Durum'].str.contains(k)])})" for k in kategori_listesi]
        + [f"📄 Faturası Yüklü Olmayan (Micro) ({len(df_faturasiz_micro)})"]
    )    

    def highlight_fast_delivery(row):
        if row["FastDelivery"]:
            return ['background-color: #b6fcb6']*len(row)
        else:
            return ['']*len(row)

    for i, kategori in enumerate(kategori_listesi):
        with tabs[i]:
            df_k = df[df["Durum"].str.contains(kategori)].copy()
            if not df_k.empty:
                df_k = df_k.sort_values(by="Sipariş Tarihi", ascending=True)  # En eski → en yeni
                df_k.insert(0, "No", range(1, len(df_k) + 1))  # Sıra numarası ekle
                st.dataframe(df_k.style.apply(highlight_fast_delivery, axis=1))
            else:
                st.info("Bu kategoride sipariş bulunmuyor.")
    with tabs[-1]:
        if not df_faturasiz_micro.empty:
            df_faturasiz_micro = df_faturasiz_micro.sort_values(by="Sipariş Tarihi", ascending=True)
            df_faturasiz_micro.insert(0, "No", range(1, len(df_faturasiz_micro) + 1))
            st.dataframe(df_faturasiz_micro.style.apply(highlight_fast_delivery, axis=1))
        else:
            st.success("🎉 Tüm micro siparişlerin faturası yüklü görünüyor.")
else:
    st.info("Verileri görmek için yukarıdan 'Verileri Güncelle' butonuna tıklayın.")
