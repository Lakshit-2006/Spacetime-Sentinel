"""
app.py - Spacetime Sentinel Game Interface (Crash-Proof Linux Edition)
Run with: streamlit run app.py
"""

import json
import subprocess
import sys
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Spacetime Sentinel | Quantum Error Detection",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Spacetime Sentinel: Quantum Error Detection Game")
st.markdown(
    "Design and balance spacetime coherent Pauli checks to protect payload circuits "
    "against physical noise on simulated quantum hardware."
)

st.divider()

col_cfg, col_main = st.columns([1, 2])

with col_cfg:
    st.subheader("1. Mission Setup")
    level = st.selectbox(
        "Challenge Level",
        [
            "Level 1: Clifford Channel (T = 0)",
            "Level 2: Light T-Doping (T = 1)",
            "Level 3: Heavy T-Doping (T = 2)",
            "Level 4: Magic-State Stress Test (T = 4)",
        ],
    )

    t_map = {
        "Level 1: Clifford Channel (T = 0)": 0,
        "Level 2: Light T-Doping (T = 1)": 1,
        "Level 3: Heavy T-Doping (T = 2)": 2,
        "Level 4: Magic-State Stress Test (T = 4)": 4,
    }
    t_val = t_map[level]

    st.subheader("2. Check Configuration")
    checks = st.slider("Ancilla Check Budget", min_value=0, max_value=4, value=1)

    if t_val > 0:
        check_type = st.radio(
            "Select Check Operator",
            options=["Z", "X"],
            help="Z-checks commute with T-gates. X-checks anti-commute and destroy non-Clifford states.",
        )
    else:
        check_type = "Z"

    st.subheader("3. Hardware Environment")
    noise = st.select_slider(
        "Depolarizing Gate Noise Rate (p)",
        options=[0.005, 0.01, 0.02, 0.03, 0.05],
        value=0.01,
        format_func=lambda x: f"{x*100:.1f}%",
    )
    shots = st.select_slider("Shot Budget", options=[1024, 2048, 4096, 8192], value=4096)

    execute_btn = st.button("🚀 Transpile & Run Simulation", type="primary")

with col_main:
    if execute_btn:
        with st.spinner("Executing simulation in isolated process on Qiskit Aer..."):
            cmd = [
                sys.executable,
                "engine.py",
                "--t_count", str(t_val),
                "--checks", str(checks),
                "--check_type", str(check_type),
                "--noise", str(noise),
                "--shots", str(shots),
            ]
            process = subprocess.run(cmd, capture_output=True, text=True)

            if process.returncode != 0:
                st.error(f"Engine execution error:\n{process.stderr}")
                res = None
            else:
                try:
                    res = json.loads(process.stdout.strip())
                except Exception as e:
                    st.error(f"Failed to parse engine output: {e}\nRaw output: {process.stdout}")
                    res = None

        if res:
            # Performance Metric Cards
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Objective Score", f"{res['score']:,}")
            m2.metric("Post-Selected Fidelity", f"{res['post_fidelity']*100:.1f}%")
            m3.metric("Kept-Shot Yield", f"{res['kept_ratio']*100:.1f}%", f"{res['kept_shots']}/{res['total_shots']}")
            m4.metric("Transpiled Depth", res["total_depth"], f"+{res['added_depth']} overhead")

            # Physics Alert Banners
            if t_val > 0 and check_type == "X" and checks > 0:
                st.error(
                    "🚨 **NON-CLIFFORD COMMUTATION COLLAPSE!** You applied an X-check across a T-gate. "
                    "Because $X$ and $T$ do not commute, measuring the check projects and collapses the quantum state, "
                    "destroying fidelity."
                )
            elif checks >= 3:
                discarded_pct = (1.0 - res["kept_ratio"]) * 100.0
                st.warning(
                    f"⚠️ **OVER-CHECKING ATTRITION!** Adding {checks} ancilla checks introduced excess gate noise. "
                    f"{discarded_pct:.1f}% of execution shots failed syndrome verification and were discarded."
                )
            else:
                st.success("✅ **OPTIMAL OPERATION.** Circuit compiled and filtered within safe tolerance.")

            # Performance Progress Bars
            st.subheader("Physics Verification: Fidelity vs. Kept Yield")
            st.write(f"**Post-Selected State Fidelity:** {res['post_fidelity']*100:.1f}%")
            st.progress(float(min(1.0, max(0.0, res["post_fidelity"]))))

            st.write(f"**Kept-Shot Yield (Throughput):** {res['kept_ratio']*100:.1f}%")
            st.progress(float(min(1.0, max(0.0, res["kept_ratio"]))))

            # Hardware Resource Breakdown Table
            st.subheader("Hardware Cost Breakdown")
            cost_df = pd.DataFrame(
                {
                    "Hardware Metric": [
                        "Depth Overhead (Added by Checks)",
                        "Two-Qubit (CX) Gates",
                        "SWAP Gates Inserted",
                        "Accepted Shots",
                        "Discarded Shots",
                    ],
                    "Value": [
                        res["added_depth"],
                        res["cx_count"],
                        res["swap_count"],
                        res["kept_shots"],
                        res["total_shots"] - res["kept_shots"],
                    ],
                }
            )
            st.table(cost_df)
    else:
        st.info("👈 Select mission settings in the sidebar and click **Transpile & Run Simulation** to begin.")
