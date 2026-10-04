import io
import base64
import glob
import math
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg') # GUIを使わない設定
import matplotlib.pyplot as plt
from flask import Flask, render_template_string

# --- CentOS 7 / Ubuntu 共通の日本語文字化け対策 ---
matplotlib.rcParams['font.family'] = 'IPAexGothic'
matplotlib.rcParams['axes.unicode_minus'] = False 
# ------------------------------------------------

app = Flask(__name__)

@app.route('/')
def index():
    # 1. カレントディレクトリから「.csv」ファイルをすべて取得
    csv_files = sorted(glob.glob("./csv/*.csv"))
    
    if not csv_files:
        return "<h1>CSVファイルが見つかりません。</h1>"
    
    # 2. グラフの配置（2列固定、行数はファイル数から自動計算）
    ncols = 2
    nrows = math.ceil(len(csv_files) / ncols)
    
    # 全体のグラフサイズを決定（1グラフあたり横5×縦4インチ計算）
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(10, 4 * nrows))
    
    # 1個のグラフしか無い場合や、多次元配列（行列）を1次元配列にフラット化する処理
    if len(csv_files) == 1:
        axes = [axes]
    else:
        axes = axes.flatten()
        
    # 3. 各CSVファイルをループ処理してグラフを描画
    for i, file_path in enumerate(csv_files):
        ax = axes[i]
        file_name = os.path.basename(file_path)
        
        try:
            # CSVの読み込み
            df = pd.read_csv(file_path)
            
            # 折れ線グラフを描画
            ax.plot(df['月'], df['売上'], marker='o', color='b')
            ax.set_title(f'{file_name} の売上グラフ')
            ax.set_xlabel('月')
            ax.set_ylabel('売上')
            ax.grid(True)
            
        except Exception as e:
            ax.text(0.5, 0.5, f'エラー:\n{str(e)}', ha='center', va='center')
            ax.set_title(f'{file_name} (読込失敗)')

    # 4. 余った空白の枠（プロット領域）を非表示にする
    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])
        
    # 全体のレイアウトを綺麗に整える
    plt.tight_layout()
    
    # 5. 画像をメモリ上に保存してBase64に変換
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close(fig)
    
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    
    # HTMLを表示
    html = '''
    <h1>複数CSVデータ 2列並びグラフ</h1>
    <img src="data:image/png;base64,{{ plot_url }}">
    '''
    return render_template_string(html, plot_url=plot_url)

if __name__ == '__main__':
    app.run(debug=True)

