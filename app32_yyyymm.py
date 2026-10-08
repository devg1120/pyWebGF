import io
import base64
import glob
import os
import platform
import pandas as pd
import matplotlib
import json
import traceback

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
BASE_DIR = "./gen_csv/month_data_build/test"

# --- ダッシュボード登録データを保持する簡易リスト ---
DASHBOARD_REGISTRY = []


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

    # 現在の表示モードを取得（デフォルトは通常モード "single"）
    current_mode = request.args.get("mode", "single")

    selected_yyyymm = request.args.get("yyyymm", "")
    if not selected_yyyymm or selected_yyyymm not in date_tree:
        selected_yyyymm = available_yyyymm[0]

    available_dds = date_tree.get(selected_yyyymm, [])
    if not available_dds:
        return (
            f"<h1>エラー: 選択された月 {selected_yyyymm} に有効な日（DD）がありません。</h1>",
            500,
        )

    selected_dd = request.args.get("dd", "")
    if not selected_dd or selected_dd not in available_dds:
        selected_dd = available_dds[0]

    # 期間指定用の開始日・終了日パラメータの取得
    selected_start_dd = request.args.get("start_dd", "")
    selected_end_dd = request.args.get("end_dd", "")

    selected_date = f"{selected_yyyymm}/{selected_dd}"
    date_dir = os.path.join(BASE_DIR, selected_date)
    
    available_switches = sorted(
        [
            os.path.basename(d)
            for d in glob.glob(os.path.join(date_dir, "*"))
            if os.path.isdir(d)
        ]
    )

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
    info_dic = {}
    if selected_switch:
        target_dir = os.path.join(BASE_DIR, selected_date, selected_switch)
        csv_files = sorted(glob.glob(os.path.join(target_dir, "*.csv")))
        csv_filenames = natsorted([os.path.basename(f) for f in csv_files])
        info_json_path = os.path.join(BASE_DIR, selected_date, selected_switch, "info.json")
        if os.path.exists(info_json_path):
            with open(info_json_path, 'r', encoding='utf-8') as f:
                info_dic = json.load(f)

    return render_template(
        "index32.html",
        date_tree=date_tree,
        current_mode=current_mode,
        selected_start_dd=selected_start_dd,
        selected_end_dd=selected_end_dd,
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
        registry=DASHBOARD_REGISTRY,
    )
