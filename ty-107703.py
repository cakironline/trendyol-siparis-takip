import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.colors as mcolors
import numpy as np

st.set_page_config(page_title="Sipariş Takip", layout="wide")

# --- Veri yükleme ---
uploaded_file = st.file_uploader("Excel dosyasını yükle (.xlsx)", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # --- Tarih dönüştürme ve filtreleme ---
    if "Kargoya Verilme Tarihi" in df.columns:
        df["Kargoya Verilme Tarihi"] = pd.to_datetime(df["Kargoya Verilme Tarihi"], errors="coerce")

    # --- Filtreler ---
    kategori = st.radio("Kategori Seçin:", ["🟢 Tamamlandı", "🟡 Beklemede", "🔴 Gecikmede"], horizontal=True)

    bugun = datetime.now()
    df["Durum"] = "🟡 Beklemede"
    df.loc[df["Kargoya Verilme Tarihi"].notna(), "Durum"] = "🟢 Tamamlandı"
    df.loc[df["Tahmini Teslim Tarihi"] < bugun, "Durum"] = "🔴 Gecikmede"

    df_k = df[df["Durum"] == kategori]

    st.markdown(f"### {kategori} Siparişler")
    st.dataframe(df_k, use_container_width=True, height=800)

    # --- Gecikmede tabına özel mağaza bazlı kartlar ---
    if kategori == "🔴 Gecikmede" and not df_k.empty:
        st.markdown("### 🏬 Onaylayan Mağazalara Göre Gecikmedeki Siparişler")

        # Boş olmayan mağazaları al ve adetlerine göre sırala
        magazalar = (
            df_k["Onaylayan Mağaza"]
            .dropna()
            .value_counts()
            .reset_index()
            .rename(columns={"index": "Mağaza", "Onaylayan Mağaza": "Adet"})
        )

        if not magazalar.empty:
            # Renk skalası (en çoktan aza doğru)
            max_count = magazalar["Adet"].max()
            min_count = magazalar["Adet"].min()
            cmap = mcolors.LinearSegmentedColormap.from_list("", ["#8B0000", "#FFB3B3"])  # koyu kırmızı → açık ton

            # 3’lü grid düzeninde kartları göster
            for i in range(0, len(magazalar), 3):
                cols = st.columns(3)
                for col, row in zip(cols, magazalar.iloc[i:i+3].itertuples()):
                    magaza = row.Mağaza
                    adet = row.Adet
                    df_magaza = df_k[df_k["Onaylayan Mağaza"] == magaza][["HB_SİP_NO", "Müşteri Adı", "Kargo Kodu"]]

                    # Renk hesaplama (adet sayısına göre ton)
                    ratio = 0 if max_count == min_count else (adet - min_count) / (max_count - min_count)
                    hex_color = mcolors.to_hex(cmap(1 - ratio))  # çok adet → koyu ton

                    # Kart yapısı
                    with col:
                        st.markdown(
                            f"""
                            <div style="
                                background-color:{hex_color};
                                border-radius:16px;
                                padding:14px;
                                margin-bottom:10px;
                                box-shadow:0 4px 10px rgba(0,0,0,0.15);
                                height:400px;
                                overflow:hidden;
                            ">
                                <h4 style="color:white; text-align:center; margin-bottom:10px;">
                                    🏬 {magaza} ({adet})
                                </h4>
                                <div style="background-color:white; border-radius:10px; padding:6px; height:320px; overflow:auto;">
                            """,
                            unsafe_allow_html=True,
                        )

                        st.dataframe(df_magaza, use_container_width=True, hide_index=True, height=290)

                        st.markdown("</div></div>", unsafe_allow_html=True)
        else:
            st.info("Henüz 'Onaylayan Mağaza' bilgisi bulunmuyor.")
else:
    st.info("Lütfen bir Excel dosyası yükleyin.")
