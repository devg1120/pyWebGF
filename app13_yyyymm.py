import io
import base64
import glob
import math
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg') # GUIを使わない設定

from matplotlib.figure import Figure
import matplotlib.dates as mdates  
from flask import Flask, render_template, request

# --- CentOS 7 / Ubuntu 共通の日本語文字化け対策 ---
matplotlib.rcParams['font.family'] = 'IPAexGothic'
matplotlib.rcParams['axes.unicode_minus'] = False 
# ------------------------------------------------

app = Flask(__name__)
# データのルートディレクトリ。配下に「202610/03/SWITCH_1/data1.csv」などが配置される想定
BASE_DIR = "./data_yyyymm"

@app.route('/')
def index():
    # 1. 2階層（YYYYMM / DD）の有効な日付パス一覧を探索・取得
    available_dates = []
    yyyymm_dirs = sorted([d for d in glob.glob(os.path.join(BASE_DIR, "*")) if os.path.isdir(d)])
    
    for yyyymm_dir in yyyymm_dirs:
        yyyymm_name = os.path.basename(yyyymm_dir)
        dd_dirs = sorted([d for d in glob.glob(os.path.join(yyyymm_dir, "*")) if os.path.isdir(d)])
        for dd_dir in dd_dirs:
            dd_name = os.path.basename(dd_dir)
            available_dates.append(f"{yyyymm_name}/{dd_name}")
            
    if not available_dates:
        return f"<h1>エラー: {BASE_DIR} 配下に /YYYYMM/DD/ 形式のディレクトリが見つかりません。</h1>", 500
        
    # リクエストから選択された日付（デフォルトは最初の日付）を取得
    selected_date = request.args.get('dir', available_dates[0])
    
    # 【変更点】選択された日付配下にある「SWITCH_#」の一覧を動的に取得
    date_dir = os.path.join(BASE_DIR, selected_date)
    available_switches = sorted([
        os.path.basename(d) for d in glob.glob(os.path.join(date_dir, "SWITCH_*"))
        if os.path.isdir(d)
    ])
    
    # 選択されたSWITCH（デフォルトは最初のスイッチ。なければ空文字）
    selected_switch = request.args.get('switch', available_switches[0] if available_switches else "")
    
    # 時間ベースの範囲パラメータ（デフォルトは 8時 〜 18時）
    start_hour = int(request.args.get('start_hour', 8))
    end_hour = int(request.args.get('end_hour', 18))
    
    # 【変更点】選択された「日付」と「SWITCH」から、data1.csv 〜 data4.csv の4つのファイルを固定で探索
    csv_files = []
    if selected_switch:
        target_dir = os.path.join(BASE_DIR, selected_date, selected_switch)
        for i in range(1, 5):
            file_name = f"data{i}.csv"
            file_path = os.path.join(target_dir, file_name)
            # ファイルが存在していればパスを登録、なければ None を入れて枠だけ維持する（4つのレイアウト固定のため）
            if os.path.exists(file_path):
                csv_files.append(file_path)
            else:
                csv_files.append(None)
                
    plot_url = ""
    
    # 2. グラフの描画処理（2行 × 2列 = 4つのグラフ固定）
    if any(csv_files):
        ncols = 2
        nrows = 2
        
        fig = Figure(figsize=(14, 10)) # 4面見やすくするために縦幅を10に広げました
        axes = fig.subplots(nrows=nrows, ncols=ncols)
        axes = axes.flatten() # 2x2の配列を1次元にフラット化
        
        for i in range(4):
            ax = axes[i]
            file_path = csv_files[i]
            file_name = f"data{i+1}.csv"
            
            # ファイルが存在しない場合の空枠表示
            if file_path is None:
                ax.text(0.5, 0.5, f'{file_name} が見つかりません', ha='center', va='center', color='gray')
                ax.set_title(f'{file_name} (データなし)')
                ax.grid(True, linestyle='--', alpha=0.3)
                continue
                
            try:
                df = pd.read_csv(file_path)
                
                if len(df.columns) >= 3:
                    df.columns = ['日時', '項目A', '項目B']
                else:
                    raise ValueError("CSVの列数が足りません。日時、項目A、項目Bの3列が必要です。")
                    
                df['日時'] = pd.to_datetime(df['日時'])
                
                # グラフのプロット
                ax.plot(df['日時'], df['項目A'], color='b', label='項目A（In）', linewidth=1)
                ax.plot(df['日時'], df['項目B'], color='orange', label='項目B（Out）', linewidth=1)
                
                # 指定された「時間（Hour）」で表示範囲（xlim）を制限
                base_date = df['日時'].iloc[0].normalize() 
                start_time = base_date + pd.Timedelta(hours=start_hour)
                end_time = base_date + pd.Timedelta(hours=end_hour, minutes=55)
                ax.set_xlim(start_time, end_time)
                
                # 目盛りの個別強制表示と回転設定
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.tick_params(labelbottom=True) 
                for label in ax.get_xticklabels():
                    label.set_rotation(30)
                    label.set_horizontalalignment('right')
                
                # Y軸のカンマ区切りと指数表記防止
                ax.get_yaxis().get_major_formatter().set_scientific(False)
                ax.get_yaxis().set_major_formatter(matplotlib.ticker.StrMethodFormatter('{x:,.0f}'))
                
                # タイトルにファイル名をセット
                ax.set_title(f'{file_name} 時系列グラフ')
                ax.set_xlabel('時間')
                ax.set_ylabel('数値')
                ax.grid(True, linestyle='--', alpha=0.6)
                ax.legend(loc='best')
                
            except Exception as e:
                ax.text(0.5, 0.5, f'エラー:\n{str(e)}', ha='center', va='center')
                ax.set_title(f'{file_name} (読込失敗)')
                
        fig.tight_layout(h_pad=4.0, w_pad=3.0) 
        
        img = io.BytesIO()
        fig.savefig(img, format='png', bbox_inches='tight')
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode('utf8')
        fig.clear()

    # HTML テンプレートへ渡す変数に switches と selected_switch を追加
    return render_template(
        'index3.html', 
        sub_directories=available_dates, 
        selected_dir=selected_date, 
        switches=available_switches,
        selected_switch=selected_switch,
        start_hour=start_hour,
        end_hour=end_hour,
        plot_url=plot_url
    )

if __name__ == '__main__':
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
    app.run(debug=True)