@app.route("/plot")
def plot_graph():
    mode = request.args.get("mode", "single")
    yyyymm = request.args.get("yyyymm")
    dd = request.args.get("dd")
    switch = request.args.get("switch")
    filename = request.args.get("filename")
    cols = int(request.args.get("cols", 2))
    start_hour = int(request.args.get("start_hour", 8))
    end_hour = int(request.args.get("end_hour", 18))
    desc = request.args.get("desc", "")

    # 期間指定用パラメータ
    start_date_str = request.args.get("start_dd", "")
    end_date_str = request.args.get("end_dd", "")

    if cols == 1:
        fig_size = (14, 4.0)
    elif cols == 4:
        fig_size = (6, 2.8)
    else:
        fig_size = (8, 3.0)

    fig = Figure(figsize=fig_size)
    ax = fig.subplots()

    try:
        df_list = []
        
        # ─── 📊 期間指定モード (range) ───
        if mode == "range" and start_date_str and end_date_str:
            dr = pd.date_range(start=start_date_str, end=end_date_str)
            for d in dr:
                m_str = d.strftime("%Y%m")
                d_str = d.strftime("%d")
                file_path = os.path.join(BASE_DIR, m_str, d_str, switch, filename)
                if os.path.exists(file_path):
                    _df = pd.read_csv(file_path, engine="c")
                    if not _df.empty:
                        df_list.append(_df)
            
            if df_list:
                df = pd.concat(df_list, ignore_index=True)
            else:
                raise FileNotFoundError("指定された期間内にデータファイルが見つかりません。")
                
            start_time = pd.to_datetime(start_date_str) + pd.Timedelta(hours=start_hour)
            end_time = pd.to_datetime(end_date_str) + pd.Timedelta(hours=end_hour, minutes=55)
            x_label_text = f"{start_date_str} ～ {end_date_str}"
            x_tick_format = "%m/%d %H:%M"
            
        # ─── 📅 通常特定日モード (single) ───
        else:
            file_path = os.path.join(BASE_DIR, yyyymm, dd, switch, filename)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"ファイルが見つかりません: {yyyymm}/{dd}")
            df = pd.read_csv(file_path, engine="c")
            
            if not df.empty and len(df.columns) > 0:
                df["日時_temp"] = pd.to_datetime(df.iloc[:, 0], format="mixed", errors='coerce')
                valid_dates = df["日時_temp"].dropna()
                base_date = valid_dates.iloc[0].normalize() if not valid_dates.empty else pd.to_datetime(f"{yyyymm[:4]}-{yyyymm[4:]}-{dd}").normalize()
                df.drop(columns=["日時_temp"], inplace=True)
            else:
                base_date = pd.to_datetime(f"{yyyymm[:4]}-{yyyymm[4:]}-{dd}").normalize()
                
            start_time = base_date + pd.Timedelta(hours=start_hour)
            end_time = base_date + pd.Timedelta(hours=end_hour, minutes=55)
            x_label_text = f"{yyyymm}/{dd}"
            x_tick_format = "%H:%M"

        # ─── 🛠️ 共通データ整形処理 ───
        if len(df.columns) >= 6:
            new_columns = list(df.columns)
            new_columns[:6] = ["日時", "INDEX", "NAME", "STATUS", "項目A", "項目B"]
            df.columns = new_columns
        elif len(df.columns) >= 3:
            new_columns = list(df.columns)
            new_columns[:3] = ["日時", "項目A", "項目B"]
            df.columns = new_columns

        df["日時"] = pd.to_datetime(df["日時"], format="mixed", errors='coerce')
        df = df.dropna(subset=["日時"]).sort_values("日時").reset_index(drop=True)

        df["差分A"] = df["項目A"].diff()
        df["差分B"] = df["項目B"].diff() if "項目B" in df.columns else pd.Series(0, index=df.index)
        df.loc[df["差分A"] < 0, "差分A"] = 0
        df.loc[df["差分B"] < 0, "差分B"] = 0

        df["bps_A"] = (df["差分A"] * 8) / 300
        df["bps_B"] = (df["差分B"] * 8) / 300

        df_filtered = df[(df["日時"] >= start_time) & (df["日時"] <= end_time)]

        fig.set_facecolor("#f0f0f0")
        ax.set_facecolor("#ffffff")

        if not df_filtered.empty:
            ax.fill_between(df_filtered["日時"], df_filtered["bps_A"], color="#00eb0c", alpha=0.9, label="In (bps)")
            ax.plot(df_filtered["日時"], df_filtered["bps_A"], color="#006600", linewidth=0.8)
            if "bps_B" in df_filtered.columns:
                ax.plot(df_filtered["日時"], df_filtered["bps_B"], color="#1000ff", linewidth=1.8, label="Out (bps)")
        else:
            ax.text(0.5, 0.5, "指定された時間帯に\nデータがありません", ha="center", va="center", fontsize=12, color="red")

        ax.grid(True, which="both", color="#cccccc", linestyle="-", linewidth=0.5)
        ax.set_axisbelow(True)

        for spine in ax.spines.values():
            spine.set_color("#000000")
            spine.set_linewidth(0.3)

        ax.set_xlim(start_time, end_time)
        ax.xaxis.set_major_formatter(mdates.DateFormatter(x_tick_format))
        ax.tick_params(labelbottom=True, colors="#000000")
        for label in ax.get_xticklabels():
            label.set_rotation(30)
            label.set_horizontalalignment("right")

        ax.get_yaxis().get_major_formatter().set_scientific(False)

        max_val = 0
        if not df_filtered.empty:
            max_val_a = df_filtered["bps_A"].max() if not df_filtered["bps_A"].isna().all() else 0
            max_val_b = df_filtered["bps_B"].max() if "bps_B" in df_filtered.columns and not df_filtered["bps_B"].isna().all() else 0
            max_val = max(max_val_a, max_val_b)

        if max_val >= 1_000_000:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000_000:,.1f} M"))
            ax.set_ylabel("転送速度 (Mbps)", color="#000000")
        elif max_val >= 1_000:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000:,.0f} K"))
            ax.set_ylabel("転送速度 (Kbps)", color="#000000")
        else:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))
            ax.set_ylabel("転送速度 (bps)", color="#000000")

        interface = filename.replace(".csv", "")
        ax.set_title(f"{switch}: {interface}", color="#000000", fontsize=11, fontweight="bold", loc="left")
        ax.set_title(f"{desc}", color="#000000", fontsize=11, fontweight="bold", loc="right")
        ax.set_xlabel(x_label_text, color="#000000")
        ax.legend(loc="upper left", ncol=2, frameon=True, facecolor="#ffffff", edgecolor="#cccccc")

    except Exception as e:
        print("====== グラフ描画エラー詳細 ======")
        traceback.print_exc()
        print("==================================")
        ax.text(0.5, 0.5, f"エラーが発生しました:\n{type(e).__name__}\n{str(e)}", ha="center", va="center", color="red", fontsize=9)
        ax.set_title(f"{filename} (読込失敗)")

    fig.tight_layout()
    img = io.BytesIO()
    fig.savefig(img, format="png", bbox_inches="tight", dpi=120)
    img.seek(0)
    fig.clear()

    return send_file(img, mimetype="image/png")

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

    # 💡 【追加】現在の表示モードを取得（デフォルトは通常モード "single"）
    current_mode = request.args.get("mode", "single")

    # 選択された日付の取得とフォールバック
    selected_yyyymm = request.args.get('yyyymm', "")
    if not selected_yyyymm or selected_yyyymm not in date_tree:
        selected_yyyymm = available_yyyymm[0] if available_yyyymm else ""
        
    available_dds = date_tree.get(selected_yyyymm, [])
    selected_dd = request.args.get('dd', "")
    if not selected_dd or selected_dd not in available_dds:
        selected_dd = available_dds[0] if available_dds else ""

    # 💡 【追加】期間指定用の開始日・終了日パラメータの取得
    selected_start_dd = request.args.get("start_dd", "")
    selected_end_dd = request.args.get("end_dd", "")

    try:
        selected_cols = int(request.args.get('cols', 2))
    except ValueError:
        selected_cols = 2

    start_hour = int(request.args.get('start_hour', 8))
    end_hour = int(request.args.get('end_hour', 18))

    return render_template(
        'dashboard32.html',
        registry=DASHBOARD_REGISTRY,
        date_tree=date_tree,
        current_mode=current_mode,            # 💡 追加：現在の表示モード
        selected_start_dd=selected_start_dd,  # 💡 追加：開始日
        selected_end_dd=selected_end_dd,      # 💡 追加：終了日
        selected_yyyymm=selected_yyyymm,
        selected_dd=selected_dd,
        available_dds=available_dds,
        selected_cols=selected_cols,
        start_hour=start_hour,
        end_hour=end_hour,
    )

