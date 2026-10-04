import io
import base64
import glob
import math
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg') # GUIを使わない設定

from matplotlib.figure import Figure
import matplotlib.dates as mdates  # 【重要】時系列フォーマット用
from flask import Flask, render_template, request

# --- CentOS 7 / Ubuntu 共通の日本語文字化け対策 ---
matplotlib.rcParams['font.family'] = 'IPAexGothic'
matplotlib.rcParams['axes.unicode_minus'] = False 
# ------------------------------------------------

app = Flask(__name__)
BASE_DIR = "./data_times"

@app.route('/')
def index():
    # 1. サブディレクトリ一覧を取得
    sub_directories = sorted([
        os.path.basename(d) for d in glob.glob(os.path.join(BASE_DIR, "*")) 
        if os.path.isdir(d)
    ])
    
    if not sub_directories:
        return "<h1>エラー: data_long 配下にディレクトリが見つかりません。</h1>", 500
        
    selected_dir = request.args.get('dir', sub_directories[0])
    
    # 選択されたディレクトリ内のCSVファイルを取得
    target_path = os.path.join(BASE_DIR, selected_dir, "*.csv")
    csv_files = sorted(glob.glob(target_path))
    
    # 2. 初期スキャン：データ件数（24時間5分刻みなら最大288行）を取得
    max_data_index = 287 # デフォルト（288件分）
    if csv_files:
        try:
            # 1列目をインデックスとして、また日時としてパースできるように仮読み込み
            sample_df = pd.read_csv(csv_files[0])
            if not sample_df.empty:
                max_data_index = max(0, len(sample_df) - 1)
        except Exception:
            pass

    # 3. 範囲パラメータの取得とバリデーション
    start_xlim = int(request.args.get('start_xlim', 0))
    end_xlim = int(request.args.get('end_xlim', max_data_index))
    
    if start_xlim > end_xlim:
        start_xlim, end_xlim = end_xlim, start_xlim

    plot_url = ""
    
    # 4. グラフの描画処理
    if csv_files:
        ncols = 2
        nrows = math.ceil(len(csv_files) / ncols)
        
        fig = Figure(figsize=(14, 5 * nrows)) # 横軸が時間で見づらくならないよう、横幅を14に広げました
        axes = fig.subplots(nrows=nrows, ncols=ncols)
        
        try:
            if len(csv_files) == 1:
                axes = [axes]
            else:
                axes = axes.flatten()
                
            last_index = 0
            for i, file_path in enumerate(csv_files):
                ax = axes[i]
                file_name = os.path.basename(file_path)
                last_index = i
                
                try:
                    # 【重要】1列目を「日時」として読み込み、日付型に変換
                    df = pd.read_csv(file_path)
                    df.columns = ['日時', '項目A', '項目B'] # 列名を明示的に固定
                    df['日時'] = pd.to_datetime(df['日時'])
                    
                    # 画面で選択されたインデックスに対応する実際の日時を取得
                    # 選択範囲外でもグラフ自体に線を描画させ、xlimで絞り込むアプローチ
                    start_time = df['日時'].iloc[start_xlim]
                    end_time = df['日時'].iloc[min(end_xlim, len(df)-1)]
                    
                    # グラフの描画
                    ax.plot(df['日時'], df['項目A'], color='b', label='項目A', linewidth=1)
                    ax.plot(df['日時'], df['項目B'], color='orange', label='項目B', linewidth=1)
                    
                    # 時系列の範囲を指定
                    ax.set_xlim(start_time, end_time)
                    
                    # --- 時系列軸の見栄え調整 ---
                    # 横軸の時間を「10:30」のような形式にする（日付が変わる場合は「10-03 10:30」なども可能）
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                    # ラベルの間隔を自動でいい感じにする（データが詰まって重なるのを防ぐ）
                    fig.autofmt_xdate(rotation=30) 
                    
                    # Y軸の数字が「1e6」などの指数表記になるのを防ぎ、通常の整数表記にする
                    ax.get_yaxis().get_major_formatter().set_scientific(False)
                    # カンマ区切り（1,000,000）にする場合
                    ax.get_yaxis().set_major_formatter(matplotlib.ticker.StrMethodFormatter('{x:,.0f}'))
                    
                    ax.set_title(f'{file_name} 時系列グラフ')
                    ax.set_xlabel('時間')
                    ax.set_ylabel('数値')
                    ax.grid(True, linestyle='--', alpha=0.6)
                    ax.legend(loc='best')
                    
                except Exception as e:
                    ax.text(0.5, 0.5, f'エラー:\n{str(e)}', ha='center', va='center')
                    ax.set_title(f'{file_name} (読込失敗)')

            for j in range(last_index + 1, len(axes)):
                fig.delaxes(axes[j])
                
            fig.tight_layout()
            
            img = io.BytesIO()
            fig.savefig(img, format='png', bbox_inches='tight')
            img.seek(0)
            plot_url = base64.b64encode(img.getvalue()).decode('utf8')
            
        finally:
            fig.clear()

    return render_template(
        'index.html', 
        sub_directories=sub_directories, 
        selected_dir=selected_dir, 
        start_xlim=start_xlim,
        end_xlim=end_xlim,
        max_data_index=max_data_index,
        plot_url=plot_url
    )

if __name__ == '__main__':
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
    app.run(debug=True)

