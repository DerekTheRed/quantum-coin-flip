from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

from config import IBM_API_KEY


class QuantumCoin:
    def __init__(self, backend_name="ibm_kingston"):
        self.service = QiskitRuntimeService(
            channel="ibm_quantum_platform",
            token=IBM_API_KEY,
            instance="open-instance"
        )

        self.backend = self.service.backend(backend_name)
        self.sampler = SamplerV2(self.backend)

    def flip(self):
        # Create eight qubits
        qc = QuantumCircuit(8)

        # Hadamard gates
        for i in range(8):
            qc.h(i)

        # Measure
        qc.measure_all()

        # Compile and execute
        compiled = transpile(qc, self.backend)
        job = self.sampler.run([compiled], shots=1)

        result = job.result()
        bits = result[0].data.meas.get_bitstrings()[0]

        # XOR parity
        outcome = bits.count("1") % 2

        return {
            "result": "Tails" if outcome else "Heads",
            "bitstring": bits,
            "job_id": job.job_id(),
            "backend": self.backend.name
        }
