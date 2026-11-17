
import strawberry
from datetime import date, datetime
from typing import List, Optional

from backend.tunisovereign_core.models import (
    PharmaFacility,
    Medicine,
    MedicineBatch,
    Shipment,
    ColdChainReading,
    PharmaAnomaly,
    DrugAuthenticityReceipt,
    AgentLoopExecution,
)


# =========================
# GRAPHQL TYPES
# =========================

@strawberry.type
class PharmaFacilityType:
    id: str
    code: str
    name: str
    facility_type: str
    governorate: str
    address: Optional[str]
    is_active: bool


@strawberry.type
class MedicineType:
    id: str
    product_code: str
    name: str
    active_ingredient: Optional[str]
    manufacturer: str
    cold_chain_required: bool
    min_storage_temp_c: float
    max_storage_temp_c: float


@strawberry.type
class MedicineBatchType:
    id: str
    batch_number: str
    serial_number: Optional[str]
    manufacturing_date: date
    expiry_date: date
    assigned_governorate: str
    authenticity_status: str
    quantity: int
    medicine_id: str
    medicine_name: str


@strawberry.type
class ShipmentType:
    id: str
    tracking_code: str
    status: str
    shipped_at: Optional[datetime]
    received_at: Optional[datetime]
    batch_number: str
    origin_name: str
    destination_name: str


@strawberry.type
class ColdChainReadingType:
    id: str
    recorded_at: datetime
    temperature_c: float
    humidity_pct: Optional[float]
    ingestion_protocol: str
    sensor_code: str
    shipment_code: str


@strawberry.type
class PharmaAnomalyType:
    id: str
    anomaly_type: str
    severity: str
    description: str
    detection_score: Optional[float]
    detected_at: Optional[datetime]
    is_resolved: bool
    batch_number: str


@strawberry.type
class ZKReceiptType:
    id: str
    commitment_hash: str
    transaction_hash: Optional[str]
    block_number: Optional[int]
    network_name: str
    verification_status: str
    batch_number: str


@strawberry.type
class AgentExecutionType:
    thread_id: str
    trigger_source: str
    darja_transcript: str
    final_recommendation: str
    confidence_score: float
    zk_receipt: Optional[ZKReceiptType]


# =========================
# QUERY ROOT
# =========================

