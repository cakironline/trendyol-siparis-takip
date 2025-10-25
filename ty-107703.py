import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

# ----- Navbar -----
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

# ----- Secrets -----
SELLER_ID_1 = st.secrets["SELLER_ID_1"]
USERNAME_1 = st.secrets["USERNAME_1"]
PASSWORD_1 = st.secrets["PASSWORD_1"]

SELLER_ID_2 = st.secrets["SELLER_ID_2"]
USERNAME_2 = st.secrets["USERNAME_2"]
PASSWORD_2 = st.secrets["PASSWORD_2"]

st.write("API bağlantısı için bilgiler yüklendi ✅")

# ----- Yeni Fonksiyon: Hamurlabs API (güncellenmiş payload) -----
def get_warehouse_status(order_id, order_number):
    """
    Hamurlabs API'den warehouse_code bilgisini alır.
    tracker_code = f"{order_id}_{order_number}"
    Eğer warehouse_code boşsa 'Onaylanmamış' döner.
    """
    url = "http://dgn.hamurlabs.io/api/order/status"
    headers = {
        "Authorization": "Basic c2VsaW0uc2FyaWtheWE6NDMxMzQyNzhDY0A=",
        "Content-Type": "application/json"
    }

    payload = {
        "company_id": "1",
        "updated_at__start": "2021-07-25 23:22:40",
        "updated_at__end": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "size": 1,
        "start": 0,
        "shop_id": "",
        "tracker_code": f"{order_id}_{order_number}",
        "order_types": ["selling"]
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            warehouse_code = data.get("warehouse_code") or "Onaylanmamış"
            return warehouse_code
        else:
            return "Onaylanmamış"
    except:
        return "Onaylanmamış"


# ----- Trendyol Sipariş Fonksiyonu -----
def fetch_orders(seller_id, username, password):
    now = datetime.now()
    start_date = int((now - timedelta(days=14)).timestamp() * 1000)
    end_date = int(now.timestamp() * 1000)

    url = f"https://apigw.trendyol.com/integration/order/sellers/{seller_id}/orders"
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
            r = requests.get(url, auth=HTTPBasicAuth(username, password), params=params)
            data = r.json().get("content", [])
            if not data:
                break
            all_orders.extend(data)
            page += 1

    if not all_orders:
        return pd.DataFrame(columns=[
            "Sipariş No", "Sipariş Tarihi", "Kargoya Verilmesi Gereken Tarih",
            "Statü", "FastDelivery", "Barcode", "ProductCode", "Micro", "Fatura Durumu", "Kargo Kodu", "Depo Durumu"
        ])

    rows = []
    for o in all_orders:
        lines = o.get("lines", [])
        barcodes = ", ".join([str(line.get("barcode", "")) for line in lines if line.get("barcode")])
        product_codes = ", ".join([str(line.get("productCode", "")) for line in lines if line.get("productCode")])
        micro_value = o.get("micro", "")
        invoice_link = o.get("invoiceLink", "")
        fatura_durumu = "Faturalı" if invoice_link else "Fatura Yüklü Değil"
        kargo_code = o.get("cargoTrackingNumber", "")

        # 👇 Yeni ekleme: Hamurlabs API'den depo durumu çek (güncellenmiş payload formatı ile)
        depo_durumu = get_warehouse_status(o.get("id", ""), o["orderNumber"])

        rows.append({
            "HB_SİP_NO": f"{o.get('id', '')}_{o['orderNumber']}",
            "Sipariş No": o["orderNumber"],
            "Müşteri Adı": f"{o.get('customerFirstName', '')} {o.get('customerLastName', '')}".strip(),
            "Package ID": o.get("id", ""),
            "Sipariş Tarihi": datetime.fromtimestamp(o["orderDate"]/1000),
            "Kargoya Verilmesi Gereken Tarih": datetime.fromtimestamp(o["agreedDeliveryDate"]/1000) + timedelta(hours=3),
            "Statü": o["status"],
            "FastDelivery": o.get("fastDelivery", False),
            "Barcode": barcodes,
            "ProductCode": product_codes,
            "Micro": micro_value,
            "Fatura Durumu": fatura_durumu,
            "Kargo Kodu": kargo_code,
            "Depo Durumu": depo_durumu  # 👈 Hamurlabs'tan gelen bilgi
        })

    return pd.DataFrame(rows)

# ----- Hesap Sekmeleri -----
account_tabs = st.tabs(["🟥​ DGN-TRENDYOL", "🟩​ DGNONLİNE-TRENDYOL"])

for i, (seller, user, pwd, hesap_adi) in enumerate([
    (SELLER_ID_1, USERNAME_1, PASSWORD_1, "DGN-TRENDYOL"),
    (SELLER_ID_2, USERNAME_2, PASSWORD_2, "DGNONLİNE-TRENDYOL")
]):
    with account_tabs[i]:
        st.subheader(f"📦 {hesap_adi} Siparişleri")

        if st.button(f"🔄 Verileri Güncelle ({hesap_adi})"):
            df = fetch_orders(seller, user, pwd)
            st.session_state[f"data_{hesap_adi}"] = df
            st.success(f"{hesap_adi} verileri güncellendi ✅")

        if f"data_{hesap_adi}" in st.session_state:
            df = st.session_state[f"data_{hesap_adi}"]
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
                    return f"🔵 6 Saat İçinde ({saat} Saat {dakika} Dakika)"
                elif kalan_saat <= 12:
                    saat = int(kalan_saat)
                    dakika = int((kalan_saat - saat) * 60)
                    return f"🟣 12 Saat İçinde ({saat} Saat {dakika} Dakika)"
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

            kategori_listesi = [
                "🔴 Gecikmede", "🟠 2 Saat İçinde", "🟡 4 Saat İçinde",
                "🔵 6 Saat İçinde", "🟣 12 Saat İçinde", "🟢 24 Saat İçinde", "✅ Süresi Var"
            ]

            tabs = st.tabs(
                [f"{k} ({len(df[df['Durum'].str.contains(k)])})" for k in kategori_listesi]
                + [f"📄 Faturası Yüklü Olmayan (Micro) ({len(df_faturasiz_micro)})"]
            )

            def highlight_fast_delivery(row):
                if row["FastDelivery"]:
                    return ['background-color: #b6fcb6'] * len(row)
                else:
                    return [''] * len(row)

            for j, kategori in enumerate(kategori_listesi):
                with tabs[j]:
                    df_k = df[df["Durum"].str.contains(kategori)].copy()
                    if not df_k.empty:
                        df_k = df_k.sort_values(by="Sipariş Tarihi", ascending=True)
                        df_k.insert(0, "No", range(1, len(df_k) + 1))
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
            st.info(f"{hesap_adi} için verileri görmek üzere 'Verileri Güncelle' butonuna tıklayın.")