"""
@app.route('/dashboard')
def dashboard():
    date_tree = {}
    yyyymm_dirs = sorted([d for d in glob.glob(os.path.join(BASE_DIR, "*")) if os.path.isdir(d)])
    
    for yyyymm_dir in yyyymm_dirs:
        yyyymm_name = os.path.basename(yyyymm_dir)
        dd_dirs = sorted([d for d in glob.glob(os.path.join(yyyymm_dir, "*")) if os.path.isdir(d)])
        dd_list = [os.path.basename(d) for d in dd_dirs]
        if dd_list:
            date_tree[yyyymm_name] = dd_list

    available_yyyymm = list(date_tree.keys())

    selected_yyyymm = request.args.get('yyyymm', available_yyyymm[0] if available_yyyymm else "")
    if selected_yyyymm not in date_tree and available_yyyymm:
        selected_yyyymm = available_yyyymm[0]
        
    available_dds = date_tree.get(selected_yyyymm, [])
    selected_dd = request.args.get('dd', available_dds[0] if available_dds else "")
    if selected_dd not in available_dds and available_dds:
        selected_dd = available_dds[0]

    try:
        selected_cols = int(request.args.get('cols', 2))
    except ValueError:
        selected_cols = 2

    start_hour = int(request.args.get('start_hour', 8))
    end_hour = int(request.args.get('end_hour', 18))

    return render_template(
        'dashboard32.html',
        registry=DASHBOARD_REGISTRY,
        date_tree=date_tree,
        selected_yyyymm=selected_yyyymm,
        selected_dd=selected_dd,
        available_dds=available_dds,
        selected_cols=selected_cols,
        start_hour=start_hour,
        end_hour=end_hour,
    )
"""

@app.route("/dashboard/add", methods=["POST"])
def dashboard_add():
    yyyymm = request.form.get("yyyymm")
    dd = request.form.get("dd")
    switch = request.form.get("switch")
    filename = request.form.get("filename")
    desc = request.form.get("desc")

    redirect_args = f"?yyyymm={yyyymm}&dd={dd}&switch={switch}"

    if yyyymm and dd and switch and filename:
        exists = any(
            item["yyyymm"] == yyyymm
            and item["dd"] == dd
            and item["switch"] == switch
            and item["filename"] == filename
            and item["desc"] == desc
            for item in DASHBOARD_REGISTRY
        )
        if not exists:
            DASHBOARD_REGISTRY.append(
                {"yyyymm": yyyymm, "dd": dd, "switch": switch, "filename": filename, "desc": desc}
            )

    from flask import redirect, url_for
    return redirect(url_for("index") + redirect_args)


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