@strawberry.type
class Query:

    @strawberry.field
    def facilities(
        self, governorate: Optional[str] = None
    ) -> List[PharmaFacilityType]:

        qs = PharmaFacility.objects.all().order_by("name")

        if governorate:
            qs = qs.filter(governorate__iexact=governorate)

        return [
            PharmaFacilityType(
                id=str(obj.id),
                code=obj.code,
                name=obj.name,
                facility_type=obj.facility_type,
                governorate=obj.governorate,
                address=obj.address or None,
                is_active=obj.is_active,
            )
            for obj in qs
        ]

    @strawberry.field
    def medicines(self) -> List[MedicineType]:

        return [
            MedicineType(
                id=str(obj.id),
                product_code=obj.product_code,
                name=obj.name,
                active_ingredient=obj.active_ingredient or None,
                manufacturer=obj.manufacturer,
                cold_chain_required=obj.cold_chain_required,
                min_storage_temp_c=float(obj.min_storage_temp_c),
                max_storage_temp_c=float(obj.max_storage_temp_c),
            )
            for obj in Medicine.objects.all().order_by("name")
        ]

    @strawberry.field
    def batches(
        self, governorate: Optional[str] = None
    ) -> List[MedicineBatchType]:

        qs = MedicineBatch.objects.select_related(
            "medicine"
        ).all().order_by("batch_number")

        if governorate:
            qs = qs.filter(assigned_governorate__iexact=governorate)

        return [
            MedicineBatchType(
                id=str(obj.id),
                batch_number=obj.batch_number,
                serial_number=obj.serial_number or None,
                manufacturing_date=obj.manufacturing_date,
                expiry_date=obj.expiry_date,
                assigned_governorate=obj.assigned_governorate,
                authenticity_status=obj.authenticity_status,
                quantity=obj.quantity,
                medicine_id=str(obj.medicine_id),
                medicine_name=obj.medicine.name,
            )
            for obj in qs
        ]

    @strawberry.field
    def shipments(self) -> List[ShipmentType]:

        qs = Shipment.objects.select_related(
            "batch", "origin", "destination"
        ).all().order_by("-created_at")

        return [
            ShipmentType(
                id=str(obj.id),
                tracking_code=obj.tracking_code,
                status=obj.status,
                shipped_at=obj.shipped_at,
                received_at=obj.received_at,
                batch_number=obj.batch.batch_number,
                origin_name=obj.origin.name,
                destination_name=obj.destination.name,
            )
            for obj in qs
        ]

    @strawberry.field
    def cold_chain_readings(
        self
    ) -> List[ColdChainReadingType]:

        qs = ColdChainReading.objects.select_related(
            "sensor", "shipment"
        ).all().order_by("-recorded_at")

        return [
            ColdChainReadingType(
                id=str(obj.id),
                recorded_at=obj.recorded_at,
                temperature_c=float(obj.temperature_c),
                humidity_pct=(
                    float(obj.humidity_pct)
                    if obj.humidity_pct is not None
                    else None
                ),
                ingestion_protocol=obj.ingestion_protocol,
                sensor_code=obj.sensor.sensor_code,
                shipment_code=obj.shipment.tracking_code,
            )
            for obj in qs
        ]

    @strawberry.field
    def anomalies(self) -> List[PharmaAnomalyType]:

        qs = PharmaAnomaly.objects.select_related(
            "batch"
        ).all().order_by("-detected_at")

        return [
            PharmaAnomalyType(
                id=str(obj.id),
                anomaly_type=obj.anomaly_type,
                severity=obj.severity,
                description=obj.description,
                detection_score=(
                    float(obj.detection_score)
                    if obj.detection_score is not None
                    else None
                ),
                detected_at=obj.detected_at,
                is_resolved=obj.is_resolved,
                batch_number=obj.batch.batch_number,
            )
            for obj in qs
        ]

    @strawberry.field
    def zk_receipts(self) -> List[ZKReceiptType]:

        qs = DrugAuthenticityReceipt.objects.select_related(
            "batch"
        ).all().order_by("-created_at")

        return [
            ZKReceiptType(
                id=str(obj.id),
                commitment_hash=obj.commitment_hash,
                transaction_hash=obj.transaction_hash,
                block_number=obj.block_number,
                network_name=obj.network_name,
                verification_status=obj.verification_status,
                batch_number=obj.batch.batch_number,
            )
            for obj in qs
        ]

    @strawberry.field
    def agent_executions(self) -> List[AgentExecutionType]:

        executions = list(
            AgentLoopExecution.objects.all().order_by("-created_at")[:50]
        )

        receipts = DrugAuthenticityReceipt.objects.filter(
            agent_execution__in=executions
        ).select_related("batch").order_by("-created_at")

        receipt_by_execution = {}

        for receipt in receipts:
            execution_id = receipt.agent_execution_id

            if execution_id not in receipt_by_execution:
                receipt_by_execution[execution_id] = ZKReceiptType(
                    id=str(receipt.id),
                    commitment_hash=receipt.commitment_hash,
                    transaction_hash=receipt.transaction_hash,
                    block_number=receipt.block_number,
                    network_name=receipt.network_name,
                    verification_status=receipt.verification_status,
                    batch_number=receipt.batch.batch_number,
                )

        return [
            AgentExecutionType(
                thread_id=obj.thread_id,
                trigger_source=obj.trigger_source,
                darja_transcript=obj.darja_transcript,
                final_recommendation=obj.final_recommendation,
                confidence_score=float(obj.confidence_score),
                zk_receipt=receipt_by_execution.get(obj.id),
            )
            for obj in executions
        ]


schema = strawberry.Schema(query=Query)
