
"""
PharmaSovereign-TN - gRPC Cold-Chain Telemetry Server
Receives temperature readings and stores them in PostgreSQL.
"""

import os
import sys
import time
from datetime import datetime, timedelta
from concurrent import futures

import grpc
import django

# Ajouter la racine du projet au chemin Python
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Initialiser Django avant d'importer les modèles
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from protos import tunisovereign_pb2
from protos import tunisovereign_pb2_grpc

from django.utils import timezone
from backend.tunisovereign_core.models import (
    ColdChainSensor,
    ColdChainReading,
    PharmaAnomaly,
)


class TelemetryIngestServicer(
    tunisovereign_pb2_grpc.TelemetryIngestServiceServicer
):
    """
    Service gRPC de réception de la télémétrie pharmaceutique.
    """

    def StreamTelemetry(self, request_iterator, context):
        accepted = 0
        anomaly_triggered = False
        thread_id = ""

        for packet in request_iterator:

            # Pour cette première version, nous traitons les températures.
            if packet.metric_type.upper() != "TEMPERATURE":
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    "Only TEMPERATURE telemetry is supported."
                )

            # Retrouver le capteur à partir de son code.
            try:
                sensor = ColdChainSensor.objects.select_related(
                    "shipment__batch"
                ).get(sensor_code=packet.node_code)
            except ColdChainSensor.DoesNotExist:
                context.abort(
                    grpc.StatusCode.NOT_FOUND,
                    f"Unknown sensor: {packet.node_code}"
                )

            if not sensor.shipment_id:
                context.abort(
                    grpc.StatusCode.FAILED_PRECONDITION,
                    "This sensor is not linked to a shipment."
                )

            # Convertir la date ISO reçue par gRPC.
            try:
                recorded_at = datetime.fromisoformat(
                    packet.iso_timestamp.replace("Z", "+00:00")
                )
                if timezone.is_naive(recorded_at):
                    recorded_at = timezone.make_aware(recorded_at)
            except ValueError:
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    "Invalid ISO timestamp."
                )

            # Enregistrer le relevé dans PostgreSQL.
            reading = ColdChainReading.objects.create(
                sensor=sensor,
                shipment=sensor.shipment,
                recorded_at=recorded_at,
                temperature_c=packet.value,
                signature_hmac=packet.signature_hmac,
                ingestion_protocol="gRPC",
            )

            accepted += 1

            # Seuil de température : excursion supérieure à 8.5 °C.
            if packet.value > 8.5:
                shipment = sensor.shipment
                batch = shipment.batch

                # Chercher les relevés > 8.5 °C sur les 30 dernières minutes.
                recent_readings = ColdChainReading.objects.filter(
                    shipment=shipment,
                    temperature_c__gt=8.5,
                    recorded_at__gte=recorded_at - timedelta(hours=1),
                    recorded_at__lte=recorded_at,
                ).order_by("recorded_at")

                first = recent_readings.first()
                last = recent_readings.last()

                if (
                    first is not None
                    and last is not None
                    and last.recorded_at - first.recorded_at
                    >= timedelta(minutes=30)
                ):
                    anomaly_triggered = True
                    thread_id = (
                        f"grpc-cold-chain-{packet.node_code}-{accepted}"
                    )

                    # Éviter de créer plusieurs anomalies identiques non résolues.
                    already_exists = PharmaAnomaly.objects.filter(
                        batch=batch,
                        anomaly_type="TEMP_EXCURSION",
                        is_resolved=False,
                    ).exists()

                    if not already_exists:
                        PharmaAnomaly.objects.create(
                            batch=batch,
                            shipment=shipment,
                            reading=reading,
                            anomaly_type="TEMP_EXCURSION",
                            severity="CRITICAL",
                            description=(
                                "Temperature above 8.5 °C for at least "
                                "30 minutes, received through gRPC."
                            ),
                            detected_at=timezone.now(),
                        )

        return tunisovereign_pb2.IngestAck(
            accepted_count=accepted,
            anomaly_triggered=anomaly_triggered,
            agent_thread_id=thread_id,
        )

    def TriggerUrgentAudit(self, request, context):
        """
        Enregistre une demande d'audit urgent.
        Cette opération ne crée pas encore de preuve ZK ou blockchain.
        """

        try:
            sensor = ColdChainSensor.objects.select_related(
                "shipment__batch"
            ).get(sensor_code=request.node_code)
        except ColdChainSensor.DoesNotExist:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Unknown sensor: {request.node_code}"
            )

        if not sensor.shipment_id:
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                "This sensor is not linked to a shipment."
            )

        PharmaAnomaly.objects.create(
            batch=sensor.shipment.batch,
            shipment=sensor.shipment,
            anomaly_type="AUTH_RISK",
            severity="HIGH",
            description=f"Urgent audit requested: {request.reason}",
            detected_at=timezone.now(),
        )

        return tunisovereign_pb2.AuditResponse(
            status="AUDIT_RECORDED_PENDING_REVIEW",
            tx_hash="",
        )


def serve(port=50051):
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=8)
    )

    tunisovereign_pb2_grpc.add_TelemetryIngestServiceServicer_to_server(
        TelemetryIngestServicer(),
        server,
    )

    server.add_insecure_port(f"[::]:{port}")

    print(
        f"[PharmaSovereign-TN] gRPC server listening on port {port}"
    )

    server.start()

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve()
