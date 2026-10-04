import io
import base64
import pandas as pd
import matplotlib
matplotlib.use('Agg') # GUIを使わない設定
import matplotlib.pyplot as plt
from flask import Flask, render_template_string

# --- Ubuntu用の日本語文字化け対策 ---
#matplotlib.rcParams['font.family'] = 'Noto Sans CJK JP'
# マイナス記号「-」の文字化け（豆腐）も同時に防ぐ設定
#matplotlib.rcParams['axes.unicode_minus'] = False


matplotlib.rcParams['font.family'] = 'IPAexGothic'
matplotlib.rcParams['axes.unicode_minus'] = False # マイナス記号の文字化け防止

app = Flask(__name__)

@app.route('/')
def index():
    # pandasでデータフレームを作成
    data = {
        '月': ['1月', '2月', '3月', '4月', '5月'],
        '売上': [120, 150, 180, 130, 210]
    }
    df = pd.DataFrame(data)
    
    # グラフを描画
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(df['月'], df['売上'], marker='o', color='b')
    ax.set_title('月別売上グラフ')
    ax.set_xlabel('月')
    ax.set_ylabel('売上 (万円)')
    ax.grid(True)
    
    # 画像をメモリ上に保存
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close(fig)
    
    # Base64エンコードに変換
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    
    # HTMLを表示
    html = '''
    <h1>pandasとFlaskで作ったグラフ</h1>
    <img src="data:image/png;base64,{{ plot_url }}">
    '''
    return render_template_string(html, plot_url=plot_url)

if __name__ == '__main__':
    app.run(debug=True)
