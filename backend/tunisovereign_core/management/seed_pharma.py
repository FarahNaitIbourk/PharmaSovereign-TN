import hashlib
from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from backend.tunisovereign_core.models import (
    AgentLoopExecution,
    BatchScan,
    ColdChainReading,
    ColdChainSensor,
    DrugAuthenticityReceipt,
    Medicine,
    MedicineBatch,
    PharmaAnomaly,
    PharmaFacility,
    Shipment,
    StakeholderUser,
)


class Command(BaseCommand):
    help = "Create an idempotent synthetic PharmaSovereign-TN demonstration dataset."

    @transaction.atomic
    def handle(self, *args, **options):
        # Fixed timestamp keeps the demo readings stable across reruns.
        now = timezone.make_aware(datetime(2026, 11, 15, 12, 0, 0))

        # 1. Pharmaceutical facilities (synthetic demo scenario)
        pct, _ = PharmaFacility.objects.update_or_create(
            code="DEMO-PCT-TUN",
            defaults={
                "name": "Depot central PCT - simulation",
                "facility_type": "PCT_DEPOT",
                "governorate": "Tunis",
                "address": "Adresse fictive pour la demonstration universitaire",
                "is_active": True,
            },
        )

        sfax_hospital, _ = PharmaFacility.objects.update_or_create(
            code="DEMO-HOSP-SFAX",
            defaults={
                "name": "Hopital Hedi Chaker - scenario demo",
                "facility_type": "HOSPITAL",
                "governorate": "Sfax",
                "address": "Sfax, Tunisie - donnees de demonstration",
                "is_active": True,
            },
        )

        tunis_hospital, _ = PharmaFacility.objects.update_or_create(
            code="DEMO-HOSP-TUN",
            defaults={
                "name": "Hopital Charles Nicolle - scenario demo",
                "facility_type": "HOSPITAL",
                "governorate": "Tunis",
                "address": "Tunis, Tunisie - donnees de demonstration",
                "is_active": True,
            },
        )

        # 2. A demo pharmacist/auditor account for recording scans.
        auditor, auditor_created = StakeholderUser.objects.get_or_create(
            username="demo_pct_auditor",
            defaults={
                "first_name": "Demo",
                "last_name": "Auditor",
                "email": "demo.auditor@example.invalid",
                "role": "REGIONAL_AUDITOR",
                "governorate": "Tunis",
                "is_active": True,
            },
        )
        if auditor_created:
            auditor.set_unusable_password()
            auditor.save(update_fields=["password"])

        # 3. Medicine and two traceable batches.
        insulin, _ = Medicine.objects.update_or_create(
            product_code="DEMO-MED-INS-001",
            defaults={
                "name": "Insuline - produit de demonstration",
                "active_ingredient": "Insuline (exemple pedagogique)",
                "manufacturer": "Fabricant fictif - demonstration",
                "cold_chain_required": True,
                "min_storage_temp_c": 2.0,
                "max_storage_temp_c": 8.0,
            },
        )

        batch_sfax, _ = MedicineBatch.objects.update_or_create(
            batch_number="DEMO-INS-SFAX-001",
            defaults={
                "medicine": insulin,
                "serial_number": "DEMO-SERIAL-SFAX-001",
                "manufacturing_date": date(2026, 2, 1),
                "expiry_date": date(2027, 12, 31),
                "assigned_governorate": "Sfax",
                "authenticity_status": "PENDING",
                "quantity": 500,
            },
        )

        batch_tunis, _ = MedicineBatch.objects.update_or_create(
            batch_number="DEMO-INS-TUN-002",
            defaults={
                "medicine": insulin,
                "serial_number": "DEMO-SERIAL-TUN-002",
                "manufacturing_date": date(2026, 2, 1),
                "expiry_date": date(2027, 12, 31),
                "assigned_governorate": "Tunis",
                "authenticity_status": "PENDING",
                "quantity": 400,
            },
        )

        # 4. Shipments from the simulated central depot.
        shipment_sfax, _ = Shipment.objects.update_or_create(
            tracking_code="DEMO-SHIP-SFAX-001",
            defaults={
                "batch": batch_sfax,
                "origin": pct,
                "destination": sfax_hospital,
                "status": "IN_TRANSIT",
                "shipped_at": now - timedelta(hours=2),
                "received_at": None,
            },
        )

        shipment_tunis, _ = Shipment.objects.update_or_create(
            tracking_code="DEMO-SHIP-TUN-002",
            defaults={
                "batch": batch_tunis,
                "origin": pct,
                "destination": tunis_hospital,
                "status": "IN_TRANSIT",
                "shipped_at": now - timedelta(hours=2),
                "received_at": None,
            },
        )

        # 5. Sensors attached to each shipment.
        sensor_sfax, _ = ColdChainSensor.objects.update_or_create(
            sensor_code="DEMO-SENSOR-SFAX-001",
            defaults={
                "sensor_type": "TEMP_HUMIDITY",
                "shipment": shipment_sfax,
                "is_active": True,
                "installed_at": now - timedelta(hours=2),
            },
        )

        sensor_tunis, _ = ColdChainSensor.objects.update_or_create(
            sensor_code="DEMO-SENSOR-TUN-002",
            defaults={
                "sensor_type": "TEMP_HUMIDITY",
                "shipment": shipment_tunis,
                "is_active": True,
                "installed_at": now - timedelta(hours=2),
            },
        )

        # 6. Cold-chain readings. The second shipment has readings above
        # 8.5 C spanning 40 minutes; all values are synthetic.
        normal_readings = [
            (now - timedelta(minutes=70), 5.2),
            (now - timedelta(minutes=50), 5.4),
            (now - timedelta(minutes=30), 5.3),
        ]
        excursion_readings = [
            (now - timedelta(minutes=90), 9.2),
            (now - timedelta(minutes=70), 9.5),
            (now - timedelta(minutes=50), 9.3),
        ]

        created_readings = {}
        for sensor, shipment, readings, prefix in [
            (sensor_sfax, shipment_sfax, normal_readings, "SFAX"),
            (sensor_tunis, shipment_tunis, excursion_readings, "TUN"),
        ]:
            for index, (recorded_at, temperature) in enumerate(readings, start=1):
                reading, _ = ColdChainReading.objects.get_or_create(
                    sensor=sensor,
                    shipment=shipment,
                    recorded_at=recorded_at,
                    defaults={
                        "temperature_c": temperature,
                        "humidity_pct": 45.0,
                        "signature_hmac": f"SIMULATED-HMAC-{prefix}-{index}",
                        "ingestion_protocol": "SIMULATOR",
                    },
                )
                created_readings[f"{prefix}-{index}"] = reading

        # 7. GS1-like scan events: one authorized, one outside assigned governorate.
        BatchScan.objects.get_or_create(
            batch=batch_sfax,
            facility=sfax_hospital,
            scan_reference="DEMO-SCAN-SFAX-OK-001",
            defaults={
                "scanned_by": auditor,
                "is_authorized": True,
            },
        )

        BatchScan.objects.get_or_create(
            batch=batch_tunis,
            facility=sfax_hospital,
            scan_reference="DEMO-SCAN-TUN-WRONG-GOV-002",
            defaults={
                "scanned_by": auditor,
                "is_authorized": False,
            },
        )

        # 8. Explicitly recorded demo anomalies (not claimed as ML output).
        PharmaAnomaly.objects.get_or_create(
            batch=batch_tunis,
            anomaly_type="TEMP_EXCURSION",
            description=(
                "SIMULATION: temperature readings above 8.5 C "
                "span 40 minutes (9.2, 9.5, 9.3 C)."
            ),
            defaults={
                "shipment": shipment_tunis,
                "reading": created_readings["TUN-3"],
                "severity": "CRITICAL",
                "detection_score": 0.99,
            },
        )

        PharmaAnomaly.objects.get_or_create(
            batch=batch_tunis,
            anomaly_type="GOV_MISMATCH",
            description=(
                "SIMULATION: batch assigned to Tunis was scanned "
                "at a facility in Sfax."
            ),
            defaults={
                "shipment": shipment_tunis,
                "severity": "HIGH",
                "detection_score": 0.98,
            },
        )

        # 9. Agent execution and pending authenticity receipts.
        execution, _ = AgentLoopExecution.objects.get_or_create(
            thread_id="demo-pharma-cold-chain-thread-001",
            defaults={
                "trigger_source": "SEED_DEMO_COLD_CHAIN",
                "darja_transcript": "",
                "parsed_intent_json": {
                    "scenario": "synthetic_pharma_cold_chain_demo"
                },
                "mcp_tools_invoked": [],
                "skills_executed": [
                    "ColdChainThermalDriftSkill",
                    "GS1BarcodeAndLotVerifierSkill",
                ],
                "final_recommendation": (
                    "SIMULATION: isolate the affected batch, verify "
                    "its custody history, and request a human audit."
                ),
                "confidence_score": 0.95,
            },
        )

        for batch in [batch_sfax, batch_tunis]:
            commitment = hashlib.sha256(
                f"PHARMASOVEREIGN-DEMO|{batch.batch_number}|{batch.serial_number}".encode(
                    "utf-8"
                )
            ).hexdigest()

            DrugAuthenticityReceipt.objects.get_or_create(
                commitment_hash=commitment,
                defaults={
                    "batch": batch,
                    "agent_execution": execution,
                    "public_inputs_json": {
                        "batch_number": batch.batch_number,
                        "scenario": "synthetic_demo_only",
                    },
                    "transaction_hash": None,
                    "block_number": None,
                    "network_name": "DEMO-NOT-ANCHORED",
                    "verification_status": "PENDING",
                },
            )

        self.stdout.write(self.style.SUCCESS(
            "Jeu de donnees PharmaSovereign-TN cree/verifie avec succes."
        ))
        for model in [
            PharmaFacility,
            Medicine,
            MedicineBatch,
            Shipment,
            ColdChainSensor,
            ColdChainReading,
            BatchScan,
            PharmaAnomaly,
            AgentLoopExecution,
            DrugAuthenticityReceipt,
        ]:
            self.stdout.write(f"{model.__name__}: {model.objects.count()}")
