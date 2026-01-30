import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import json
import copy
import os

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="Dashboard HIV Jabar",
    page_icon="🎗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. FUNGSI LOAD DATA (Caching & Path Fix)
# ==========================================
@st.cache_data
def load_data():
    # Coba baca file dari root atau folder
    file_path = "jumlah_kasus_hiv_berdasarkan_kelompok_umur_v1_data.csv"
    if not os.path.exists(file_path):
        file_path = "jabar-hiv-aids/odhiv_jabar_2022_clean.csv"
        
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
    else:
        st.error("File CSV tidak ditemukan. Pastikan file ada di folder yang benar.")
        return None
    
    # Standarisasi nama kota
    if 'nama_kabupaten_kota' in df.columns:
        df['nama_kabupaten_kota'] = df['nama_kabupaten_kota'].str.title()
    
    # Mapping Kategori Usia
    def kategori_usia(u):
        if u <= 14: return 'Anak-anak'
        elif u <= 24: return 'Remaja'
        elif u <= 49: return 'Dewasa'
        else: return 'Lansia'
    
    if 'kategori_usia' not in df.columns and 'umur' in df.columns:
        df['kategori_simple'] = df['umur'].apply(kategori_usia)
    elif 'kategori_usia' in df.columns:
        mapping = {
            '4 th ke bawah': 'Anak-anak', '5 - 14 th': 'Anak-anak',
            '15 - 19 th': 'Remaja', '20 - 24 th': 'Remaja',
            '25 - 49 th': 'Dewasa', '50 th ke atas': 'Lansia'
        }
        df['kategori_simple'] = df['kategori_usia'].map(mapping).fillna('Dewasa')
    else:
        df['kategori_simple'] = 'Dewasa' 
        
    return df

@st.cache_data
def load_geojson():
    file_path = "geo_jabar.json"
    if not os.path.exists(file_path):
        file_path = "jawa_barat_32_batas_kabkota.geojson"
        
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    else:
        st.error("File GeoJSON tidak ditemukan.")
        return None

# Load Data Awal
df = load_data()
geo_data_raw = load_geojson()

# ==========================================
# 3. FUNGSI LOGIKA (AI & PERHITUNGAN)
# ==========================================
def get_ai_clusters(df_input):
    agg = df_input.groupby('nama_kabupaten_kota')['jumlah_kasus'].sum().reset_index()
    if agg.empty: return {}, {}, {}

    q1 = agg['jumlah_kasus'].quantile(0.33)
    q2 = agg['jumlah_kasus'].quantile(0.66)
    
    colors, labels, scores = {}, {}, {}
    
    for _, row in agg.iterrows():
        kota = row['nama_kabupaten_kota']
        val = row['jumlah_kasus']
        scores[kota] = val
        
        if val <= q1:
            colors[kota] = '#2ecc71'
            labels[kota] = {'lbl': 'ZONA HIJAU', 'desc': 'Risiko Rendah'}
        elif val <= q2:
            colors[kota] = '#f1c40f'
            labels[kota] = {'lbl': 'ZONA KUNING', 'desc': 'Waspada'}
        else:
            colors[kota] = '#e74c3c'
            labels[kota] = {'lbl': 'ZONA MERAH', 'desc': 'Bahaya'}
    return colors, labels, scores

