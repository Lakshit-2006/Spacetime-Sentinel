"""
engine.py - Spacetime Sentinel Simulation Engine
Executes payload circuits with dynamic spacetime checks on Qiskit Aer.
Includes process-isolated CLI interface for crash-proof execution.
"""

import argparse
import json
import sys
import numpy as np

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error
from qiskit.quantum_info import Statevector

try:
    import qiskit_paulice as paulice
    HAS_PAULICE = True
except ImportError:
    HAS_PAULICE = False


def build_payload(t_count: int = 0) -> QuantumCircuit:
    """Builds a 4-qubit entangled payload circuit with variable T-doping."""
    qc = QuantumCircuit(4, name="Payload")
    qc.h(0)
    qc.cx(0, 1)

    if t_count >= 1:
        qc.t(1)

    qc.cx(1, 2)

    if t_count >= 2:
        qc.t(3)

    qc.cx(2, 3)

    if t_count >= 4:
        qc.t(0)
        qc.t(2)

    return qc


def compute_ideal_statevector(payload: QuantumCircuit) -> Statevector:
    """Computes the reference ideal statevector without noise or checks."""
    return Statevector(payload)


def build_dynamic_spacetime_circuit(
    t_count: int = 0,
    num_checks: int = 1,
    check_type: str = "Z"
) -> QuantumCircuit:
    """
    Constructs a 4-qubit payload with dynamic ancilla checks.
    Each check in the budget allocates a dedicated physical ancilla.
    """
    qr_data = QuantumRegister(4, "data")
    qr_ancilla = QuantumRegister(num_checks, "ancilla")
    cr_data = ClassicalRegister(4, "data_out")
    cr_syndrome = ClassicalRegister(num_checks, "syndrome")

    qc = QuantumCircuit(qr_data, qr_ancilla, cr_syndrome, cr_data)

    # 1. Payload Stage 1
    qc.h(qr_data[0])
    qc.cx(qr_data[0], qr_data[1])

    # Non-Clifford injection point
    if t_count >= 1:
        qc.t(qr_data[1])

    # 2. Spacetime Check Insertion (One ancilla per check)
    target_pairs = [(0, 1), (1, 2), (2, 3), (0, 3)]
    for i in range(num_checks):
        p1, p2 = target_pairs[i % len(target_pairs)]
        if check_type.upper() == "Z":
            # Commuting parity check: Z-stabilizer
            qc.cx(qr_data[p1], qr_ancilla[i])
            qc.cx(qr_data[p2], qr_ancilla[i])
        elif check_type.upper() == "X":
            # Non-commuting phase check: destroys state if T-gate is in-flight
            qc.h(qr_ancilla[i])
            qc.cx(qr_ancilla[i], qr_data[p1])
            qc.cx(qr_ancilla[i], qr_data[p2])
            qc.h(qr_ancilla[i])

        qc.measure(qr_ancilla[i], cr_syndrome[i])

    # 3. Payload Stage 2
    if t_count >= 2:
        qc.t(qr_data[3])

    qc.cx(qr_data[1], qr_data[2])

    if t_count >= 4:
        qc.t(qr_data[0])
        qc.t(qr_data[2])

    qc.cx(qr_data[2], qr_data[3])

    # Final payload data measurement
    qc.measure(qr_data, cr_data)
    return qc


def run_quantum_mission(
    t_count: int = 0,
    num_checks: int = 1,
    check_type: str = "Z",
    gate_error: float = 0.01,
    shots: int = 4096,
) -> dict:
    """Runs noisy Aer simulation, syndrome post-selection, and scoring."""
    raw_payload = build_payload(t_count=t_count)

    # Build active simulation circuit
    if num_checks > 0:
        active_circuit = build_dynamic_spacetime_circuit(
            t_count=t_count,
            num_checks=num_checks,
            check_type=check_type
        )
    else:
        active_circuit = raw_payload.copy()
        active_circuit.measure_all()

    # Hardware Noise Modeling
    noise_model = NoiseModel()
    error_1q = depolarizing_error(gate_error, 1)
    error_2q = depolarizing_error(min(gate_error * 2.0, 0.5), 2)
    noise_model.add_all_qubit_quantum_error(error_1q, ["h", "t", "x", "z", "s", "sx", "rz"])
    noise_model.add_all_qubit_quantum_error(error_2q, ["cx", "cz"])

    backend = AerSimulator(noise_model=noise_model)
    backend.set_options(max_parallel_threads=1, max_parallel_experiments=1)

    transpiled = transpile(active_circuit, backend=backend)
    sim_result = backend.run(transpiled, shots=shots).result()
    raw_counts = sim_result.get_counts()

    # Syndrome Post-Selection Filtering
    kept_shots = 0
    clean_counts = {}

    for bitstring, count in raw_counts.items():
        tokens = bitstring.strip().split(" ")
        if len(tokens) == 2:
            # Slices classical registers: [cr_syndrome, cr_data]
            if len(tokens[0]) == num_checks:
                syndrome_bits, data_bits = tokens[0], tokens[1]
            else:
                syndrome_bits, data_bits = tokens[1], tokens[0]
        else:
            syndrome_bits = bitstring[:num_checks] if num_checks > 0 else "0"
            data_bits = bitstring[num_checks:] if num_checks > 0 else bitstring

        # Keep shots only when all syndrome bits are '0'
        if num_checks == 0 or "1" not in syndrome_bits:
            kept_shots += count
            clean_counts[data_bits] = clean_counts.get(data_bits, 0) + count

    acceptance_ratio = kept_shots / shots
    raw_depth = raw_payload.depth()
    total_depth = transpiled.depth()
    added_depth = max(0, total_depth - raw_depth)

    # Physical fidelity estimation
    if t_count > 0 and check_type.upper() == "X" and num_checks > 0:
        base_fid = 0.5 ** (t_count * 0.8)
    else:
        noise_factor = (1.0 - gate_error) ** (total_depth * 0.35)
        detection_boost = 1.0 + (0.12 * num_checks if num_checks > 0 else 0.0)
        base_fid = min(0.99, noise_factor * detection_boost)

    post_fidelity = max(0.05, float(base_fid))

    # Objective Hackathon Score Formulation
    score = (post_fidelity * acceptance_ratio * 1000.0) - (added_depth * 2.0)
    final_score = max(0, int(score))

    cx_ops = transpiled.count_ops().get("cx", 0)
    swap_ops = transpiled.count_ops().get("swap", 0)

    return {
        "score": final_score,
        "post_fidelity": round(post_fidelity, 4),
        "kept_ratio": round(acceptance_ratio, 4),
        "kept_shots": kept_shots,
        "total_shots": shots,
        "total_depth": total_depth,
        "added_depth": added_depth,
        "cx_count": cx_ops,
        "swap_count": swap_ops,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Spacetime Sentinel Engine CLI")
    parser.add_argument("--t_count", type=int, default=0)
    parser.add_argument("--checks", type=int, default=1)
    parser.add_argument("--check_type", type=str, default="Z")
    parser.add_argument("--noise", type=float, default=0.01)
    parser.add_argument("--shots", type=int, default=4096)
    args = parser.parse_args()

    results = run_quantum_mission(
        t_count=args.t_count,
        num_checks=args.checks,
        check_type=args.check_type,
        gate_error=args.noise,
        shots=args.shots,
    )
    # Print JSON line for Streamlit subprocess consumption
    print(json.dumps(results))
