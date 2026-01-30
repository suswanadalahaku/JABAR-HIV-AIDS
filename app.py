import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import json
import copy

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
# 2. FUNGSI LOAD DATA (Caching)
# ==========================================
@st.cache_data
def load_data():
    # GANTI PATH INI SESUAI LOKASI FILE ANDA
    df = pd.read_csv("jabar-hiv-aids/odhiv_jabar_2022_clean.csv") 
    
    # Pastikan kolom sesuai
    if 'nama_kabupaten_kota' not in df.columns:
        st.error("Kolom 'nama_kabupaten_kota' tidak ditemukan.")
        return None
    
    # Standarisasi nama kota (Title Case)
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
        # Jika dataset sudah punya kategori, mapping ke simple
        mapping = {
            '4 th ke bawah': 'Anak-anak', '5 - 14 th': 'Anak-anak',
            '15 - 19 th': 'Remaja', '20 - 24 th': 'Remaja',
            '25 - 49 th': 'Dewasa', '50 th ke atas': 'Lansia'
        }
        # Gunakan map, jika tidak ada di map biarkan aslinya atau anggap Dewasa
        df['kategori_simple'] = df['kategori_usia'].map(mapping).fillna('Dewasa')
    else:
        df['kategori_simple'] = 'Dewasa' # Fallback
        
    return df

@st.cache_data
def load_geojson():
    # GANTI PATH INI SESUAI LOKASI FILE ANDA
    with open("jabar-hiv-aids/geo_jabar.json", "r") as f:
        return json.load(f)

# Load Data
df = load_data()
geo_data_raw = load_geojson()

# ==========================================
# 3. FUNGSI LOGIKA BISNIS (AI & PROSES)
# ==========================================
def get_ai_clusters(df_input):
    """Menghitung skor risiko berdasarkan jumlah kasus"""
    agg = df_input.groupby('nama_kabupaten_kota')['jumlah_kasus'].sum().reset_index()
    
    # Logika threshold sederhana (Rule-based AI)
    # Anda bisa mengganti ini dengan K-Means jika ada sklearn
    q1 = agg['jumlah_kasus'].quantile(0.33)
    q2 = agg['jumlah_kasus'].quantile(0.66)
    
    colors = {}
    labels = {}
    scores = {}
    
    for _, row in agg.iterrows():
        kota = row['nama_kabupaten_kota']
        val = row['jumlah_kasus']
        scores[kota] = val
        
        if val <= q1:
            colors[kota] = '#2ecc71' # Hijau
            labels[kota] = {'lbl': 'ZONA HIJAU', 'desc': 'Risiko Rendah'}
        elif val <= q2:
            colors[kota] = '#f1c40f' # Kuning
            labels[kota] = {'lbl': 'ZONA KUNING', 'desc': 'Waspada'}
        else:
            colors[kota] = '#e74c3c' # Merah
            labels[kota] = {'lbl': 'ZONA MERAH', 'desc': 'Bahaya'}
            
    return colors, labels, scores

def calculate_province_status(df_all, city_scores):
    total_kasus = df_all['jumlah_kasus'].sum()
    # Logika sederhana: rata-rata kasus per kota
    avg = total_kasus / len(city_scores)
    if avg > 500: return {'lbl': 'ZONA MERAH', 'desc': 'Tingkat Provinsi: Bahaya', 'c': '#e74c3c'}
    elif avg > 200: return {'lbl': 'ZONA KUNING', 'desc': 'Tingkat Provinsi: Waspada', 'c': '#f1c40f'}
    else: return {'lbl': 'ZONA HIJAU', 'desc': 'Tingkat Provinsi: Terkendali', 'c': '#2ecc71'}

def get_policy_advice(zona_label, demografi_dict, gender_filter):
    advice = []
    
    # 1. Berdasarkan Zona
    if 'MERAH' in zona_label:
        advice.append("🚨 <b>PRIORITAS TINGGI:</b> Wajib screening massal di hotspot populasi kunci.")
        advice.append("🏥 Tambah stok ARV di Puskesmas dan RSUD setempat segera.")
    elif 'KUNING' in zona_label:
        advice.append("⚠️ Tingkatkan sosialisasi pencegahan di komunitas berisiko.")
        advice.append("🔍 Perluas tracing kontak erat dari kasus yang ditemukan.")
    else:
        advice.append("✅ Pertahankan edukasi rutin sekolah dan tempat kerja.")
    
    # 2. Berdasarkan Demografi Dominan
    max_cat = max(demografi_dict, key=demografi_dict.get)
    if max_cat == 'Remaja':
        advice.append("🎓 <b>Fokus Remaja:</b> Integrasikan edukasi seks & HIV di kurikulum SMA/Kampus.")
    elif max_cat == 'Dewasa':
        advice.append("🏢 <b>Fokus Usia Produktif:</b> Program screening rutin di pabrik dan perkantoran.")
    elif max_cat == 'Anak-anak':
        advice.append("👶 <b>Perhatian Khusus:</b> Cek penularan vertikal (Ibu ke Anak), perkuat program PPIA.")
        
    # 3. Berdasarkan Gender
    if gender_filter == 'Laki-laki':
        advice.append("👨 Perkuat kampanye penggunaan pengaman dan tes rutin pria.")
    elif gender_filter == 'Perempuan':
        advice.append("👩 Fokus pada kesehatan reproduksi dan screening ibu hamil.")
        
    return advice