def calculate_status(df_all, city_scores, selected_city):
    if selected_city == 'SEMUA KAB/KOTA':
        if not city_scores: return {'lbl': 'N/A', 'c': '#ccc'}
        avg = df_all['jumlah_kasus'].sum() / len(city_scores)
        if avg > 500: return {'lbl': 'ZONA MERAH', 'desc': 'Provinsi: Bahaya', 'c': '#e74c3c'}
        elif avg > 200: return {'lbl': 'ZONA KUNING', 'desc': 'Provinsi: Waspada', 'c': '#f1c40f'}
        else: return {'lbl': 'ZONA HIJAU', 'desc': 'Provinsi: Terkendali', 'c': '#2ecc71'}
    else:
        # Ambil status dari dictionary labels yang sudah dihitung sebelumnya
        # Kita hitung ulang lokal saja untuk simplifikasi fungsi ini
        total = df_all[df_all['nama_kabupaten_kota'] == selected_city]['jumlah_kasus'].sum()
        # Logika threshold lokal (bisa disesuaikan)
        if total > 500: return {'lbl': 'ZONA MERAH', 'desc': 'Wilayah Bahaya', 'c': '#e74c3c'}
        elif total > 100: return {'lbl': 'ZONA KUNING', 'desc': 'Wilayah Waspada', 'c': '#f1c40f'}
        else: return {'lbl': 'ZONA HIJAU', 'desc': 'Wilayah Aman', 'c': '#2ecc71'}

def get_policy_advice(zona_label, demografi_dict, gender_filter):
    advice = []
    if 'MERAH' in zona_label:
        advice.append("🚨 <b>URGENT:</b> Wajib screening massal di titik panas.")
        advice.append("🏥 Stok ARV harus ditambah di RSUD setempat.")
    elif 'KUNING' in zona_label:
        advice.append("⚠️ Tingkatkan sosialisasi komunitas.")
        advice.append("🔍 Perluas tracing kontak erat.")
    else:
        advice.append("✅ Pertahankan edukasi di sekolah/tempat kerja.")
    
    if demografi_dict:
        max_cat = max(demografi_dict, key=demografi_dict.get)
        if max_cat == 'Remaja': advice.append("🎓 Masuk ke sekolah/kampus untuk edukasi seks.")
        elif max_cat == 'Dewasa': advice.append("🏢 Screening rutin di pabrik/kantor.")
        elif max_cat == 'Anak-anak': advice.append("👶 Cek penularan Ibu ke Anak (PPIA).")
        
    if gender_filter == 'Laki-laki': advice.append("👨 Kampanye pemakaian pengaman.")
    elif gender_filter == 'Perempuan': advice.append("👩 Fokus kesehatan reproduksi ibu.")
    return advice

