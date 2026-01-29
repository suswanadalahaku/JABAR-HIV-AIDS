import streamlit as st
import pandas as pd
import json
import folium
import copy
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from streamlit_folium import st_folium

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(layout="wide", page_title="Dashboard HIV Jabar")

# ==========================================
# 2. LOAD DATA
# ==========================================
@st.cache_data
def load_data():
    try:
        df = pd.read_csv('jumlah_kasus_hiv_berdasarkan_kelompok_umur_v1_data.csv')
        with open('jawa_barat_32_batas_kabkota.geojson', 'r') as f:
            geo_data_raw = json.load(f)
        
        # Cleaning
        df['jumlah_kasus'] = pd.to_numeric(df['jumlah_kasus'], errors='coerce').fillna(0)
        df['nama_kabupaten_kota'] = df['nama_kabupaten_kota'].str.title()
        df['jenis_kelamin'] = df['jenis_kelamin'].str.upper()

        def simple_cat(x):
            if x in ['0-4', '5-14']: return 'Anak-anak'
            elif x in ['15-19', '20-24']: return 'Remaja'
            elif x in ['25-49']: return 'Dewasa'
            else: return 'Lansia'
        df['kategori_simple'] = df['kelompok_umur'].apply(simple_cat)
        
        return df, geo_data_raw
    except Exception as e:
        st.error(f"Error Loading Data: {e}")
        return None, None

df, geo_data_raw = load_data()

# ==========================================
# 3. FUNGSI LOGIKA (AI & STATUS)
# ==========================================
def get_ai_clusters(df_input):
    if df_input.empty: return {}, {}, {} 
    
    df_p = df_input.pivot_table(index='nama_kabupaten_kota', columns='kategori_simple', values='jumlah_kasus', aggfunc='sum', fill_value=0)
    if len(df_p) < 3: return {}, {}, {}
    
    scaler = StandardScaler()
    X = scaler.fit_transform(df_p)
    km = KMeans(n_clusters=3, random_state=42, n_init=10)
    df_p['cluster'] = km.fit_predict(X)
    df_p['total'] = df_p.sum(axis=1)

    rank = df_p.groupby('cluster')['total'].mean().sort_values().index
    
    cmap = {
        rank[0]: {'c':'#2ecc71', 'lbl':'ZONA HIJAU', 'desc':'Risiko Rendah', 'score': 1},
        rank[1]: {'c':'#f1c40f', 'lbl':'ZONA KUNING', 'desc':'Waspada', 'score': 2},
        rank[2]: {'c':'#e74c3c', 'lbl':'ZONA MERAH', 'desc':'Bahaya', 'score': 3}
    }
    
    colors, labels, city_scores = {}, {}, {}
    for kota, row in df_p.iterrows():
        clust_id = row['cluster']
        colors[kota] = cmap[clust_id]['c']
        labels[kota] = cmap[clust_id]
        city_scores[kota] = cmap[clust_id]['score']
        
    return colors, labels, city_scores

def calculate_province_status(df_filtered, city_scores):
    kota_totals = df_filtered.groupby('nama_kabupaten_kota')['jumlah_kasus'].sum()
    total_kasus_provinsi = kota_totals.sum()
    
    if total_kasus_provinsi == 0:
        return {'lbl':'ZONA HIJAU', 'desc':'Tidak Ada Kasus', 'c':'#2ecc71'}

    weighted_score = 0
    for kota, total in kota_totals.items():
        score = city_scores.get(kota, 1) 
        weighted_score += (score * total)
    
    avg_risk_index = weighted_score / total_kasus_provinsi
    
    if avg_risk_index >= 2.2:
        return {'lbl':'ZONA MERAH', 'desc':'Bahaya', 'c':'#e74c3c'}
    elif avg_risk_index >= 1.6:
        return {'lbl':'ZONA KUNING', 'desc':'Waspada', 'c':'#f1c40f'}
    else:
        return {'lbl':'ZONA HIJAU', 'desc':'Risiko Rendah', 'c':'#2ecc71'}

def get_policy_advice(zona_label, data_usia, filter_gender):
    advice = []
    if zona_label == 'ZONA MERAH':
        advice.append("<b>🚨 DARURAT:</b> Eskalasi kasus tinggi. Perlu audit stok ARV.")
        advice.append("<b>🏥 FASKES:</b> Skrining wajib pasien rawat inap.")
    elif zona_label == 'ZONA KUNING':
        advice.append("<b>⚠️ WASPADA:</b> Tren naik. Perkuat supervisi.")
        advice.append("<b>📢 KAMPANYE:</b> Sosialisasi masif via medsos.")
    else:
        advice.append("<b>✅ MONITORING:</b> Pertahankan kondisi. Fokus edukasi.")

    if data_usia['Anak-anak'] > 0: advice.append("<b>👶 ANAK:</b> Prioritas Triple Eliminasi.")
    if data_usia['Remaja'] > 50: advice.append("<b>🎓 REMAJA:</b> Masukkan modul kesehatan di sekolah.")

    if filter_gender == 'LAKI-LAKI': advice.append("<b>♂️ LAKI-LAKI:</b> Fokus komunitas pekerja.")
    elif filter_gender == 'PEREMPUAN': advice.append("<b>♀️ PEREMPUAN:</b> Fokus via Posyandu/PKK.")
        
    return advice

