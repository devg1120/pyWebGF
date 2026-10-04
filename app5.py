import io
import base64
import glob
import math
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg') # GUIを使わない設定
import matplotlib.pyplot as plt
from flask import Flask, render_template_string, request

# --- CentOS 7 / Ubuntu 共通の日本語文字化け対策 ---
matplotlib.rcParams['font.family'] = 'IPAexGothic'
matplotlib.rcParams['axes.unicode_minus'] = False 
# ------------------------------------------------

app = Flask(__name__)

# CSVが格納されているルートディレクトリ
BASE_DIR = "./data_long"

@app.route('/')
def index():
    # 1. BASE_DIR 直下のサブディレクトリ一覧を自動取得
    #    (例: ['./data/東京支店', './data/大阪支店'] -> ['東京支店', '大阪支店'])
    sub_directories = sorted([
        os.path.basename(d) for d in glob.glob(os.path.join(BASE_DIR, "*")) 
        if os.path.isdir(d)
    ])
    
    if not sub_directories:
        return f"<h1>エラー: {BASE_DIR} 配下にディレクトリが見つかりません。</h1>"
        
    # 2. ユーザーが選択したディレクトリを取得（未選択なら1番目のディレクトリ）
    selected_dir = request.args.get('dir', sub_directories[0])
    
    # 選択されたディレクトリ内のCSVファイルを取得
    target_path = os.path.join(BASE_DIR, selected_dir, "*.csv")
    csv_files = sorted(glob.glob(target_path))
    
    # 3. CSVファイルが存在する場合のみグラフを描画
    plot_url = ""
    if csv_files:
        ncols = 2
        nrows = math.ceil(len(csv_files) / ncols)
        
        fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(10, 4 * nrows))
        
        if len(csv_files) == 1:
            axes = [axes]
        else:
            axes = axes.flatten()
            
        i = 0
        for i, file_path in enumerate(csv_files):
            ax = axes[i]
            file_name = os.path.basename(file_path)
            
            try:
                df = pd.read_csv(file_path)
                ax.plot(df['月'], df['売上'], marker='o', color='b')
                #ax.set_xlim(1, 3)  # 例：2番目（2月）から4番目（4月）の範囲に絞る
                ax.set_xlim(5, 11)  # 6月から12月表示
                ax.set_title(f'{file_name} の売上グラフ')
                ax.set_xlabel('月')
                ax.set_ylabel('売上')
                ax.grid(True)
            except Exception as e:
                ax.text(0.5, 0.5, f'エラー:\n{str(e)}', ha='center', va='center')
                ax.set_title(f'{file_name} (読込失敗)')

        for j in range(i + 1, len(axes)):
            fig.delaxes(axes[j])
            
        plt.tight_layout()
        
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight')
        img.seek(0)
        plt.close(fig)
        
        plot_url = base64.b64encode(img.getvalue()).decode('utf8')

    # 4. HTMLの構築（ドロップダウンメニューとグラフ表示）
    # セレクトボックスが変更されたら、JavaScriptで自動リロードしてパラメータを飛ばします
     # 4. HTMLの構築（ヘッダー固定版）
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>ディレクトリ切り替えグラフ</title>
        <style>
            /* ページ全体の基本設定 */
            body { 
                font-family: sans-serif; 
                margin: 0; 
                padding: 0; 
                /* ヘッダーの高さ分（約140px）だけ上部に余白を作り、グラフが隠れるのを防ぐ */
                padding-top: 140px; 
                background-color: #f9f9f9;
            }
            
            /* ヘッダーを最上部に固定する設定 */
            .fixed-header {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100px; /* ヘッダーの高さ */
                background-color: #ffffff;
                padding: 15px 30px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1); /* 下部にうっすら影をつける */
                z-index: 1000; /* グラフより手前に表示させる */
                box-sizing: border-box;
            }
            
            /* メインコンテンツ（グラフエリア）の調整 */
            .content {
                padding: 20px 30px;
            }
            
            select { padding: 8px; font-size: 16px; }
            h1 { color: #333; margin: 0 0 10px 0; font-size: 24px; }
            h2 { color: #555; margin: 0 0 15px 0; font-size: 18px; }
        </style>
    </head>
    <body>
        <!-- 固定ヘッダーエリア -->
        <div class="fixed-header">
            <h1>データソースの選択</h1>
            <form method="get" action="/">
                <label for="dir-select">ディレクトリ選択: </label>
                <select id="dir-select" name="dir" onchange="this.form.submit()">
                    {% for d in sub_directories %}
                        <option value="{{ d }}" {% if d == selected_dir %}selected{% endif %}>{{ d }}</option>
                    {% endfor %}
                </select>
            </form>
        </div>

        <!-- スクロールするコンテンツエリア -->
        <div class="content">
            <h2>「{{ selected_dir }}」のグラフ一覧</h2>
            {% if plot_url %}
                <img src="data:image/png;base64,{{ plot_url }}">
            {% else %}
                <p>選択されたディレクトリにCSVファイルがありません。</p>
            {% endif %}
        </div>
    </body>
    </html>
    '''
   
    return render_template_string(
        html, 
        sub_directories=sub_directories, 
        selected_dir=selected_dir, 
        plot_url=plot_url
    )

if __name__ == '__main__':
    # 動作確認用にルートディレクトリがなければ自動作成
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
    app.run(debug=True)
    #app.run(host='0.0.0.0', port=80, debug=True)


