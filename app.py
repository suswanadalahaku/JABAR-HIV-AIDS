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

st.markdown("""
<style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    /* Mempercantik tampilan font global */
    html, body, [class*="css"] {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
</style>
""", unsafe_allow_html=True)

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
        rank[1]: {'c':'#f1c40f', 'lbl':'ZONA KUNING', 'desc':'Waspada / Sedang', 'score': 2},
        rank[2]: {'c':'#e74c3c', 'lbl':'ZONA MERAH', 'desc':'Bahaya / Tinggi', 'score': 3}
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
    
    avg_risk_index = weighted_score / total_kasus_provinsi if total_kasus_provinsi > 0 else 0
    
    if avg_risk_index >= 2.2:
        return {'lbl':'ZONA MERAH', 'desc':'Bahaya (Dominasi Klaster Tinggi)', 'c':'#e74c3c'}
    elif avg_risk_index >= 1.6:
        return {'lbl':'ZONA KUNING', 'desc':'Waspada (Sebaran Meningkat)', 'c':'#f1c40f'}
    else:
        return {'lbl':'ZONA HIJAU', 'desc':'Risiko Rendah (Dominasi Klaster Rendah)', 'c':'#2ecc71'}

def get_policy_advice(zona_label, data_usia, filter_gender):
    advice = []
    if zona_label == 'ZONA MERAH':
        advice.append("<b>🚨 DARURAT PROVINSI:</b> Eskalasi kasus tinggi. Gubernur perlu menginstruksikan penambahan anggaran darurat HIV dan audit stok obat ARV.")
        advice.append("<b>🏥 FASKES:</b> Wajibkan skrining HIV bagi seluruh pasien rawat inap dengan gejala oportunistik.")
    elif zona_label == 'ZONA KUNING':
        advice.append("<b>⚠️ PERINGATAN DINI:</b> Tren kasus meningkat. Perkuat peran Dinkes Provinsi untuk supervisi daerah dengan kasus tinggi.")
        advice.append("<b>📢 KAMPANYE:</b> Gencarkan sosialisasi masif melalui media sosial dan tokoh masyarakat tingkat provinsi.")
    else: 
        advice.append("<b>✅ MONITORING:</b> Pertahankan kondisi risiko rendah. Fokuskan anggaran pada edukasi preventif untuk mencegah lonjakan kasus.")

    if data_usia.get('Anak-anak', 0) > 0:
        advice.append("<b>👶 IBU & ANAK:</b> Prioritas penyelamatan generasi. Audit pelaksanaan 'Triple Eliminasi' pada Ibu Hamil di seluruh Puskesmas.")
    if data_usia.get('Remaja', 0) > 50:
        advice.append("<b>🎓 REMAJA:</b> Kasus muda tinggi. Disdik Provinsi wajib memasukkan modul kesehatan reproduksi di SMA/SMK.")

    if filter_gender == 'LAKI-LAKI':
        advice.append("<b>♂️ LAKI-LAKI:</b> Fokus pada komunitas pekerja dan bapak rumah tangga. Libatkan Serikat Pekerja untuk sosialisasi.")
    elif filter_gender == 'PEREMPUAN':
        advice.append("<b>♀️ PEREMPUAN:</b> Fokus perlindungan Ibu Rumah Tangga. Optimalkan peran PKK dan Posyandu untuk deteksi dini.")
        
    return advice

