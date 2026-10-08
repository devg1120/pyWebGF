import io
import base64
import glob
import os
import platform
import pandas as pd
import matplotlib
import json

matplotlib.use("Agg")  # GUIを使わない設定

import matplotlib.pyplot as plt

from matplotlib.figure import Figure
import matplotlib.dates as mdates
from flask import Flask, render_template, request, send_file

from natsort import natsorted

# --- OS自動判定による日本語文字化け対策 ---
current_os = platform.system()

if current_os == "Windows":
    matplotlib.rcParams["font.family"] = "Yu Gothic"  # Windowsの游ゴシック
elif current_os == "Linux":
    matplotlib.rcParams["font.family"] = "IPAexGothic"  # LinuxのIPAexゴシック
else:
    matplotlib.rcParams["font.family"] = "sans-serif"  # その他のフォールバック用

matplotlib.rcParams["axes.unicode_minus"] = False
# -----------------------------------------------------------------

app = Flask(__name__)
#BASE_DIR = "./data_yyyymm_counter"
BASE_DIR = "./gen_csv/month_data_build/test"


@app.route("/")
def index():
    # 1. 2階層（YYYYMM / DD）の構造を辞書型で取得
    date_tree = {}
    yyyymm_dirs = sorted(
        [d for d in glob.glob(os.path.join(BASE_DIR, "*")) if os.path.isdir(d)]
    )

    for yyyymm_dir in yyyymm_dirs:
        yyyymm_name = os.path.basename(yyyymm_dir)
        dd_dirs = sorted(
            [d for d in glob.glob(os.path.join(yyyymm_dir, "*")) if os.path.isdir(d)]
        )

        dd_list = [os.path.basename(d) for d in dd_dirs]
        if dd_list:
            date_tree[yyyymm_name] = dd_list

    if not date_tree:
        return (
            f"<h1>エラー: {BASE_DIR} 配下に /YYYYMM/DD/ 形式のディレクトリが見つかりません。</h1>",
            500,
        )

    available_yyyymm = list(date_tree.keys())

    # 💡 【不具合対策①】パラメータが空、または存在しない月だった場合はデフォルト値にする
    selected_yyyymm = request.args.get("yyyymm", "")
    if not selected_yyyymm or selected_yyyymm not in date_tree:
        selected_yyyymm = available_yyyymm[0]

    available_dds = date_tree.get(selected_yyyymm, [])
    if not available_dds:
        return (
            f"<h1>エラー: 選択された月 {selected_yyyymm} に有効な日（DD）がありません。</h1>",
            500,
        )

    # 💡 【不具合対策②】パラメータが空、または存在しない日だった場合はデフォルト値にする
    selected_dd = request.args.get("dd", "")
    if not selected_dd or selected_dd not in available_dds:
        selected_dd = available_dds[0]

    selected_date = f"{selected_yyyymm}/{selected_dd}"

    date_dir = os.path.join(BASE_DIR, selected_date)
    available_switches = sorted(
        [
            os.path.basename(d)
            #for d in glob.glob(os.path.join(date_dir, "SWITCH_*"))
            for d in glob.glob(os.path.join(date_dir, "*"))
            if os.path.isdir(d)
        ]
    )

    # 💡 【不具合対策③】パラメータが空、または存在しないスイッチだった場合はデフォルト値にする
    selected_switch = request.args.get("switch", "")
    if not selected_switch or selected_switch not in available_switches:
        selected_switch = available_switches[0] if available_switches else ""

    try:
        selected_cols = int(request.args.get("cols", 2))
    except ValueError:
        selected_cols = 2

    start_hour = int(request.args.get("start_hour", 8))
    end_hour = int(request.args.get("end_hour", 18))

    csv_filenames = []
    info_dic = None
    if selected_switch:
        target_dir = os.path.join(BASE_DIR, selected_date, selected_switch)
        csv_files = sorted(glob.glob(os.path.join(target_dir, "*.csv")))
        #csv_filenames = [os.path.basename(f) for f in csv_files]
        csv_filenames = natsorted([os.path.basename(f) for f in csv_files])
        info_json_path = os.path.join(BASE_DIR, selected_date, selected_switch, "info.json")
        with open(info_json_path, 'r', encoding='utf-8') as f:
              info_dic = json.load(f)

    print(info_dic)
    return render_template(
        "index31.html",
        date_tree=date_tree,
        selected_yyyymm=selected_yyyymm,
        selected_dd=selected_dd,
        available_dds=available_dds,
        switches=available_switches,
        selected_switch=selected_switch,
        selected_cols=selected_cols,
        start_hour=start_hour,
        end_hour=end_hour,
        csv_filenames=csv_filenames,
        info_dic=info_dic,
        registry=DASHBOARD_REGISTRY,  # 登録リストを引き渡す
    )




