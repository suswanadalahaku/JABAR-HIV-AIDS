# ==========================================
    # 6. HTML LAPORAN (PERBAIKAN LOGIKA HIDE RANKING)
    # ==========================================
    if kt == 'SEMUA KAB/KOTA':
        judul_lap = "JAWA BARAT (PROVINSI)"
        prov_status = calculate_province_status(df_f, city_scores)
        zona_stats = prov_status 
        tot_val = df_f['jumlah_kasus'].sum()
        
        # Data Demografi untuk Provinsi
        r = df_f.pivot_table(columns='kategori_simple', values='jumlah_kasus', aggfunc='sum')
        r = r.iloc[0] if not r.empty else pd.Series()
        det_val = {k: r.get(k, 0) for k in ['Anak-anak','Remaja','Dewasa','Lansia']}
        warna_header = prov_status['c'] 
        
    else:
        # Jika memilih Kota Spesifik
        judul_lap = kt.upper()
        zona_stats = labels_data.get(kt.title(), {'lbl':'N/A', 'desc':''})
        tot_val = df_grp.get(kt.title(), 0)
        
        # Data Demografi untuk Kota Spesifik
        r = df_det.loc[kt.title()] if kt.title() in df_det.index else pd.Series({'Anak-anak':0, 'Remaja':0, 'Dewasa':0, 'Lansia':0})
        det_val = r.to_dict()
        warna_header = colors.get(kt.title(), "#95a5a6")

    # --- REKOMENDASI KEBIJAKAN ---
    rekomendasi = get_policy_advice(zona_stats.get('lbl'), det_val, jk)
    html_rekomendasi = "<ul style='margin:0; padding-left:20px;'>"
    for rec in rekomendasi: 
        html_rekomendasi += f"<li style='margin-bottom:8px;'>{rec}</li>"
    html_rekomendasi += "</ul>"

    # --- TABEL DEMOGRAFI (SELALU MUNCUL) ---
    html_table = f"""
    <table style="width:100%; border-collapse: collapse; font-family: Arial; font-size: 13px; margin-top:10px; color:#333;">
        <tr style="background-color: #f1f2f6; color: #333;">
            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">KELOMPOK USIA</th>
            <th style="border: 1px solid #ddd; padding: 8px; text-align: right;">JUMLAH KASUS</th>
        </tr>
        <tr><td style="border: 1px solid #ddd; padding: 8px;">Anak-anak</td><td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{det_val['Anak-anak']:,.0f}</td></tr>
        <tr><td style="border: 1px solid #ddd; padding: 8px;">Remaja</td><td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{det_val['Remaja']:,.0f}</td></tr>
        <tr><td style="border: 1px solid #ddd; padding: 8px;">Dewasa</td><td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{det_val['Dewasa']:,.0f}</td></tr>
        <tr><td style="border: 1px solid #ddd; padding: 8px;">Lansia</td><td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{det_val['Lansia']:,.0f}</td></tr>
    </table>"""

    # --- RANKING 5 WILAYAH (HANYA MUNCUL JIKA 'SEMUA KAB/KOTA') ---
    html_top5 = "" # Default KOSONG agar tidak muncul
    
    if kt == 'SEMUA KAB/KOTA':
        # Logika pembuatan tabel ranking hanya dijalankan di sini
        top5 = df_grp.sort_values(ascending=False).head(5)
        rows = ""
        max_v = top5.max() if not top5.empty else 1
        for c, v in top5.items():
            pct = (v/max_v)*100
            rows += f"<tr><td style='padding:5px; border-bottom:1px solid #eee;'>{c}</td><td style='padding:5px; text-align:right; border-bottom:1px solid #eee;'><b>{v}</b></td><td style='padding:5px; width:40%; border-bottom:1px solid #eee;'><div style='background:#3498db; width:{pct}%; height:8px; border-radius:4px;'></div></td></tr>"
        
        # Isi variabel html_top5
        html_top5 = f"<div style='margin-top:20px; border:1px solid #ddd; padding:10px; border-radius:5px;'><b style='color:#555;'>🏆 5 WILAYAH TERTINGGI</b><table style='width:100%; font-size:12px; margin-top:5px; border-collapse:collapse; color:#333;'>{rows}</table></div>"

    # --- RENDER FINAL HTML ---
    final_html = f"""
    <div style="font-family: Arial, sans-serif; color:#333; background-color:white; border-radius:8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-top: 10px;">
        <div style="background-color: {warna_header}; color: white; padding: 15px; border-radius: 8px 8px 0 0;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h3 style="margin:0;">📊 LAPORAN: {judul_lap}</h3>
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
        <div style="border: 1px solid #ddd; border-top:none; padding: 20px; border-radius: 0 0 8px 8px; background-color:white;">
            <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 250px;">
                    <b style="color:#555; display:block; border-bottom:2px solid #eee; padding-bottom:5px;">📋 DATA DEMOGRAFI</b>
                    {html_table}
                    {html_top5} </div>
                <div style="flex: 1; min-width: 250px;">
                    <div style="background-color: #fff8e1; border-left: 5px solid #f1c40f; padding: 15px; border-radius: 4px;">
                        <b style="color:#d35400; display:block; margin-bottom:10px;">💡 REKOMENDASI KEBIJAKAN</b>
                        <div style="font-size: 13px; line-height: 1.5; color:#333;">{html_rekomendasi}</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