# ==========================================
# 4. SIDEBAR & LOGIKA INTERAKTIF
# ==========================================
if df is not None:
    # --- A. STATE MANAGEMENT ---
    if 'selected_city' not in st.session_state:
        st.session_state.selected_city = 'SEMUA KAB/KOTA'

    # --- B. SIDEBAR ---
    st.sidebar.header("🎛️ Filter Data")
    
    if st.session_state.selected_city == 'SEMUA KAB/KOTA':
        # Mode Pencarian (Dropdown)
        opt_kt = ['SEMUA KAB/KOTA'] + sorted(df['nama_kabupaten_kota'].unique())
        
        def on_dropdown_change():
            st.session_state.selected_city = st.session_state.dropdown_val

        st.sidebar.selectbox(
            "📍 Pilih Wilayah:",
            opt_kt,
            index=0,
            key='dropdown_val',
            on_change=on_dropdown_change
        )
    else:
        # Mode Fokus (Reset Button)
        st.sidebar.success(f"📍 Fokus: **{st.session_state.selected_city}**")
        
        if st.sidebar.button("🔄 Reset ke Provinsi", type="primary"):
            st.session_state.selected_city = 'SEMUA KAB/KOTA'
            st.rerun()
    
    st.sidebar.markdown("---")
    
    opt_th = ['SEMUA TAHUN'] + sorted(df['tahun'].unique(), reverse=True)
    th = st.sidebar.selectbox("📅 Tahun:", opt_th)
    
    opt_jk = ['SEMUA GENDER'] + sorted(df['jenis_kelamin'].unique().tolist())
    jk = st.sidebar.selectbox("👥 Gender:", opt_jk)
    
    kt = st.session_state.selected_city

    # --- FILTER DATA ---
    df_f = df.copy()
    if th != 'SEMUA TAHUN': df_f = df_f[df_f['tahun'] == th]
    if jk != 'SEMUA GENDER': df_f = df_f[df_f['jenis_kelamin'] == jk]

    # --- HITUNG AI ---
    colors, labels_data, city_scores = get_ai_clusters(df_f)
    
    df_grp = df_f.groupby('nama_kabupaten_kota')['jumlah_kasus'].sum()
    df_det = df_f.pivot_table(index='nama_kabupaten_kota', columns='kategori_simple', values='jumlah_kasus', aggfunc='sum', fill_value=0)
    for c in ['Anak-anak', 'Remaja', 'Dewasa', 'Lansia']: 
        if c not in df_det.columns: df_det[c] = 0

    # ==========================================
    # 5. PETA
    # ==========================================
    geo_current = copy.deepcopy(geo_data_raw)
    
    for feature in geo_current['features']:
        kota_nm = feature['properties']['name'].title()
        tot = df_grp.get(kota_nm, 0)
        risk_info = labels_data.get(kota_nm, {'lbl':'N/A', 'desc':''})
        warna_zona = colors.get(kota_nm, '#95a5a6')
        
        html_hover = f"""<div style="font-family:'Segoe UI',sans-serif;width:200px;background-color:white;border-radius:8px;box-shadow:0 4px 15px rgba(0,0,0,0.2);overflow:hidden;border:1px solid #f0f0f0;">
        <div style="background-color:{warna_zona};color:white;padding:10px 12px;font-size:14px;font-weight:bold;">{kota_nm.upper()}</div>
        <div style="padding:12px;color:#444;font-size:13px;">
        <div style="margin-bottom:5px;">Status: <b>{risk_info.get('lbl')}</b></div>
        <div>Total Kasus: <b>{tot:,.0f}</b></div>
        <div style="font-size:11px;color:#999;margin-top:5px;">(Klik untuk Detail)</div>
        </div></div>"""

        feature['properties']['fillColor'] = warna_zona
        feature['properties']['isi_tooltip'] = html_hover

    def style_function_dynamic(feature):
        kota_name = feature['properties']['name'].title()
        base = feature['properties']['fillColor']
        if kt != 'SEMUA KAB/KOTA' and kota_name.upper() == kt.upper():
            return {'fillColor': base, 'color': 'cyan', 'weight': 4, 'fillOpacity': 0.9, 'opacity': 1}
        return {'fillColor': base, 'color': 'white', 'weight': 1, 'fillOpacity': 0.7, 'opacity': 1}

    st.title("Peta Persebaran Risiko HIV Jawa Barat")
    
    st.markdown('''
    <div style="font-family:sans-serif; font-size:14px; margin-bottom: 5px; font-weight:bold;">
        ZONA RISIKO (AI) &nbsp;&nbsp;&nbsp;
        <span style="color:#e74c3c;">■</span> Merah (Bahaya) &nbsp;&nbsp;
        <span style="color:#f1c40f;">■</span> Kuning (Waspada) &nbsp;&nbsp;
        <span style="color:#2ecc71;">■</span> Hijau (Risiko Rendah)
    </div>
    ''', unsafe_allow_html=True)

    sw, ne = [-8.0, 106.0], [-5.5, 109.0]
    m = folium.Map(location=[-6.9175, 107.6191], zoom_start=9, min_zoom=8, max_zoom=12, max_bounds=True, tiles='CartoDB positron')
    m.fit_bounds([sw, ne])

    folium.GeoJson(
        geo_current, 
        style_function=style_function_dynamic, 
        tooltip=folium.GeoJsonTooltip(fields=['isi_tooltip'], labels=False)
    ).add_to(m)

    map_data = st_folium(m, width="100%", height=550)

    if map_data and map_data.get('last_active_drawing'):
        props = map_data['last_active_drawing'].get('properties', {})
        clicked_name = props.get('name', '').title()
        if clicked_name and clicked_name != st.session_state.selected_city:
            st.session_state.selected_city = clicked_name
            st.rerun()

    # ==========================================
    # 6. HTML LAPORAN (Updated Styling)
    # ==========================================
    if kt == 'SEMUA KAB/KOTA':
        judul_lap = "JAWA BARAT (PROVINSI)"
        zona_stats = calculate_province_status(df_f, city_scores)
        tot_val = df_f['jumlah_kasus'].sum()
        r = df_f.pivot_table(columns='kategori_simple', values='jumlah_kasus', aggfunc='sum')
        r = r.iloc[0] if not r.empty else pd.Series()
        det_val = {k: r.get(k, 0) for k in ['Anak-anak','Remaja','Dewasa','Lansia']}
        warna_header = zona_stats['c'] 
    else:
        judul_lap = kt.upper()
        zona_stats = labels_data.get(kt.title(), {'lbl':'N/A', 'desc':'', 'c':'#95a5a6'})
        tot_val = df_grp.get(kt.title(), 0)
        r = df_det.loc[kt.title()] if kt.title() in df_det.index else pd.Series({'Anak-anak':0, 'Remaja':0, 'Dewasa':0, 'Lansia':0})
        det_val = r.to_dict()
        warna_header = colors.get(kt.title(), "#95a5a6")

    rekomendasi = get_policy_advice(zona_stats.get('lbl'), det_val, jk)
    html_rekomendasi = "<ul style='margin:0; padding-left:20px;'>"
    for rec in rekomendasi: 
        html_rekomendasi += f"<li style='margin-bottom:8px;'>{rec}</li>"
    html_rekomendasi += "</ul>"

    # --- HTML TABLE YANG DIUPDATE AGAR SIMETRIS ---
    # Menggunakan styling yang lebih bersih dan modern mirip screenshot
    html_table = f"""
    <div style="border: 1px solid #e0e0e0; border-radius: 6px; overflow: hidden; margin-top:10px;">
        <table style="width:100%; border-collapse: collapse; font-family: 'Segoe UI', sans-serif; font-size: 14px;">
            <thead>
                <tr style="background-color: #f8f9fa;">
                    <th style="text-align: left; padding: 12px 15px; color: #555; font-weight: 600; border-bottom: 1px solid #e0e0e0;">KELOMPOK USIA</th>
                    <th style="text-align: right; padding: 12px 15px; color: #555; font-weight: 600; border-bottom: 1px solid #e0e0e0;">JUMLAH KASUS</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td style="padding: 10px 15px; border-bottom: 1px solid #f0f0f0; color:#333;">Anak-anak</td>
                    <td style="padding: 10px 15px; text-align: right; border-bottom: 1px solid #f0f0f0; font-weight:bold; color:#333;">{det_val.get('Anak-anak',0):,.0f}</td>
                </tr>
                <tr>
                    <td style="padding: 10px 15px; border-bottom: 1px solid #f0f0f0; color:#333;">Remaja</td>
                    <td style="padding: 10px 15px; text-align: right; border-bottom: 1px solid #f0f0f0; font-weight:bold; color:#333;">{det_val.get('Remaja',0):,.0f}</td>
                </tr>
                <tr>
                    <td style="padding: 10px 15px; border-bottom: 1px solid #f0f0f0; color:#333;">Dewasa</td>
                    <td style="padding: 10px 15px; text-align: right; border-bottom: 1px solid #f0f0f0; font-weight:bold; color:#333;">{det_val.get('Dewasa',0):,.0f}</td>
                </tr>
                <tr>
                    <td style="padding: 10px 15px; color:#333;">Lansia</td>
                    <td style="padding: 10px 15px; text-align: right; font-weight:bold; color:#333;">{det_val.get('Lansia',0):,.0f}</td>
                </tr>
            </tbody>
        </table>
    </div>
    """

    # Top 5 Table (Jika Provinsi)
    html_top5 = "" 
    if kt == 'SEMUA KAB/KOTA':
        top5 = df_grp.sort_values(ascending=False).head(5)
        rows = ""
        max_v = top5.max() if not top5.empty else 1
        for c, v in top5.items():
            pct = (v/max_v)*100
            rows += f"<tr><td style='padding:5px; border-bottom:1px solid #eee;'>{c}</td><td style='padding:5px; text-align:right; border-bottom:1px solid #eee;'><b>{v}</b></td><td style='padding:5px; width:40%; border-bottom:1px solid #eee;'><div style='background:#3498db; width:{pct}%; height:8px; border-radius:4px;'></div></td></tr>"
        html_top5 = f"<div style='margin-top:20px; border:1px solid #ddd; padding:10px; border-radius:5px;'><b style='color:#555;'>🏆 5 WILAYAH TERTINGGI</b><table style='width:100%; font-size:12px; margin-top:5px; border-collapse:collapse; color:#333;'>{rows}</table></div>"

    # HTML FINAL (LAYOUT FLEX DENGAN RASIO SEIMBANG)
    final_html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; color:#333; background-color:white; border-radius:8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-top: 10px;">
        
        <div style="background-color: {warna_header}; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h2 style="margin:0; font-size:24px;">📊 LAPORAN: {judul_lap}</h2>
                    <div style="font-size:14px; margin-top:5px; opacity:0.9;">FILTER GENDER: <b>{jk}</b></div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:12px; text-transform:uppercase; opacity:0.9; letter-spacing:1px;">STATUS RISIKO</div>
                    <div style="font-size:22px; font-weight:bold; margin:2px 0;">{zona_stats.get('lbl')}</div>
                    <div style="font-size:13px;">{zona_stats.get('desc')}</div>
                </div>
            </div>
            <hr style="border:0; border-top:1px solid rgba(255,255,255,0.3); margin:15px 0;">
            <div style="font-size:15px;">TOTAL KASUS TERDATA: <b style="font-size:18px;">{tot_val:,.0f}</b> ORANG</div>
        </div>

        <div style="border: 1px solid #ddd; border-top:none; padding: 25px; border-radius: 0 0 8px 8px; background-color:white;">
            
            <div style="display: flex; gap: 30px; flex-wrap: wrap;">
                
                <div style="flex: 1; min-width: 300px;">
                    <div style="display:flex; align-items:center; margin-bottom:10px;">
                        <span style="font-size:18px; margin-right:8px;">📋</span>
                        <b style="color:#555; font-size:16px;">DATA DEMOGRAFI</b>
                    </div>
                    {html_table}
                    {html_top5}
                </div>

                <div style="flex: 1; min-width: 300px;">
                    <div style="background-color: #fff8e1; border-left: 5px solid #f1c40f; padding: 20px; border-radius: 6px; height: 100%; box-sizing: border-box;">
                        <div style="display:flex; align-items:center; margin-bottom:15px;">
                            <span style="font-size:18px; margin-right:8px;">💡</span>
                            <b style="color:#d35400; font-size:16px;">REKOMENDASI KEBIJAKAN</b>
                        </div>
                        <div style="font-size: 14px; line-height: 1.6; color:#333;">
                            {html_rekomendasi}
                        </div>
                    </div>
                </div>

            </div>
        </div>
    </div>
    """

    st.markdown(final_html, unsafe_allow_html=True)

else:
    st.warning("Data belum dimuat.")