# ==========================================
# 4. SIDEBAR & INTERAKSI (YANG DIPERBAIKI)
# ==========================================
if df is not None and geo_data_raw is not None:
    
    # --- INIT SESSION STATE ---
    if 'target_kota' not in st.session_state:
        st.session_state.target_kota = 'SEMUA KAB/KOTA'

    st.sidebar.header("🎛️ Filter Data")
    
    # Filter Tahun
    opt_th = ['SEMUA TAHUN'] + sorted(df['tahun'].unique(), reverse=True)
    th = st.sidebar.selectbox("📅 Tahun:", opt_th)
    
    # Filter Gender
    df['jenis_kelamin'] = df['jenis_kelamin'].fillna('Tidak Diketahui')
    opt_jk = ['SEMUA GENDER'] + sorted(df['jenis_kelamin'].unique().tolist())
    jk = st.sidebar.selectbox("👥 Gender:", opt_jk)
    
    # --- SYNC LOGIC: SELECTBOX ---
    opt_kt = ['SEMUA KAB/KOTA'] + sorted(df['nama_kabupaten_kota'].unique())
    
    # Callback jika user mengubah lewat Sidebar
    def on_sidebar_change():
        st.session_state.target_kota = st.session_state.widget_kota

    # Cari index list berdasarkan session state saat ini
    try:
        idx_sekarang = opt_kt.index(st.session_state.target_kota)
    except ValueError:
        idx_sekarang = 0 # Default ke Semua jika error

    # Selectbox dengan dynamic index
    st.sidebar.selectbox(
        "📍 Kabupaten/Kota:", 
        opt_kt, 
        index=idx_sekarang, 
        key='widget_kota', 
        on_change=on_sidebar_change
    )
    
    # Variabel utama untuk filtering
    kt = st.session_state.target_kota

    # --- PROSES FILTER DATA ---
    df_f = df.copy()
    if th != 'SEMUA TAHUN': df_f = df_f[df_f['tahun'] == th]
    if jk != 'SEMUA GENDER': df_f = df_f[df_f['jenis_kelamin'] == jk]

    # Hitung Statistik & AI
    colors, labels_data, city_scores = get_ai_clusters(df_f)
    
    # Data Aggregasi
    df_grp = df_f.groupby('nama_kabupaten_kota')['jumlah_kasus'].sum()
    df_det = df_f.pivot_table(index='nama_kabupaten_kota', columns='kategori_simple', values='jumlah_kasus', aggfunc='sum', fill_value=0)
    for c in ['Anak-anak', 'Remaja', 'Dewasa', 'Lansia']:
        if c not in df_det.columns: df_det[c] = 0

    # ==========================================
    # 5. RENDER PETA (DENGAN CLICK & TOOLTIP)
    # ==========================================
    st.title("Peta Persebaran Risiko HIV Jawa Barat")
    
    # Legenda Manual
    st.markdown('''
    <div style="font-size:14px; margin-bottom:10px;">
        <span style="color:#e74c3c;">■</span> Bahaya &nbsp;
        <span style="color:#f1c40f;">■</span> Waspada &nbsp;
        <span style="color:#2ecc71;">■</span> Aman
    </div>
    ''', unsafe_allow_html=True)

    # Siapkan GeoJSON
    geo_current = copy.deepcopy(geo_data_raw)
    for feature in geo_current['features']:
        k = feature['properties']['name'].title()
        val = df_grp.get(k, 0)
        c_zona = colors.get(k, '#95a5a6')
        lbl_zona = labels_data.get(k, {'lbl':'N/A'})['lbl']
        
        feature['properties']['fillColor'] = c_zona
        # TOOLTIP HTML
        feature['properties']['info'] = f"{k.upper()}: {val} Kasus ({lbl_zona})"

    # Style Function
    def style_fn(feature):
        k = feature['properties']['name'].title()
        base_color = feature['properties']['fillColor']
        # Highlight jika dipilih
        if kt != 'SEMUA KAB/KOTA' and k == kt:
            return {'fillColor': base_color, 'color': 'cyan', 'weight': 3, 'fillOpacity': 0.9}
        return {'fillColor': base_color, 'color': 'white', 'weight': 1, 'fillOpacity': 0.7}

    m = folium.Map(location=[-6.9175, 107.6191], zoom_start=9, tiles='CartoDB positron')
    
    folium.GeoJson(
        geo_current,
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(fields=['info'], labels=False)
    ).add_to(m)

    # Render Folium
    map_res = st_folium(m, width="100%", height=450)

    # --- LOGIKA KLIK PETA ---
    if map_res and map_res.get('last_active_drawing'):
        props = map_res['last_active_drawing'].get('properties', {})
        clicked_city = props.get('name', '').title()
        
        # Jika ada kota yg diklik DAN berbeda dengan yang sekarang -> Update & Rerun
        if clicked_city and clicked_city in opt_kt and clicked_city != st.session_state.target_kota:
            st.session_state.target_kota = clicked_city
            st.rerun()

    # ==========================================
    # 6. HTML LAPORAN (DIPISAH AGAR RAPI)
    # ==========================================
    
    # Siapkan Data Laporan
    if kt == 'SEMUA KAB/KOTA':
        judul = "PROVINSI JAWA BARAT"
        status = calculate_province_status(df_f, city_scores) # Fungsi helper baru jika perlu, atau gunakan logika manual
        # Kita pakai logika manual dr labels yg ada biar aman
        avg_prov = df_f['jumlah_kasus'].sum() / (len(city_scores) if city_scores else 1)
        if avg_prov > 500: status = {'lbl': 'ZONA MERAH', 'c': '#e74c3c', 'desc': 'Tingkat Provinsi: Bahaya'}
        elif avg_prov > 200: status = {'lbl': 'ZONA KUNING', 'c': '#f1c40f', 'desc': 'Tingkat Provinsi: Waspada'}
        else: status = {'lbl': 'ZONA HIJAU', 'c': '#2ecc71', 'desc': 'Tingkat Provinsi: Aman'}
            
        total_k = df_f['jumlah_kasus'].sum()
        row_dem = df_det.sum(axis=0)
    else:
        judul = kt.upper()
        # Ambil status dari dict yang sudah dihitung di awal
        status = labels_data.get(kt, {'lbl': 'DATA KOSONG', 'c': '#95a5a6', 'desc': 'Tidak ada data'})
        total_k = df_grp.get(kt, 0)
        row_dem = df_det.loc[kt] if kt in df_det.index else pd.Series({'Anak-anak':0, 'Remaja':0, 'Dewasa':0, 'Lansia':0})

    demografi_dict = row_dem.to_dict()
    rekomendasi = get_policy_advice(status['lbl'], demografi_dict, jk)

    # --- RENDER TAMPILAN LAPORAN (MENGGUNAKAN ST.COLUMNS UNTUK MENCEGAH RUSAK HTML) ---
    
    st.markdown("---")
    
    # 1. HEADER WARNA
    st.markdown(f"""
    <div style="background-color: {status['c']}; padding: 15px; border-radius: 8px 8px 0 0; color: white;">
        <h3 style="margin:0;">📊 LAPORAN: {judul}</h3>
        <p style="margin:0; opacity:0.9;">Total: {total_k:,.0f} Kasus | Status: <b>{status['lbl']}</b> ({status['desc']})</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. BODY LAPORAN (KOLOM)
    with st.container():
        # Buat container background putih
        c1, c2 = st.columns([1, 1])
        
        with c1:
            st.markdown("#### 📋 Data Demografi")
            
            # Render Tabel Manual agar style terkontrol
            table_html = f"""
            <table style="width:100%; border-collapse: collapse; font-size:14px;">
                <tr style="border-bottom:1px solid #ddd;"><td style="padding:8px;">Anak-anak</td><td style="text-align:right;"><b>{demografi_dict.get('Anak-anak',0):,.0f}</b></td></tr>
                <tr style="border-bottom:1px solid #ddd;"><td style="padding:8px;">Remaja</td><td style="text-align:right;"><b>{demografi_dict.get('Remaja',0):,.0f}</b></td></tr>
                <tr style="border-bottom:1px solid #ddd;"><td style="padding:8px;">Dewasa</td><td style="text-align:right;"><b>{demografi_dict.get('Dewasa',0):,.0f}</b></td></tr>
                <tr><td style="padding:8px;">Lansia</td><td style="text-align:right;"><b>{demografi_dict.get('Lansia',0):,.0f}</b></td></tr>
            </table>
            """
            st.markdown(table_html, unsafe_allow_html=True)
            
            # Top 5 Chart (Hanya jika Semua Kota)
            if kt == 'SEMUA KAB/KOTA':
                st.markdown("---")
                st.markdown("**🏆 5 Wilayah Tertinggi**")
                top5 = df_grp.sort_values(ascending=False).head(5)
                for city, val in top5.items():
                    st.progress(min(val / (top5.max()+1), 1.0), text=f"{city}: {val}")

        with c2:
            st.markdown("#### 💡 Rekomendasi Kebijakan")
            
            # Render Kotak Rekomendasi
            list_items = "".join([f"<li>{r}</li>" for r in rekomendasi])
            rec_html = f"""
            <div style="background-color:#fff3cd; border-left:5px solid #ffc107; padding:15px; border-radius:4px; color:#333;">
                <ul style="margin:0; padding-left:20px; line-height:1.6;">
                    {list_items}
                </ul>
            </div>
            """
            st.markdown(rec_html, unsafe_allow_html=True)

else:
    st.info("Sedang memuat data...")