# 💡 変更点②: 1枚のグラフ画像をオンデマンドで生成して返す「軽量エンドポイント」を新設
@app.route("/plot")
def plot_graph():
    yyyymm = request.args.get("yyyymm")
    dd = request.args.get("dd")
    switch = request.args.get("switch")
    filename = request.args.get("filename")
    cols = int(request.args.get("cols", 2))
    start_hour = int(request.args.get("start_hour", 8))
    end_hour = int(request.args.get("end_hour", 18))
    desc = request.args.get("desc", "")

    file_path = os.path.join(BASE_DIR, yyyymm, dd, switch, filename)

    if cols == 1:
        fig_size = (14, 4.0)
    elif cols == 4:
        fig_size = (6, 2.8)
    else:
        fig_size = (8, 3.0)

    fig = Figure(figsize=fig_size)
    ax = fig.subplots()

    try:
        df = pd.read_csv(file_path, engine="c")
        if len(df.columns) >= 3:
            #df.columns = ["日時", "項目A", "項目B"]
            df.columns = ["日時", "INDEX", "NAME", "STATUS","項目A", "項目B"]
        df["日時"] = pd.to_datetime(df["日時"], format="mixed")

        df["差分A"] = df["項目A"].diff()
        df["差分B"] = df["項目B"].diff()
        df.loc[df["差分A"] < 0, "差分A"] = 0
        df.loc[df["差分B"] < 0, "差分B"] = 0

        df["bps_A"] = (df["差分A"] * 8) / 300
        df["bps_B"] = (df["差分B"] * 8) / 300

        base_date = df["日時"].iloc[0].normalize()
        start_time = base_date + pd.Timedelta(hours=start_hour)
        end_time = base_date + pd.Timedelta(hours=end_hour, minutes=55)

        df_filtered = df[(df["日時"] >= start_time) & (df["日時"] <= end_time)]

        # =================================================================
        # 🎨 MRTG Like スタイルの適用箇所
        # =================================================================
        fig.set_facecolor("#f0f0f0")
        ax.set_facecolor("#ffffff")

        if not df_filtered.empty:
            ax.fill_between(
                df_filtered["日時"],
                df_filtered["bps_A"],
                color="#00eb0c",
                alpha=0.9,
                label="In (bps)",
            )
            ax.plot(
                df_filtered["日時"],
                df_filtered["bps_A"],
                color="#006600",
                linewidth=0.8,
            )
            ax.plot(
                df_filtered["日時"],
                df_filtered["bps_B"],
                color="#1000ff",
                linewidth=1.8,
                label="Out (bps)",
            )

        ax.grid(True, which="both", color="#cccccc", linestyle="-", linewidth=0.5)
        ax.set_axisbelow(True)

        for spine in ax.spines.values():
            spine.set_color("#000000")
            spine.set_linewidth(0.3)
        # =================================================================

        ax.set_xlim(start_time, end_time)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.tick_params(labelbottom=True, colors="#000000")
        for label in ax.get_xticklabels():
            label.set_rotation(30)
            label.set_horizontalalignment("right")

        ax.get_yaxis().get_major_formatter().set_scientific(False)

        max_val = (
            max(df_filtered["bps_A"].max(), df_filtered["bps_B"].max())
            if not df_filtered.empty
            else 0
        )
        if max_val >= 1_000_000:
            ax.get_yaxis().set_major_formatter(
                matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000_000:,.1f} M")
            )
            ax.set_ylabel("転送速度 (Mbps)", color="#000000")
        elif max_val >= 1_000:
            ax.get_yaxis().set_major_formatter(
                matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000:,.0f} K")
            )
            ax.set_ylabel("転送速度 (Kbps)", color="#000000")
        else:
            ax.get_yaxis().set_major_formatter(
                matplotlib.ticker.StrMethodFormatter("{x:,.0f}")
            )
            ax.set_ylabel("転送速度 (bps)", color="#000000")

        interface = filename.replace(".csv","")
        ax.set_title(
            f"{switch}: {interface}",
            color="#000000",
            fontsize=11,
            fontweight="bold",
            loc="left",
        )
        ax.set_title(
            f"{desc}",
            color="#000000",
            fontsize=11,
            fontweight="bold",
            loc="right",
        )
        ax.set_xlabel(f"{yyyymm}/{dd}", color="#000000")
        ax.legend(
            loc="upper left",
            ncol=2,
            frameon=True,
            facecolor="#ffffff",
            edgecolor="#cccccc",
        )

    except Exception as e:
        ax.text(0.5, 0.5, f"エラー:\n{str(e)}", ha="center", va="center")
        ax.set_title(f"{filename} (読込失敗)")

    fig.tight_layout()
    img = io.BytesIO()
    fig.savefig(img, format="png", bbox_inches="tight", dpi=120)
    img.seek(0)
    fig.clear()

    return send_file(img, mimetype="image/png")


