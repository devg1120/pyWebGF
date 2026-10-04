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
    
    # 【変更点】時間ベースの範囲パラメータ（デフォルトは 8時 〜 18時）
    start_hour = int(request.args.get('start_hour', 8))
    end_hour = int(request.args.get('end_hour', 18))
    
    # 選択されたディレクトリ内のCSVファイルを取得
    target_path = os.path.join(BASE_DIR, selected_dir, "*.csv")
    csv_files = sorted(glob.glob(target_path))
    
    plot_url = ""
    
    # 2. グラフの描画処理
    if csv_files:
        ncols = 2
        nrows = math.ceil(len(csv_files) / ncols)
        
        fig = Figure(figsize=(14, 5 * nrows)) 
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
                    df = pd.read_csv(file_path)
                    df.columns = ['日時', '項目A', '項目B'] 
                    df['日時'] = pd.to_datetime(df['日時'])
                    
                    # グラフのプロット（全体データを描画）
                    ax.plot(df['日時'], df['項目A'], color='b', label='項目A', linewidth=1)
                    ax.plot(df['日時'], df['項目B'], color='orange', label='項目B', linewidth=1)
                    
                    # --- 【変更点】指定された「時間（Hour）」で表示範囲（xlim）を制限 ---
                    # 基準となる日付を取得（データ内の最初の日付の年月日をベースにする）
                    base_date = df['日時'].iloc[0].normalize() 
                    
                    # ユーザーが指定した開始時刻と終了時刻をTimestampとして作成
                    # 終了時刻は、その時間の「55分」までカバーできるように設定、または次の時間の00分にする
                    start_time = base_date + pd.Timedelta(hours=start_hour)
                    end_time = base_date + pd.Timedelta(hours=end_hour, minutes=55)
                    
                    ax.set_xlim(start_time, end_time)
                    
                    # 目盛りの個別強制表示と回転設定（1行目が隠れる問題の対策済）
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                    ax.tick_params(labelbottom=True) 
                    for label in ax.get_xticklabels():
                        label.set_rotation(30)
                        label.set_horizontalalignment('right')
                    
                    # Y軸のカンマ区切りと指数表記防止
                    ax.get_yaxis().get_major_formatter().set_scientific(False)
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
                
            fig.tight_layout(h_pad=3.0) 
            
            img = io.BytesIO()
            fig.savefig(img, format='png', bbox_inches='tight')
            img.seek(0)
            plot_url = base64.b64encode(img.getvalue()).decode('utf8')
            
        finally:
            fig.clear()

    return render_template(
        'index2.html', 
        sub_directories=sub_directories, 
        selected_dir=selected_dir, 
        start_hour=start_hour,
        end_hour=end_hour,
        plot_url=plot_url
    )

if __name__ == '__main__':
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
    app.run(debug=True)
