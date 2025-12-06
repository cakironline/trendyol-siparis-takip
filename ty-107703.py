import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np

# ----- Navbar ve CSS -----
st.markdown("""
<style>
.navbar {background-color:#f0f0f0;padding:10px;border-radius:8px;text-align:center;}
.navbar a {text-decoration:none;margin:0 20px;color:black;font-weight:600;}
.navbar a:hover {color:#ff6600;}
.store-card {border-radius:14px;box-shadow:0 3px 8px rgba(0,0,0,0.1);padding:15px;margin-bottom:25px;height:350px;display:flex;flex-direction:column;justify-content:flex-start;color:#222;}
.store-card h4 {text-align:center;font-weight:600;margin-bottom:10px;}
.store-table {flex-grow:1;overflow-y:auto;border-radius:8px;background-color:rgba(255,255,255,0.8);}
</style>
<div class="navbar">
        <a href="https://dgn-satis-takip-ddzwb2ys9nzk5p5fyddxbw.streamlit.app/" target="_blank">📈 DGN Satış Takip</a>
        <a href="https://urunler.streamlit.app/" target="_blank">💼 Ürün Yönetim</a>
        <a href="https://dgn-siparis-takip.streamlit.app/" target="_blank">📦 Sipariş Takip</a>
        <a href="https://trendyol-gecikme.streamlit.app/" target="_blank">🗓️ Trendyol Gecikme Takip</a>
        <a href="https://ty-dgn.streamlit.app/" target="_blank">🔰​ Trendyol Satış Takip</a>
        <a href="https://ty-kargotakip.streamlit.app/" target="_blank">🚚​ Trendyol Kargo Takip</a>
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

# ----- Depo sözlüğü -----
depo_dict = {
    "4216":"Ereğli","27005":"Karataş","27004":"Gazikent","6101":"Trabzon",
    "27003":"İpekyolu","4215":"Meram","46002":"Binevler","TOM":"TOM",
    "27001":"Sanko","4203":"Kampüs","46001":"Piazza","4200":"Merkez Ayakkabı",
    "4201":"Merkez Giyim","4210":"Novada","4214":"Fabrika Satış","46012":"Oniki Şubat",
    "27000":"Gazimuhtar","27002":"Suburcu","4207":"BosnaMix","4212":"Real",
    "4206":"Plus","M":"Aykent Depo","4202":"Sportive"
}

# Virgüllü mağaza listesi (YENİ)
onaylayabilecek_magazalar_str = ", ".join(depo_dict.values())

# ----- Hamurlabs API -----
HAMURLABS_URL = "http://dgn.hamurlabs.io/api/order/v2/search/"
HAMURLABS_HEADERS = {"Authorization":"Basic c2VsaW0uc2FyaWtheWE6NDMxMzQyNzhDY0A=","Content-Type":"application/json"}

def get_warehouse_code(tracker_code):
    payload = {"company_id":"1","updated_at__start":"2025-11-20 00:00:00",
               "updated_at__end": (datetime.now() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
               "size":100,"start":0,"shop_id":"","tracker_code":tracker_code,"order_types":["selling"]}
    try:
        r = requests.post(HAMURLABS_URL, headers=HAMURLABS_HEADERS, data=json.dumps(payload), timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("data"): 
                return tracker_code, data["data"][0].get("warehouse_code","")
    except Exception as e:
        st.warning(f"⚠️ Hamurlabs sorgusunda hata: {e}")
    return tracker_code, ""

def fetch_warehouse_codes_parallel(tracker_codes):
    warehouse_map = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(get_warehouse_code, code) for code in tracker_codes]
        for future in as_completed(futures):
            code, warehouse = future.result()
            warehouse_map[code] = warehouse
    return warehouse_map

def map_depo(kod_str):
    if pd.isna(kod_str) or kod_str=="": 
        return ""
    kod = kod_str.split(",")[0].strip()
    return depo_dict.get(kod,kod)

# ----- Trendyol Sipariş Fonksiyonu -----
def fetch_orders(seller_id, username, password):
    now=datetime.now()
    start_date=int((now-timedelta(days=14)).timestamp()*1000)
    end_date=int(now.timestamp()*1000)
    url=f"https://apigw.trendyol.com/integration/order/sellers/{seller_id}/orders"
    statuses=["Created","Picking","Invoiced"]; all_orders=[]
    for status in statuses:
        page=0
        while True:
            params={"status":status,"startDate":start_date,"endDate":end_date,
                    "orderByField":"PackageLastModifiedDate","orderByDirection":"DESC",
                    "size":200,"page":page}
            r = requests.get(url, auth=HTTPBasicAuth(username,password), params=params)
            data = r.json().get("content",[])
            if not data: break
            all_orders.extend(data); page+=1

    if not all_orders: 
        return pd.DataFrame(columns=["Sipariş No","Sipariş Tarihi","Kargoya Verilmesi Gereken Tarih",
                                     "Statü","FastDelivery","Barcode","ProductCode","Micro",
                                     "Fatura Durumu","Kargo Kodu","HB_SİP_NO","Durum",
                                     "Onaylayan Mağaza","Onaylayabilecek Mağazalar","Kargo Firması"])

    rows=[]
    for o in all_orders:
        lines=o.get("lines",[])
        barcodes=", ".join([str(l.get("barcode","")) for l in lines if l.get("barcode")])
        product_codes=", ".join([str(l.get("productCode","")) for l in lines if l.get("productCode")])
        invoice_link=o.get("invoiceLink","")
        fatura_durumu="Faturalı" if invoice_link else "Fatura Yüklü Değil"
        kargo_code=o.get("cargoTrackingNumber","")
        hb_sip_no=f"{o.get('id','')}_{o['orderNumber']}"
        rows.append({
            "HB_SİP_NO":hb_sip_no,
            "Sipariş No":o["orderNumber"],
            "Müşteri Adı":f"{o.get('customerFirstName','')} {o.get('customerLastName','')}".strip(),
            "Package ID":o.get("id",""),
            "Sipariş Tarihi":datetime.fromtimestamp(o["orderDate"]/1000),
            "Kargoya Verilmesi Gereken Tarih":datetime.fromtimestamp(o["agreedDeliveryDate"]/1000)+timedelta(hours=3),
            "Statü":o["status"],
            "FastDelivery":o.get("fastDelivery",False),
            "Barcode":barcodes,
            "ProductCode":product_codes,
            "Micro":o.get("micro",""),
            "Fatura Durumu":fatura_durumu,
            "Kargo Kodu":kargo_code,
            "Kargo Firması":o.get("cargoProviderName","")
        })

    df=pd.DataFrame(rows)

    now_guncel=datetime.now()+timedelta(hours=3)

    def durum_hesapla(row):
        kalan_saat=(row["Kargoya Verilmesi Gereken Tarih"]-now_guncel).total_seconds()/3600
        if kalan_saat<0: 
            toplam=-kalan_saat; gun=int(toplam//24); saat=int(toplam%24)
            return f"🔴 Gecikmede ({gun} Gün {saat} Saat)"
        elif kalan_saat<=2: return "🟠 2 Saat İçinde"
        elif kalan_saat<=4: return "🟡 4 Saat İçinde"
        elif kalan_saat<=6: return "🔵 6 Saat İçinde"
        elif kalan_saat<=12: return "🟣 12 Saat İçinde"
        elif kalan_saat<=24: return "🟢 24 Saat İçinde"
        else: return "✅ Süresi Var"

    df["Durum"]=df.apply(durum_hesapla, axis=1)

    df["Onaylayan Mağaza"]=""
    df["Onaylayabilecek Mağazalar"]=""

    return df

# ----- Hesap Sekmeleri -----
account_tabs = st.tabs(["🟥​ DGN-TRENDYOL","🟩​ DGNONLİNE-TRENDYOL"])

for i,(seller,user,pwd,hesap_adi) in enumerate([(SELLER_ID_1,USERNAME_1,PASSWORD_1,"DGN-TRENDYOL"),
                                                (SELLER_ID_2,USERNAME_2,PASSWORD_2,"DGNONLİNE-TRENDYOL")]):
    with account_tabs[i]:
        st.subheader(f"📦 {hesap_adi} Siparişleri")

        if st.button(f"🔄 Verileri Güncelle ({hesap_adi})"):
            df = fetch_orders(seller,user,pwd)

            gecikmis_idx = df[df["Durum"].str.contains("🔴 Gecikmede")].index

            if not gecikmis_idx.empty:
                tracker_codes = df.loc[gecikmis_idx,"HB_SİP_NO"].tolist()
                warehouse_map = fetch_warehouse_codes_parallel(tracker_codes)

                df.loc[gecikmis_idx,"Onaylayan Mağaza"] = df.loc[gecikmis_idx,"HB_SİP_NO"].map(
                    lambda x: map_depo(warehouse_map.get(x,""))
                )

            # ✅ YENİ EKLENTİ: Boş olanlara onaylayabilecek mağazaları yaz
            bos_idx = df["Onaylayan Mağaza"].isna() | (df["Onaylayan Mağaza"]=="")
            df.loc[bos_idx,"Onaylayabilecek Mağazalar"] = onaylayabilecek_magazalar_str

            st.session_state[f"data_{hesap_adi}"]=df
            st.success(f"{hesap_adi} verileri güncellendi ✅")

        if f"data_{hesap_adi}" in st.session_state:
            df = st.session_state[f"data_{hesap_adi}"]

            kategori_listesi=["🔴 Gecikmede","🟠 2 Saat İçinde","🟡 4 Saat İçinde","🔵 6 Saat İçinde",
                              "🟣 12 Saat İçinde","🟢 24 Saat İçinde","✅ Süresi Var"]

            tabs = st.tabs([f"{k} ({len(df[df['Durum'].str.contains(k)])})" for k in kategori_listesi])

            for j,kategori in enumerate(kategori_listesi):
                with tabs[j]:
                    df_k = df[df["Durum"].str.contains(kategori)].copy()

                    if df_k.empty:
                        st.info("Bu kategoride sipariş bulunmuyor.")
                        continue

                    df_k = df_k.sort_values(by="Sipariş Tarihi", ascending=True)
                    df_k.insert(0,"No", range(1,len(df_k)+1))
                    st.dataframe(df_k,height=800)