# --- ダッシュボード登録データを保持する簡易リスト ---
DASHBOARD_REGISTRY = []


# --- [変更] パターンA：表示対象日を一括切り替えできるダッシュボード画面 ---
@app.route('/dashboard')
def dashboard():
    # 1. メインと同様に2階層（YYYYMM / DD）の構造を辞書型で取得
    date_tree = {}
    yyyymm_dirs = sorted([d for d in glob.glob(os.path.join(BASE_DIR, "*")) if os.path.isdir(d)])
    
    for yyyymm_dir in yyyymm_dirs:
        yyyymm_name = os.path.basename(yyyymm_dir)
        dd_dirs = sorted([d for d in glob.glob(os.path.join(yyyymm_dir, "*")) if os.path.isdir(d)])
        
        dd_list = [os.path.basename(d) for d in dd_dirs]
        if dd_list:
            date_tree[yyyymm_name] = dd_list

    available_yyyymm = list(date_tree.keys())

    # 2. パラメータから現在ダッシュボードで選択された日付を取得（デフォルトは最新または先頭データ）
    selected_yyyymm = request.args.get('yyyymm', available_yyyymm[0] if available_yyyymm else "")
    
    # 選択された月が存在しない場合のフォールバック
    if selected_yyyymm not in date_tree and available_yyyymm:
        selected_yyyymm = available_yyyymm[0]
        
    available_dds = date_tree.get(selected_yyyymm, [])
    selected_dd = request.args.get('dd', available_dds[0] if available_dds else "")
    
    # 選択された日が存在しない場合のフォールバック
    if selected_dd not in available_dds and available_dds:
        selected_dd = available_dds[0]

    # 3. 表示列数・時間の取得
    try:
        selected_cols = int(request.args.get('cols', 2))
    except ValueError:
        selected_cols = 2

    start_hour = int(request.args.get('start_hour', 8))
    end_hour = int(request.args.get('end_hour', 18))

    return render_template(
        'dashboard29.html',
        registry=DASHBOARD_REGISTRY,
        date_tree=date_tree,
        selected_yyyymm=selected_yyyymm,
        selected_dd=selected_dd,
        available_dds=available_dds,
        selected_cols=selected_cols,
        start_hour=start_hour,
        end_hour=end_hour
    )

"""
@app.route("/dashboard")
def dashboard():
    # メイン画面に戻るための選択状態を取得
    yyyymm = request.args.get("yyyymm", "")
    dd = request.args.get("dd", "")
    switch = request.args.get("switch", "")

    # グラフの表示列数・時間
    try:
        selected_cols = int(request.args.get("cols", 2))
    except ValueError:
        selected_cols = 2

    start_hour = int(request.args.get("start_hour", 8))
    end_hour = int(request.args.get("end_hour", 18))

    return render_template(
        "dashboard29.html",
        registry=DASHBOARD_REGISTRY,
        selected_cols=selected_cols,
        start_hour=start_hour,
        end_hour=end_hour,
        # ✨メインに戻るためのパラメータをHTMLに引き渡す
        yyyymm=yyyymm,
        dd=dd,
        switch=switch,
    )
"""

# --- ダッシュボードへの登録処理エンドポイント ---
@app.route("/dashboard/add", methods=["POST"])
def dashboard_add():
    yyyymm = request.form.get("yyyymm")
    dd = request.form.get("dd")
    switch = request.form.get("switch")
    filename = request.form.get("filename")

    redirect_args = f"?yyyymm={yyyymm}&dd={dd}&switch={switch}"

    if yyyymm and dd and switch and filename:
        exists = any(
            item["yyyymm"] == yyyymm
            and item["dd"] == dd
            and item["switch"] == switch
            and item["filename"] == filename
            for item in DASHBOARD_REGISTRY
        )
        if not exists:
            DASHBOARD_REGISTRY.append(
                {"yyyymm": yyyymm, "dd": dd, "switch": switch, "filename": filename}
            )

    from flask import redirect, url_for

    return redirect(url_for("index") + redirect_args)


# --- ダッシュボードからの削除処理エンドポイント ---
@app.route("/dashboard/delete", methods=["POST"])
def dashboard_delete():
    idx = int(request.form.get("index", -1))
    if 0 <= idx < len(DASHBOARD_REGISTRY):
        DASHBOARD_REGISTRY.pop(idx)

    from flask import redirect, url_for

    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
    app.run(debug=True)