# ==========================================
# 4. SIDEBAR & PROSES FILTER
# ==========================================
if df is not None:
    st.sidebar.header("🎛️ Filter Data")
    
    # --- FILTER TAHUN & GENDER ---
    opt_th = ['SEMUA TAHUN'] + sorted(df['tahun'].unique(), reverse=True)
    th = st.sidebar.selectbox("📅 Tahun:", opt_th)
    
    # Handling data kosong untuk gender
    df['jenis_kelamin'] = df['jenis_kelamin'].fillna('Tidak Diketahui')
    opt_jk = ['SEMUA GENDER'] + sorted(df['jenis_kelamin'].unique().tolist())
    jk = st.sidebar.selectbox("👥 Gender:", opt_jk)
    
    # --- LOGIKA SINKRONISASI SELECTBOX & PETA (SOLUSI FIX SYNC) ---
    
    # 1. Pastikan state 'target_kota' ada
    if 'target_kota' not in st.session_state:
        st.session_state.target_kota = 'SEMUA KAB/KOTA'
    
    # 2. List opsi kota
    opt_kt = ['SEMUA KAB/KOTA'] + sorted(df['nama_kabupaten_kota'].unique())
    
    # 3. Callback: Saat user ubah Selectbox, update State utama
    def on_sidebar_change():
        st.session_state.target_kota = st.session_state.widget_kt_key

    # 4. Tentukan index awal Selectbox berdasarkan State saat ini
    try:
        current_index = opt_kt.index(st.session_state.target_kota)
    except ValueError:
        current_index = 0

    # 5. Render Selectbox
    # 'key' digunakan untuk widget ID, 'index' memastikannya sinkron dengan peta
    st.sidebar.selectbox(
        "📍 Kabupaten/Kota:", 
        opt_kt, 
        index=current_index,
        key='widget_kt_key', 
        on_change=on_sidebar_change
    )
    
    # 6. Variabel yang digunakan untuk filter logika di bawah
    kt = st.session_state.target_kota

    # --- FILTER DATAFRAME UTAMA ---
    df_f = df.copy()
    if th != 'SEMUA TAHUN': 
        df_f = df_f[df_f['tahun'] == th]
    if jk != 'SEMUA GENDER': 
        df_f = df_f[df_f['jenis_kelamin'] == jk]

    # --- HITUNG DATA ---
    colors, labels_data, city_scores = get_ai_clusters(df_f)
    
    # Agregasi untuk Peta & Grafik
    df_grp = df_f.groupby('nama_kabupaten_kota')['jumlah_kasus'].sum()
    
    # Agregasi Detail Usia (Pivot)
    df_det = df_f.pivot_table(
        index='nama_kabupaten_kota', 
        columns='kategori_simple', 
        values='jumlah_kasus', 
        aggfunc='sum', 
        fill_value=0
    )
    # Pastikan semua kolom ada
    for c in ['Anak-anak', 'Remaja', 'Dewasa', 'Lansia']: 
        if c not in df_det.columns: df_det[c] = 0

    # ==========================================
    # 5. PEMBUATAN PETA
    # ==========================================
    geo_current = copy.deepcopy(geo_data_raw)
    
    # Inject Data ke GeoJSON
    for feature in geo_current['features']:
        kota_nama = feature['properties']['name'].title()
        
        # Ambil data
        tot = df_grp.get(kota_nama, 0)
        risk_info = labels_data.get(kota_nama, {'lbl':'N/A', 'desc':''})
        warna_zona = colors.get(kota_nama, '#95a5a6')
        
        # HTML untuk Tooltip (Hover) - TETAP ADA
        html_hover = f"""
        <div style="font-family: sans-serif; width: 150px;">
            <div style="background:{warna_zona}; color:white; padding:4px 8px; font-weight:bold; font-size:12px;">
                {kota_nama.upper()}
            </div>
            <div style="padding:5px; font-size:11px; color:#333;">
                <b>{risk_info['lbl']}</b><br>
                Total: {tot:,.0f} Kasus
            </div>
        </div>
        """
        
        feature['properties']['fillColor'] = warna_zona
        feature['properties']['isi_tooltip'] = html_hover      

    # Fungsi Style Dinamis (Highlight yang dipilih)
    def style_function_dynamic(feature):
        kota_name = feature['properties']['name'].title()
        base = feature['properties']['fillColor']
        
        # Highlight kota yang sedang dipilih di state
        if st.session_state.target_kota != 'SEMUA KAB/KOTA' and kota_name.upper() == st.session_state.target_kota.upper():
            return {'fillColor': base, 'color': 'cyan', 'weight': 4, 'fillOpacity': 0.9, 'opacity': 1}
        
        return {'fillColor': base, 'color': 'white', 'weight': 1, 'fillOpacity': 0.7, 'opacity': 1}

    # Inisialisasi Peta
    sw, ne = [-8.0, 106.0], [-5.5, 109.0]
    m = folium.Map(location=[-6.9175, 107.6191], zoom_start=9, min_zoom=8, max_zoom=10, max_bounds=True, tiles='CartoDB positron')
    m.fit_bounds([sw, ne])

    # Render GeoJSON
    # PERBAIKAN: Hapus 'popup=...' agar tidak muncul balon saat diklik
    folium.GeoJson(
        geo_current, 
        style_function=style_function_dynamic, 
        tooltip=folium.GeoJsonTooltip(fields=['isi_tooltip'], labels=False), 
        # popup dihapus agar murni interaksi klik -> filter
    ).add_to(m)

    # ==========================================
    # 6. RENDER PETA & HTML LAPORAN
    # ==========================================
    
    st.title("Peta Persebaran Risiko HIV Jawa Barat")
    st.markdown('''
    <div style="font-family:sans-serif; font-size:14px; margin-bottom: 5px; font-weight:bold;">
        ZONA RISIKO &nbsp;&nbsp;&nbsp;
        <span style="color:#e74c3c;">■</span> Merah (Bahaya) &nbsp;&nbsp;
        <span style="color:#f1c40f;">■</span> Kuning (Waspada) &nbsp;&nbsp;
        <span style="color:#2ecc71;">■</span> Hijau (Risiko Rendah)
    </div>
    ''', unsafe_allow_html=True)
    
    # RENDER PETA
    # last_active_drawing akan menangkap data saat diklik meskipun popup dimatikan
    map_data = st_folium(m, width="100%", height=500)

    # LOGIKA KLIK PETA (MENGGANTI FILTER)
    if map_data and map_data.get('last_active_drawing'):
        properties = map_data['last_active_drawing'].get('properties', {})
        clicked_name = properties.get('name', '').title()
        
        # Jika nama valid DAN berbeda dari yang sekarang terpilih -> Update & Rerun
        if clicked_name in opt_kt and clicked_name != st.session_state.target_kota:
            st.session_state.target_kota = clicked_name
            st.rerun() # Refresh halaman agar Selectbox dan Dashboard terupdate

    # --- PERSIAPAN DATA LAPORAN ---
    
    # 1. Tentukan Data Statistik
    if kt == 'SEMUA KAB/KOTA':
        judul_lap = "JAWA BARAT (PROVINSI)"
        zona_stats = calculate_province_status(df_f, city_scores)
        tot_val = df_f['jumlah_kasus'].sum()
        
        # Sum semua detail
        r = df_det.sum(axis=0)
        det_val = {k: r.get(k, 0) for k in ['Anak-anak','Remaja','Dewasa','Lansia']}
        warna_header = zona_stats['c'] 
    else:
        judul_lap = kt.upper()
        zona_stats = labels_data.get(kt.title(), {'lbl':'N/A', 'desc':'', 'c':'#95a5a6'})
        tot_val = df_grp.get(kt.title(), 0)
        
        # Ambil detail kota spesifik
        if kt.title() in df_det.index:
            r = df_det.loc[kt.title()]
            det_val = r.to_dict()
        else:
            det_val = {'Anak-anak':0, 'Remaja':0, 'Dewasa':0, 'Lansia':0}
            
        warna_header = colors.get(kt.title(), "#95a5a6")

    # 2. Buat List Rekomendasi
    rekomendasi_list = get_policy_advice(zona_stats.get('lbl', ''), det_val, jk)
    
    # ==========================================
    # 7. KONSTRUKSI HTML (PERBAIKAN TAMPILAN)
    # ==========================================
    
    # Kita pisahkan pembuatan string HTML per bagian agar lebih aman dan tidak crash
    
    # A. Header
    html_header = f"""
    <div style="background-color: {warna_header}; color: white; padding: 15px; border-radius: 8px 8px 0 0;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h3 style="margin:0; font-family:Arial;">📊 LAPORAN: {judul_lap}</h3>
                <div style="font-size:13px; margin-top:5px; opacity:0.9;">FILTER GENDER: <b>{jk}</b></div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:11px; text-transform:uppercase; opacity:0.8;">STATUS RISIKO</div>
                <div style="font-size:18px; font-weight:bold;">{zona_stats.get('lbl')}</div>
                <div style="font-size:11px;">{zona_stats.get('desc')}</div>
            </div>
        </div>
        <hr style="border:0; border-top:1px solid rgba(255,255,255,0.3); margin:10px 0;">
        <div style="font-size:14px;">TOTAL KASUS: <b style="font-size:16px;">{tot_val:,.0f}</b> ORANG</div>
    </div>
    """

    # B. Tabel Demografi
    html_table = f"""
    <table style="width:100%; border-collapse: collapse; font-family: Arial; font-size: 13px; margin-top:10px; color:#333;">
        <tr style="background-color: #f8f9fa; color: #333;"><th style="border: 1px solid #ddd; padding: 8px; text-align: left;">KELOMPOK USIA</th><th style="border: 1px solid #ddd; padding: 8px; text-align: right;">JUMLAH KASUS</th></tr>
        <tr><td style="border: 1px solid #ddd; padding: 8px;">Anak-anak</td><td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{det_val.get('Anak-anak',0):,.0f}</td></tr>
        <tr><td style="border: 1px solid #ddd; padding: 8px;">Remaja</td><td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{det_val.get('Remaja',0):,.0f}</td></tr>
        <tr><td style="border: 1px solid #ddd; padding: 8px;">Dewasa</td><td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{det_val.get('Dewasa',0):,.0f}</td></tr>
        <tr><td style="border: 1px solid #ddd; padding: 8px;">Lansia</td><td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{det_val.get('Lansia',0):,.0f}</td></tr>
    </table>
    """

    # C. Rekomendasi Kebijakan (Looping Aman)
    items_html = ""
    for item in rekomendasi_list:
        items_html += f"<li style='margin-bottom:6px;'>{item}</li>"
    
    html_rekomendasi = f"""
    <div style="background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 15px; border-radius: 4px; margin-top:10px;">
        <b style="color:#856404; display:block; margin-bottom:8px;">💡 REKOMENDASI KEBIJAKAN</b>
        <div style="font-size: 13px; line-height: 1.5; color:#333;">
            <ul style="margin:0; padding-left:20px;">
                {items_html}
            </ul>
        </div>
    </div>
    """

    # D. Top 5 (Hanya jika Semua Kab/Kota)
    html_top5 = ""
    if kt == 'SEMUA KAB/KOTA':
        top5 = df_grp.sort_values(ascending=False).head(5)
        rows_top5 = ""
        max_v = top5.max() if not top5.empty else 1
        for c, v in top5.items():
            pct = (v/max_v)*100
            rows_top5 += f"<tr><td style='padding:5px; border-bottom:1px solid #eee;'>{c}</td><td style='padding:5px; text-align:right; border-bottom:1px solid #eee;'><b>{v}</b></td><td style='padding:5px; width:30%; border-bottom:1px solid #eee;'><div style='background:#3498db; width:{pct}%; height:6px; border-radius:3px;'></div></td></tr>"
        
        html_top5 = f"""
        <div style="margin-top:20px; border:1px solid #eee; padding:10px; border-radius:5px;">
            <b style="color:#555; font-size:12px;">🏆 5 WILAYAH TERTINGGI</b>
            <table style="width:100%; font-size:12px; margin-top:5px; border-collapse:collapse; color:#333;">
                {rows_top5}
            </table>
        </div>
        """

    # E. Gabungkan Semua dalam Container Utama
    final_html = f"""
    <div style="font-family: Arial, sans-serif; color:#333; background-color:white; border-radius:8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-top: 10px; overflow:hidden;">
        {html_header}
        <div style="padding: 20px; border: 1px solid #ddd; border-top:none; border-radius: 0 0 8px 8px; background-color:white;">
            <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 250px;">
                    <b style="color:#555; display:block; border-bottom:2px solid #eee; padding-bottom:5px;">📋 DATA DEMOGRAFI</b>
                    {html_table}
                    {html_top5} 
                </div>
                <div style="flex: 1; min-width: 250px;">
                    {html_rekomendasi}
                </div>
            </div>
        </div>
    </div>
    """
    
    st.markdown(final_html, unsafe_allow_html=True)

else:
    st.warning("Data belum berhasil dimuat.")
