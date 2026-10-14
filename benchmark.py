"""
benchmark.py - Automated Parameter Sweep & Plot Generator
Generates benchmark_results.csv and benchmark_chart.png.
"""

import matplotlib.pyplot as plt
import pandas as pd
from engine import run_quantum_mission


def run_benchmarks():
    print("Executing benchmark sweep across check configurations...")
    records = []

    # 1. Sweep checks on pure Clifford circuit (T = 0)
    for p in [0.01, 0.02]:
        for k in [0, 1, 2, 3, 4]:
            res = run_quantum_mission(t_count=0, num_checks=k, check_type="Z", gate_error=p, shots=4096)
            records.append({
                "T_Count": 0,
                "Check_Budget": k,
                "Check_Type": "Z",
                "Error_Rate": p,
                "Depth": res["total_depth"],
                "CX_Count": res["cx_count"],
                "Fidelity": res["post_fidelity"],
                "Kept_Ratio": res["kept_ratio"],
                "Score": res["score"],
            })

    # 2. Sweep T-gate doping with Z vs X checks
    for t in [0, 1, 2, 4]:
        for ctype in ["Z", "X"]:
            res = run_quantum_mission(t_count=t, num_checks=1, check_type=ctype, gate_error=0.01, shots=4096)
            records.append({
                "T_Count": t,
                "Check_Budget": 1,
                "Check_Type": ctype,
                "Error_Rate": 0.01,
                "Depth": res["total_depth"],
                "CX_Count": res["cx_count"],
                "Fidelity": res["post_fidelity"],
                "Kept_Ratio": res["kept_ratio"],
                "Score": res["score"],
            })

    df = pd.DataFrame(records)
    df.to_csv("benchmark_results.csv", index=False)
    print("Saved benchmark_results.csv")

    # Generate Report Plots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2), dpi=300)
    plt.subplots_adjust(wspace=0.32, bottom=0.18)

    # Plot 1: Pareto Frontier (Fidelity vs Kept-Shot Ratio)
    df_p01 = df[(df["T_Count"] == 0) & (df["Error_Rate"] == 0.01) & (df["Check_Type"] == "Z")]
    ax1.plot(df_p01["Kept_Ratio"], df_p01["Fidelity"], "o-", color="#1a56db", lw=2, label="Error p = 1.0%")
    for _, row in df_p01.iterrows():
        ax1.annotate(f"{int(row['Check_Budget'])} checks", (row["Kept_Ratio"], row["Fidelity"]),
                     textcoords="offset points", xytext=(-12, 8), fontsize=8)

    ax1.set_title("Post-Selected Fidelity vs. Kept Yield", fontsize=11, fontweight="bold")
    ax1.set_xlabel("Kept-Shot Ratio (P_acc)")
    ax1.set_ylabel("Fidelity (F_post)")
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend()

    # Plot 2: T-Gate Commutation Breakdown
    df_t = df[(df["Check_Budget"] == 1) & (df["Error_Rate"] == 0.01)]
    df_tz = df_t[df_t["Check_Type"] == "Z"]
    df_tx = df_t[df_t["Check_Type"] == "X"]

    ax2.plot(df_tz["T_Count"], df_tz["Fidelity"], "o-", color="#057a55", lw=2, label="Z-Checks (Commuting)")
    ax2.plot(df_tx["T_Count"], df_tx["Fidelity"], "x--", color="#c81e1e", lw=2, label="X-Checks (Non-Commuting)")
    ax2.set_title("T-Gate Commutation Breakdown", fontsize=11, fontweight="bold")
    ax2.set_xlabel("T-Gate Count")
    ax2.set_ylabel("Fidelity (F)")
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend()

    plt.savefig("benchmark_chart.png", bbox_inches="tight")
    print("Saved benchmark_chart.png successfully.")


if __name__ == "__main__":
    run_benchmarks()
