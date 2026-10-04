import io
import base64
import glob
import math
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg') # GUIを使わない設定

# 【変更点】pyplot ではなく Figure オブジェクトを直接インポート
from matplotlib.figure import Figure
from flask import Flask, render_template, request

# --- CentOS 7 / Ubuntu 共通の日本語文字化け対策 ---
matplotlib.rcParams['font.family'] = 'IPAexGothic'
matplotlib.rcParams['axes.unicode_minus'] = False 
# ------------------------------------------------

app = Flask(__name__)
BASE_DIR = "./data_long"

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
    
    # 2. 最大値の動的計算のための初期スキャン
    max_data_index = 11
    if csv_files:
        try:
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
        
        # 【変更点】Figureオブジェクトを直接生成し、そこからサブプロット枠（axes）を作成
        fig = Figure(figsize=(10, 4 * nrows))
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
                    ax.plot(df['月'], df['売上'], marker='o', color='b')
                    ax.set_xlim(start_xlim - 0.5, end_xlim + 0.5)
                    ax.set_title(f'{file_name} の売上グラフ')
                    ax.set_xlabel('月')
                    ax.set_ylabel('売上')
                    ax.grid(True)
                except Exception as e:
                    ax.text(0.5, 0.5, f'エラー:\n{str(e)}', ha='center', va='center')
                    ax.set_title(f'{file_name} (読込失敗)')

            # 余った空白枠の非表示処理
            for j in range(last_index + 1, len(axes)):
                fig.delaxes(axes[j])
                
            # 【変更点】plt.tight_layout() ではなく fig.tight_layout() を使用
            fig.tight_layout()
            
            # 画像の変換
            img = io.BytesIO()
            # 【変更点】fig.savefig() でメモリ上のストリームに出力
            fig.savefig(img, format='png', bbox_inches='tight')
            img.seek(0)
            plot_url = base64.b64encode(img.getvalue()).decode('utf8')
            
        finally:
            # 【変更点】fig.clear() で確実にオブジェクト内部のデータ構造を全解放
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
