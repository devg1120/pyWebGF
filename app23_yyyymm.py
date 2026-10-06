import io
import base64
import glob
import os
import platform
import pandas as pd
import matplotlib
matplotlib.use('Agg') # GUIを使わない設定

from matplotlib.figure import Figure
import matplotlib.dates as mdates  
from flask import Flask, render_template, request, send_file

# --- OS自動判定による日本語文字化け対策 ---
current_os = platform.system()

if current_os == 'Windows':
    matplotlib.rcParams['font.family'] = 'Yu Gothic'    # Windowsの游ゴシック
elif current_os == 'Linux':
    matplotlib.rcParams['font.family'] = 'IPAexGothic'  # LinuxのIPAexゴシック
else:
    matplotlib.rcParams['font.family'] = 'sans-serif'   # その他のフォールバック用

matplotlib.rcParams['axes.unicode_minus'] = False 
# -----------------------------------------------------------------

app = Flask(__name__)
BASE_DIR = "./data_yyyymm_counter"

@app.route('/')
def index():
    # 1. 2階層（YYYYMM / DD）の構造を辞書型で取得
    date_tree = {}
    yyyymm_dirs = sorted([d for d in glob.glob(os.path.join(BASE_DIR, "*")) if os.path.isdir(d)])
    
    for yyyymm_dir in yyyymm_dirs:
        yyyymm_name = os.path.basename(yyyymm_dir)
        dd_dirs = sorted([d for d in glob.glob(os.path.join(yyyymm_dir, "*")) if os.path.isdir(d)])
        
        dd_list = [os.path.basename(d) for d in dd_dirs]
        if dd_list:
            date_tree[yyyymm_name] = dd_list
            
    if not date_tree:
        return f"<h1>エラー: {BASE_DIR} 配下に /YYYYMM/DD/ 形式のディレクトリが見つかりません。</h1>", 500
        
    available_yyyymm = list(date_tree.keys())
    selected_yyyymm = request.args.get('yyyymm', available_yyyymm[0])
    
    available_dds = date_tree.get(selected_yyyymm, [])
    if not available_dds:
        return f"<h1>エラー: 選択された月 {selected_yyyymm} に有効な日（DD）がありません。</h1>", 500
    
    selected_dd = request.args.get('dd', available_dds[0])
    selected_date = f"{selected_yyyymm}/{selected_dd}"
    
    date_dir = os.path.join(BASE_DIR, selected_date)
    available_switches = sorted([
        os.path.basename(d) for d in glob.glob(os.path.join(date_dir, "SWITCH_*"))
        if os.path.isdir(d)
    ])
    
    selected_switch = request.args.get('switch', available_switches[0] if available_switches else "")
    
    try:
        selected_cols = int(request.args.get('cols', 2))
    except ValueError:
        selected_cols = 2
        
    start_hour = int(request.args.get('start_hour', 8))
    end_hour = int(request.args.get('end_hour', 18))
    
    # 💡 変更点①: ここでは「ファイル名のリスト」だけを収集して、描画ループは回さない（爆速化）
    csv_filenames = []
    if selected_switch:
        target_dir = os.path.join(BASE_DIR, selected_date, selected_switch)
        csv_files = sorted(glob.glob(os.path.join(target_dir, "*.csv")))
        # フルパスではなく、ファイル名のみのリストにする
        csv_filenames = [os.path.basename(f) for f in csv_files]

    return render_template(
        'index23.html', 
        date_tree=date_tree, 
        selected_yyyymm=selected_yyyymm,
        selected_dd=selected_dd,
        available_dds=available_dds,
        switches=available_switches,
        selected_switch=selected_switch,
        selected_cols=selected_cols,  
        start_hour=start_hour,
        end_hour=end_hour,
        csv_filenames=csv_filenames  # 描画用データの代わりにファイル名リストを送る
    )

# 💡 変更点②: 1枚のグラフ画像をオンデマンドで生成して返す「軽量エンドポイント」を新設
@app.route('/plot')
def plot_graph():
    yyyymm = request.args.get('yyyymm')
    dd = request.args.get('dd')
    switch = request.args.get('switch')
    filename = request.args.get('filename')
    cols = int(request.args.get('cols', 2))
    start_hour = int(request.args.get('start_hour', 8))
    end_hour = int(request.args.get('end_hour', 18))
    
    file_path = os.path.join(BASE_DIR, yyyymm, dd, switch, filename)
    
    if cols == 1:
        fig_size = (14, 5.0)
    elif cols == 4:
        fig_size = (6, 4.5)
    else:
        fig_size = (8, 4.8)
        
    fig = Figure(figsize=fig_size)
    ax = fig.subplots()
    
    try:
        df = pd.read_csv(file_path, engine='c')
        if len(df.columns) >= 3:
            df.columns = ['日時', '項目A', '項目B']
        df['日時'] = pd.to_datetime(df['日時'], format='mixed')
        
        df['差分A'] = df['項目A'].diff()
        df['差分B'] = df['項目B'].diff()
        df.loc[df['差分A'] < 0, '差分A'] = 0
        df.loc[df['差分B'] < 0, '差分B'] = 0
        
        df['bps_A'] = (df['差分A'] * 8) / 300
        df['bps_B'] = (df['差分B'] * 8) / 300
        
        base_date = df['日時'].iloc[0].normalize() 
        start_time = base_date + pd.Timedelta(hours=start_hour)
        end_time = base_date + pd.Timedelta(hours=end_hour, minutes=55)
        
        df_filtered = df[(df['日時'] >= start_time) & (df['日時'] <= end_time)]
        
        ax.plot(df_filtered['日時'], df_filtered['bps_A'], color='b', label='In (bps)', linewidth=1)
        ax.plot(df_filtered['日時'], df_filtered['bps_B'], color='orange', label='Out (bps)', linewidth=1)
        
        ax.set_xlim(start_time, end_time)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.tick_params(labelbottom=True) 
        for label in ax.get_xticklabels():
            label.set_rotation(30)
            label.set_horizontalalignment('right')
        
        ax.get_yaxis().get_major_formatter().set_scientific(False)
        
        max_val = max(df_filtered['bps_A'].max(), df_filtered['bps_B'].max()) if not df_filtered.empty else 0
        if max_val >= 1_000_000:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f'{x/1_000_000:,.1f} M'))
            ax.set_ylabel('転送速度 (Mbps)')
        elif max_val >= 1_000:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f'{x/1_000:,.0f} K'))
            ax.set_ylabel('転送速度 (Kbps)')
        else:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.StrMethodFormatter('{x:,.0f}'))
            ax.set_ylabel('転送速度 (bps)')
        
        ax.set_title(f'{filename} トラフィック（速度）')
        ax.set_xlabel('時間')
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend(loc='best')
        
    except Exception as e:
        ax.text(0.5, 0.5, f'エラー:\n{str(e)}', ha='center', va='center')
        ax.set_title(f'{filename} (読込失敗)')
    
    fig.tight_layout()
    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight', dpi=120)
    img.seek(0)
    fig.clear()
    
    # 💡 拡張子をPNG画像としてそのままブラウザへ直接レスポンス（Base64変換不要）
    return send_file(img, mimetype='image/png')

if __name__ == '__main__':
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
    app.run(debug=True)
