
"""
PharmaSovereign-TN
Simulateur de télémétrie des capteurs de chaîne du froid.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import grpc
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from backend.tunisovereign_core.models import ColdChainSensor

from protos import tunisovereign_pb2
from protos import tunisovereign_pb2_grpc


def generate_packets(sensor_code):
    """Simule trois relevés à 20 minutes d'intervalle."""

    now = datetime.now(timezone.utc)

    temperatures = [
        (now - timedelta(minutes=40), 9.2),
        (now - timedelta(minutes=20), 9.5),
        (now, 9.3),
    ]

    for timestamp, temperature in temperatures:
        yield tunisovereign_pb2.TelemetryPacket(
            node_code=sensor_code,
            governorate="Tunis",
            metric_type="TEMPERATURE",
            value=temperature,
            iso_timestamp=timestamp.isoformat(),
            signature_hmac="SIMULATED-HMAC-NOT-VALIDATED",
        )


def main():
    # Choisir automatiquement un capteur actif lié à une expédition.
    sensor = ColdChainSensor.objects.filter(
        is_active=True,
        shipment__isnull=False,
    ).first()

    if sensor is None:
        print("ERREUR : aucun capteur actif lié à une expédition.")
        return

    print(f"Capteur utilisé : {sensor.sensor_code}")
    print("Envoi de trois températures simulées...")

    with grpc.insecure_channel("localhost:50051") as channel:
        grpc.channel_ready_future(channel).result(timeout=10)

        stub = tunisovereign_pb2_grpc.TelemetryIngestServiceStub(
            channel
        )

        response = stub.StreamTelemetry(
            generate_packets(sensor.sensor_code),
            timeout=20,
        )

        print("\nRéponse du serveur gRPC :")
        print(f"Relevés acceptés : {response.accepted_count}")
        print(f"Anomalie détectée : {response.anomaly_triggered}")
        print(f"Agent thread ID : {response.agent_thread_id}")


if __name__ == "__main__":
    main()