# ==========================================
# 4. SIDEBAR MENU
# ==========================================
if df is not None:
    st.sidebar.header("🎛️ Filter Data")
    
    opt_th = ['SEMUA TAHUN'] + sorted(df['tahun'].unique(), reverse=True)
    th = st.sidebar.selectbox("Pilih Tahun:", opt_th)
    
    opt_jk = ['SEMUA GENDER'] + sorted(df['jenis_kelamin'].unique().tolist())
    jk = st.sidebar.selectbox("Pilih Gender:", opt_jk)
    
    opt_kt = ['SEMUA KAB/KOTA'] + sorted(df['nama_kabupaten_kota'].unique())
    kt = st.sidebar.selectbox("Highlight Wilayah:", opt_kt)

    # --- FILTER DATA ---
    df_f = df.copy()
    if th != 'SEMUA TAHUN': df_f = df_f[df_f['tahun'] == th]
    if jk != 'SEMUA GENDER': df_f = df_f[df_f['jenis_kelamin'] == jk]

    colors, labels_data, city_scores = get_ai_clusters(df_f)
    
    df_grp = df_f.groupby('nama_kabupaten_kota')['jumlah_kasus'].sum()
    df_det = df_f.pivot_table(index='nama_kabupaten_kota', columns='kategori_simple', values='jumlah_kasus', aggfunc='sum', fill_value=0)
    for c in ['Anak-anak', 'Remaja', 'Dewasa', 'Lansia']: 
        if c not in df_det.columns: df_det[c] = 0

    # ==========================================
    # 5. GENERATE PETA (VERSI FIX POPUP/TOOLTIP)
    # ==========================================
    
    # Inisialisasi Peta
    m = folium.Map(location=[-6.9175, 107.6191], zoom_start=8, tiles='CartoDB positron')

    geo_current = copy.deepcopy(geo_data_raw)
    
    # Loop manual setiap fitur agar Tooltip dan Popup bisa dikontrol terpisah
    for feature in geo_current['features']:
        kota = feature['properties']['name'].title()
        tot = df_grp.get(kota, 0)
        risk_info = labels_data.get(kota, {'lbl':'N/A', 'desc':''})
        base_color = colors.get(kota, '#95a5a6')
        
        # 1. STYLE (Warna Wilayah)
        # Jika kota dipilih di filter highlight, beri border Cyan tebal
        def get_style(feature, kota_name=kota, color=base_color, highlight=kt):
            weight = 1
            border_color = 'white'
            opacity = 0.7
            if highlight != 'SEMUA KAB/KOTA' and kota_name.upper() == highlight.upper():
                weight = 4
                border_color = 'cyan'
                opacity = 0.9
            return {'fillColor': color, 'color': border_color, 'weight': weight, 'fillOpacity': opacity}

        # 2. ISI POPUP (HTML Table saat di-KLIK)
        # Penting: Kita bungkus div dengan background-color: white dan color: black 
        # agar tidak bentrok dengan Dark Mode Streamlit.
        r = df_det.loc[kota] if kota in df_det.index else pd.Series({'Anak-anak':0, 'Remaja':0, 'Dewasa':0, 'Lansia':0})
        
        popup_html = f"""
        <div style="font-family: Arial; width: 200px; background-color: white; color: #333; padding: 5px; border-radius: 5px;">
            <h4 style="margin: 0 0 5px 0; color: black;">{kota.upper()}</h4>
            <div style="font-size: 12px; margin-bottom: 5px;">
                <b>{risk_info.get('lbl')}</b><br>
                Total Kasus: <b>{tot:,.0f}</b>
            </div>
            <hr style="margin: 5px 0; border: 0; border-top: 1px solid #ddd;">
            <table style="width:100%; font-size:11px; border-collapse: collapse; color: #333;">
                <tr style="border-bottom:1px solid #eee;"><td>Anak</td><td align="right"><b>{r['Anak-anak']}</b></td></tr>
                <tr style="border-bottom:1px solid #eee;"><td>Remaja</td><td align="right"><b>{r['Remaja']}</b></td></tr>
                <tr style="border-bottom:1px solid #eee;"><td>Dewasa</td><td align="right"><b>{r['Dewasa']}</b></td></tr>
                <tr><td>Lansia</td><td align="right"><b>{r['Lansia']}</b></td></tr>
            </table>
        </div>
        """
        
        # 3. TOOLTIP (Hanya Teks saat HOVER)
        tooltip_text = f"{kota}: {risk_info.get('lbl')} (Total: {tot})"

        # 4. Tambahkan ke Peta
        gj = folium.GeoJson(
            feature,
            style_function=lambda x, style=get_style(feature): style,
            tooltip=tooltip_text 
        )
        
        # Attach Popup HTML yang sudah dirender
        folium.Popup(popup_html, max_width=250).add_to(gj)
        gj.add_to(m)

    # ==========================================
    # 6. TAMPILAN LAYOUT
    # ==========================================
    
    if kt == 'SEMUA KAB/KOTA':
        judul_lap = "JAWA BARAT (PROVINSI)"
        prov_status = calculate_province_status(df_f, city_scores)
        zona_stats = prov_status 
        tot_val = df_f['jumlah_kasus'].sum()
        r = df_f.pivot_table(columns='kategori_simple', values='jumlah_kasus', aggfunc='sum').iloc[0] if not df_f.empty else pd.Series()
        det_val = {k: r.get(k, 0) for k in ['Anak-anak','Remaja','Dewasa','Lansia']}
        warna_header = prov_status['c'] 
    else:
        judul_lap = kt.upper()
        zona_stats = labels_data.get(kt.title(), {'lbl':'N/A', 'desc':''})
        tot_val = df_grp.get(kt.title(), 0)
        r = df_det.loc[kt.title()] if kt.title() in df_det.index else pd.Series({'Anak-anak':0, 'Remaja':0, 'Dewasa':0, 'Lansia':0})
        det_val = r.to_dict()
        warna_header = colors.get(kt.title(), "#95a5a6")

    rekomendasi = get_policy_advice(zona_stats.get('lbl'), det_val, jk)
    list_rek = "".join([f"<li style='margin-bottom:5px;'>{x}</li>" for x in rekomendasi])

    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.subheader("🗺️ Peta Persebaran Risiko")
        st.caption("Arahkan mouse untuk info singkat, Klik wilayah untuk detail umur.")
        st.markdown("""
        <div style="padding:10px; background:#f8f9fa; border:1px solid #ddd; border-radius:5px; font-size:12px; margin-bottom:10px; color:black;">
            <span style="color:#e74c3c;">■</span> Merah (Bahaya) &nbsp;|&nbsp;
            <span style="color:#f1c40f;">■</span> Kuning (Waspada) &nbsp;|&nbsp;
            <span style="color:#2ecc71;">■</span> Hijau (Risiko Rendah)
        </div>
        """, unsafe_allow_html=True)
        st_folium(m, width="100%", height=500)

    with col2:
        # Card HTML dipaksa background putih agar kontras aman di Dark Mode
        html_card = f"""
        <div style="font-family: sans-serif; border: 1px solid #ddd; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); background-color: white; color: #333;">
            <div style="background-color: {warna_header}; color: white; padding: 15px;">
                <h3 style="margin:0; font-size:18px;">{judul_lap}</h3>
                <p style="margin:5px 0 0; opacity:0.9; font-size:14px;">Total Kasus: <b>{tot_val:,.0f}</b></p>
                <div style="margin-top:10px; background:rgba(255,255,255,0.2); padding:5px 10px; border-radius:5px; display:inline-block;">
                    <b>{zona_stats.get('lbl')}</b><br>
                    <small>{zona_stats.get('desc')}</small>
                </div>
            </div>
            <div style="padding: 15px;">
                <b style="color:#555;">📊 Demografi Usia:</b>
                <table style="width:100%; font-size:13px; margin-top:5px; border-collapse: collapse; color: #333;">
                    <tr style="border-bottom:1px solid #eee;"><td>Anak-anak</td><td align="right"><b>{det_val['Anak-anak']:,.0f}</b></td></tr>
                    <tr style="border-bottom:1px solid #eee;"><td>Remaja</td><td align="right"><b>{det_val['Remaja']:,.0f}</b></td></tr>
                    <tr style="border-bottom:1px solid #eee;"><td>Dewasa</td><td align="right"><b>{det_val['Dewasa']:,.0f}</b></td></tr>
                    <tr><td>Lansia</td><td align="right"><b>{det_val['Lansia']:,.0f}</b></td></tr>
                </table>
                <br>
                <div style="background-color: #fff8e1; border-left: 4px solid #f1c40f; padding: 10px; color: #d35400;">
                    <b>💡 Rekomendasi:</b>
                    <ul style="padding-left:20px; margin:5px 0 0; font-size:13px;">{list_rek}</ul>
                </div>
            </div>
        </div>
        """
        st.markdown(html_card, unsafe_allow_html=True)

else:
    st.warning("Data belum dimuat. Pastikan file CSV dan GeoJSON ada di folder yang sama.")
