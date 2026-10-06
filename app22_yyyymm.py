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
from flask import Flask, render_template, request

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
        
    # 【修正】リクエストから選択された YYYYMM を取得（デフォルトはリストの最初の要素）
    available_yyyymm = list(date_tree.keys())
    selected_yyyymm = request.args.get('yyyymm', available_yyyymm[0])
    
    # 選択された YYYYMM に属する日のリストを取得
    available_dds = date_tree.get(selected_yyyymm, [])
    if not available_dds:
        return f"<h1>エラー: 選択された月 {selected_yyyymm} に有効な日（DD）がありません。</h1>", 500
    
    # 【修正】リクエストから選択された DD を取得（デフォルトはリストの最初の要素）
    selected_dd = request.args.get('dd', available_dds[0])
    
    # 2階層を結合して従来のパス形式にする
    selected_date = f"{selected_yyyymm}/{selected_dd}"
    
    # 選択された日付配下にある「SWITCH_#」の一覧を動的に取得
    date_dir = os.path.join(BASE_DIR, selected_date)
    available_switches = sorted([
        os.path.basename(d) for d in glob.glob(os.path.join(date_dir, "SWITCH_*"))
        if os.path.isdir(d)
    ])
    
    # 【修正】選択されたSWITCH（デフォルトは最初のスイッチ [0]。なければ空文字）
    selected_switch = request.args.get('switch', available_switches[0] if available_switches else "")
    
    # 動的なグラフ列数の取得（デフォルトは 2列）
    try:
        selected_cols = int(request.args.get('cols', 2))
    except ValueError:
        selected_cols = 2
        
    # 時間ベースの範囲パラメータ（デフォルトは 8時 〜 18時）
    start_hour = int(request.args.get('start_hour', 8))
    end_hour = int(request.args.get('end_hour', 18))
    
    # フォルダ内のすべての .csv ファイルを動的に取得
    csv_files = []
    if selected_switch:
        target_dir = os.path.join(BASE_DIR, selected_date, selected_switch)
        csv_files = sorted(glob.glob(os.path.join(target_dir, "*.csv")))
                
    # 個別にエンコードされたグラフ画像を格納するリスト
    plot_urls = []
    
    # 選択された列数に応じて画像のサイズ(比率)を動的に変える
    if selected_cols == 1:
        fig_size = (14, 5.0)
    elif selected_cols == 4:
        fig_size = (6, 4.5)
    else:
        fig_size = (8, 4.8)
    
    # 2. グラフの描画処理（見つかったCSVファイルの数だけループ処理を行う）
    if csv_files:
        for file_path in csv_files:
            file_name = os.path.basename(file_path)
            
            fig = Figure(figsize=fig_size)
            ax = fig.subplots()
            
            try:
                df = pd.read_csv(file_path)
                
                if len(df.columns) >= 3:
                    df.columns = ['日時', '項目A', '項目B']
                else:
                    raise ValueError("CSVの列数が足りません。日時、項目A、項目Bの3列が必要です。")
                    
                df['日時'] = pd.to_datetime(df['日時'])
                
                # --- 前の行との差分（バイト量）を計算 ---
                df['差分A'] = df['項目A'].diff()
                df['差分B'] = df['項目B'].diff()
                
                # カウンターリセット・ラップアラウンド対策（マイナス値を0に補正）
                df.loc[df['差分A'] < 0, '差分A'] = 0
                df.loc[df['差分B'] < 0, '差=B'] = 0
                
                # --- 5分間隔（300秒）のデータから bps に変換 ---
                df['bps_A'] = (df['差分A'] * 8) / 300
                df['bps_B'] = (df['差分B'] * 8) / 300
                
                # グラフ描画
                ax.plot(df['日時'], df['bps_A'], color='b', label='In (bps)', linewidth=1)
                ax.plot(df['日時'], df['bps_B'], color='orange', label='Out (bps)', linewidth=1)
                
                base_date = df['日時'].iloc[0].normalize() 
                start_time = base_date + pd.Timedelta(hours=start_hour)
                end_time = base_date + pd.Timedelta(hours=end_hour, minutes=55)
                ax.set_xlim(start_time, end_time)
                
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.tick_params(labelbottom=True) 
                for label in ax.get_xticklabels():
                    label.set_rotation(30)
                    label.set_horizontalalignment('right')
                
                # --- Y軸の表記設定 ---
                ax.get_yaxis().get_major_formatter().set_scientific(False)
                
                # データの最大値に応じてY軸の単位（bps / Kbps / Mbps）を自動調整
                max_val = max(df['bps_A'].max(), df['bps_B'].max()) if not df.empty else 0
                if max_val >= 1_000_000:
                    ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f'{x/1_000_000:,.1f} M'))
                    ax.set_ylabel('転送速度 (Mbps)')
                elif max_val >= 1_000:
                    ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f'{x/1_000:,.0f} K'))
                    ax.set_ylabel('転送速度 (Kbps)')
                else:
                    ax.get_yaxis().set_major_formatter(matplotlib.ticker.StrMethodFormatter('{x:,.0f}'))
                    ax.set_ylabel('転送速度 (bps)')
                
                ax.set_title(f'{file_name} トラフィック（速度）')
                ax.set_xlabel('時間')
                ax.grid(True, linestyle='--', alpha=0.6)
                ax.legend(loc='best')
                
            except Exception as e:
                ax.text(0.5, 0.5, f'エラー:\n{str(e)}', ha='center', va='center')
                ax.set_title(f'{file_name} (読込失敗)')
            
            fig.tight_layout()
            img = io.BytesIO()
            fig.savefig(img, format='png', bbox_inches='tight', dpi=120)
            img.seek(0)
            
            encoded_url = base64.b64encode(img.getvalue()).decode('utf8')
            plot_urls.append(encoded_url)
            fig.clear()

    return render_template(
        'index22.html', 
        date_tree=date_tree, 
        selected_yyyymm=selected_yyyymm,
        selected_dd=selected_dd,
        available_dds=available_dds,
        switches=available_switches,
        selected_switch=selected_switch,
        selected_cols=selected_cols,  
        start_hour=start_hour,
        end_hour=end_hour,
        plot_urls=plot_urls  
    )

if __name__ == '__main__':
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
    app.run(debug=True)
